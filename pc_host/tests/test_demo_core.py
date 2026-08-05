from __future__ import annotations

from types import SimpleNamespace
import struct
import unittest

from trinity_host.demo_core import run_core_demo
from trinity_host.full_flow import DEFAULT_PLAINTEXTS
from trinity_host.protocol import (
    ErrorCode,
    HostCommand,
    Mode,
    SystemCapability,
    SystemState,
    SystemStatus,
    TargetReadyMask,
    TransactionResult,
    TransactionState,
)
from trinity_host.serial_client import (
    HostProtocolError,
    LastErrorSnapshot,
    RemoteError,
    SystemInfo,
)


class CoreDemoFakeClient:
    def __init__(
        self,
        *,
        fail_session: bool = False,
        zeroize_state: SystemState = SystemState.READY_NO_KEYPAIR,
        dirty_zeroize: bool = False,
    ) -> None:
        self.next_txid = 1
        self.retained: dict[int, TransactionResult] = {}
        self.commands: list[HostCommand] = []
        self.phase = "ready"
        self.fail_session = fail_session
        self.zeroize_state = zeroize_state
        self.dirty_zeroize = dirty_zeroize
        self.active_host_txid = 0
        self.session_id = 0xA1B2C3D4
        self.sequence = 0
        self.last_payload = b""
        self.info = SystemInfo(
            1,
            0,
            7,
            31,
            int(
                SystemCapability.KAT
                | SystemCapability.MLKEM512
                | SystemCapability.ASCON_AEAD128
                | SystemCapability.PAYLOAD_UART
                | SystemCapability.TRANSACTION_RECONCILIATION
            ),
            0x0007001F,
            0x5031D003,
            0x50320002,
        )

    def _response(self, command: HostCommand, payload: bytes, retained: bool):
        txid = self.next_txid
        self.next_txid += 1
        if retained:
            self.retained[txid] = TransactionResult(
                txid,
                TransactionState.SUCCEEDED,
                int(command),
                ErrorCode.OK,
                payload,
            )
            self.active_host_txid = txid
        return SimpleNamespace(transaction_id=txid, payload=payload)

    def request(self, command, payload=b"", *, timeout=2.0):
        del timeout
        command = HostCommand(command)
        self.commands.append(command)
        if command == HostCommand.GENERATE_KEYPAIR:
            self.phase = "keypair"
            return self._response(command, bytes(range(32)), True)
        if command == HostCommand.CREATE_SESSION:
            if self.fail_session:
                txid = self.next_txid
                self.next_txid += 1
                self.active_host_txid = txid
                self.retained[txid] = TransactionResult(
                    txid,
                    TransactionState.FAILED,
                    int(command),
                    ErrorCode.SESSION_COMMIT_FAILED,
                    b"",
                )
                self.phase = "fault"
                raise RemoteError(
                    ErrorCode.SESSION_COMMIT_FAILED,
                    int(SystemState.FAULT_LOCKED),
                    0,
                    0,
                )
            self.phase = "active"
            return self._response(
                command,
                struct.pack(">IQ", self.session_id, self.sequence),
                True,
            )
        if command == HostCommand.SEND_ONE_TELEMETRY:
            self.sequence += 1
            wire = (
                struct.pack(">IQ", self.session_id, self.sequence)
                + payload[8:]
                + struct.pack(">H", int(ErrorCode.OK))
            )
            self.last_payload = wire
            return self._response(command, wire, True)
        if command == HostCommand.READ_LAST_RESULT:
            return self._response(command, self.last_payload, False)
        if command == HostCommand.ZEROIZE_SYSTEM:
            self.phase = (
                "self_test_required"
                if self.zeroize_state == SystemState.SELF_TEST_REQUIRED
                else "ready"
            )
            self.sequence = 1 if self.dirty_zeroize else 0
            self.active_host_txid = 0
            return self._response(command, b"", True)
        raise AssertionError(command)

    def get_transaction_result(self, host_txid: int) -> TransactionResult:
        return self.retained[host_txid]

    def retire_transaction_result(self, host_txid: int) -> None:
        del self.retained[host_txid]
        if self.active_host_txid == host_txid:
            self.active_host_txid = 0

    def get_system_status(self) -> SystemStatus:
        state = {
            "ready": SystemState.READY_NO_KEYPAIR,
            "self_test_required": SystemState.SELF_TEST_REQUIRED,
            "keypair": SystemState.READY_NO_SESSION,
            "active": SystemState.ACTIVE,
            "fault": SystemState.FAULT_LOCKED,
        }[self.phase]
        return SystemStatus(
            state,
            Mode.KAT,
            int(
                TargetReadyMask.SN32
                | TargetReadyMask.PRIMER1
                | TargetReadyMask.PRIMER2
            ),
            0x11 if self.phase == "fault" else 0,
            self.session_id if self.phase == "active" else 0,
            self.sequence,
            (
                ErrorCode.SESSION_COMMIT_FAILED
                if self.phase == "fault"
                else ErrorCode.OK
            ),
            self.active_host_txid,
        )

    def get_last_error(self) -> LastErrorSnapshot:
        return LastErrorSnapshot(
            ErrorCode.SESSION_COMMIT_FAILED,
            0,
            0x38550303,
        )

    def run_sn32_hardware_qualification(self, **_kwargs):
        return SimpleNamespace(dual_spi=SimpleNamespace(info=self.info))

    def ping(self) -> int:
        return 123456


class CoreDemoTests(unittest.TestCase):
    def test_one_packet_demo_runs_and_zeroizes(self) -> None:
        client = CoreDemoFakeClient()
        progress: list[tuple[str, int | None]] = []
        result = run_core_demo(
            client,
            plaintext=DEFAULT_PLAINTEXTS[0],
            timeout=0.1,
            on_progress=lambda text, percent: progress.append((text, percent)),
        )

        self.assertEqual(result.info.sn32_build_id, 0x0007001F)
        self.assertEqual(result.session.session_id, client.session_id)
        self.assertEqual(result.telemetry.sequence, 1)
        self.assertEqual(result.telemetry.plaintext, DEFAULT_PLAINTEXTS[0])
        self.assertEqual(result.last_result.session_id, result.telemetry.session_id)
        self.assertEqual(result.last_result.sequence, result.telemetry.sequence)
        self.assertEqual(result.last_result.plaintext, result.telemetry.plaintext)
        self.assertEqual(result.last_result.status, result.telemetry.status)
        self.assertEqual(result.status_final.system_state, SystemState.READY_NO_KEYPAIR)
        self.assertEqual(result.final_uptime_ms, 123456)
        self.assertEqual(client.retained, {})
        self.assertEqual(
            client.commands,
            [
                HostCommand.GENERATE_KEYPAIR,
                HostCommand.CREATE_SESSION,
                HostCommand.SEND_ONE_TELEMETRY,
                HostCommand.READ_LAST_RESULT,
                HostCommand.ZEROIZE_SYSTEM,
            ],
        )
        self.assertEqual(progress[-1][1], 100)

    def test_clean_self_test_required_after_zeroize_is_pass(self) -> None:
        client = CoreDemoFakeClient(
            zeroize_state=SystemState.SELF_TEST_REQUIRED,
        )
        progress: list[tuple[str, int | None]] = []
        result = run_core_demo(
            client,
            timeout=0.1,
            on_progress=lambda text, percent: progress.append((text, percent)),
        )

        self.assertEqual(
            result.status_final.system_state,
            SystemState.SELF_TEST_REQUIRED,
        )
        self.assertIn("cần self-test trước phiên tiếp theo", progress[-1][0])
        self.assertEqual(progress[-1][1], 100)
        self.assertEqual(client.retained, {})

    def test_self_test_required_must_still_be_clean(self) -> None:
        client = CoreDemoFakeClient(
            zeroize_state=SystemState.SELF_TEST_REQUIRED,
            dirty_zeroize=True,
        )
        with self.assertRaisesRegex(
            HostProtocolError,
            "zeroize did not leave a clean final status",
        ):
            run_core_demo(client, timeout=0.1)

    def test_commit_failure_is_diagnosed_retired_and_zeroized(self) -> None:
        client = CoreDemoFakeClient(fail_session=True)
        with self.assertRaisesRegex(
            HostProtocolError,
            r"phase=ACTIVE_WAIT.*P2\.9_readback=HIGH.*"
            r"P1=COMMITTED_BLOCKED.*P2=COMMITTED_BLOCKED.*"
            r"emergency_zeroize=PASS",
        ):
            run_core_demo(client, timeout=0.1)
        self.assertEqual(client.phase, "ready")
        self.assertEqual(client.active_host_txid, 0)
        self.assertEqual(client.retained, {})
        self.assertEqual(client.commands[-1], HostCommand.ZEROIZE_SYSTEM)

    def test_plaintext_length_is_enforced_before_hardware(self) -> None:
        client = CoreDemoFakeClient()
        with self.assertRaisesRegex(ValueError, "exactly 24 bytes"):
            run_core_demo(client, plaintext=b"too short")
        self.assertEqual(client.commands, [])


if __name__ == "__main__":
    unittest.main()
