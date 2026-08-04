from __future__ import annotations

from types import SimpleNamespace
import struct
import unittest

from trinity_host.full_flow import (
    DEFAULT_KEYPAIR_SEED,
    DEFAULT_PLAINTEXTS,
    DEFAULT_SESSION_SEED,
    generate_keypair,
    parse_plaintext_hex,
    parse_seed_hex,
    run_secure_telemetry_qualification,
)
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
from trinity_host.serial_client import HostProtocolError, SystemInfo


class FullFlowFakeClient:
    def __init__(self) -> None:
        self.next_txid = 1
        self.retained: dict[int, TransactionResult] = {}
        self.retired: list[int] = []
        self.commands: list[HostCommand] = []
        self.phase = "ready"
        self.session_id = 0x11223344
        self.sequence = 0
        self.last_payload = b""
        self.info = SystemInfo(
            1,
            0,
            7,
            26,
            int(
                SystemCapability.KAT
                | SystemCapability.MLKEM512
                | SystemCapability.ASCON_AEAD128
                | SystemCapability.PAYLOAD_UART
                | SystemCapability.TRANSACTION_RECONCILIATION
            ),
            0x0007001A,
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
        return SimpleNamespace(transaction_id=txid, payload=payload)

    def request(self, command, payload=b"", *, timeout=2.0):
        del timeout
        command = HostCommand(command)
        self.commands.append(command)
        if command == HostCommand.GENERATE_KEYPAIR:
            self.assertEqual(payload, bytes((1,)) + DEFAULT_KEYPAIR_SEED)
            self.phase = "keypair"
            return self._response(command, bytes(range(32)), True)
        if command == HostCommand.CREATE_SESSION:
            self.assertEqual(payload, bytes((1,)) + DEFAULT_SESSION_SEED)
            self.phase = "active"
            return self._response(
                command,
                struct.pack(">IQ", self.session_id, self.sequence),
                True,
            )
        if command == HostCommand.SEND_ONE_TELEMETRY:
            self.assertEqual(len(payload), 32)
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
            self.assertEqual(payload, b"\xFF")
            self.phase = "ready"
            self.sequence = 0
            return self._response(command, b"", True)
        raise AssertionError(command)

    def get_transaction_result(self, host_txid: int) -> TransactionResult:
        return self.retained[host_txid]

    def retire_transaction_result(self, host_txid: int) -> None:
        self.retired.append(host_txid)
        del self.retained[host_txid]

    def get_system_status(self) -> SystemStatus:
        state = {
            "ready": SystemState.READY_NO_KEYPAIR,
            "keypair": SystemState.READY_NO_SESSION,
            "active": SystemState.ACTIVE,
        }[self.phase]
        return SystemStatus(
            state,
            Mode.KAT,
            int(
                TargetReadyMask.SN32
                | TargetReadyMask.PRIMER1
                | TargetReadyMask.PRIMER2
            ),
            0,
            self.session_id if self.phase == "active" else 0,
            self.sequence if self.phase == "active" else 0,
            ErrorCode.OK,
            0,
        )

    def run_sn32_hardware_qualification(self, **_kwargs):
        return SimpleNamespace(dual_spi=SimpleNamespace(info=self.info))

    @staticmethod
    def assertEqual(actual, expected) -> None:
        if actual != expected:
            raise AssertionError(f"{actual!r} != {expected!r}")


class FullFlowTests(unittest.TestCase):
    def test_seed_and_plaintext_parsers_are_exact_length(self) -> None:
        self.assertEqual(parse_seed_hex("00" * 32), bytes(32))
        self.assertEqual(parse_plaintext_hex("AB" * 24), bytes([0xAB]) * 24)
        with self.assertRaisesRegex(ValueError, "exactly 32 bytes"):
            parse_seed_hex("00" * 31)
        with self.assertRaisesRegex(ValueError, "exactly 24 bytes"):
            parse_plaintext_hex("00" * 23)

    def test_managed_result_is_verified_and_retired(self) -> None:
        client = FullFlowFakeClient()
        result = generate_keypair(client)
        self.assertEqual(result.public_key_hash, bytes(range(32)))
        self.assertEqual(client.retained, {})
        self.assertEqual(client.retired, [result.host_txid])

    def test_secure_telemetry_qualification_runs_two_sequences_and_zeroizes(self) -> None:
        client = FullFlowFakeClient()
        result = run_secure_telemetry_qualification(
            client,
            timeout=0.1,
            poll_interval=0.0,
        )

        self.assertEqual(result.status_before.system_state, SystemState.READY_NO_KEYPAIR)
        self.assertEqual(result.status_active.system_state, SystemState.ACTIVE)
        self.assertEqual(result.session.session_id, client.session_id)
        self.assertEqual(
            [packet.sequence for packet in result.telemetry],
            [1, 2],
        )
        self.assertEqual(
            [packet.plaintext for packet in result.telemetry],
            list(DEFAULT_PLAINTEXTS),
        )
        self.assertEqual(result.last_result.sequence, 2)
        self.assertEqual(result.status_final.system_state, SystemState.READY_NO_KEYPAIR)
        self.assertEqual(result.status_final.session_id, 0)
        self.assertEqual(result.status_final.current_sequence, 0)
        self.assertEqual(client.retained, {})
        self.assertEqual(
            client.commands,
            [
                HostCommand.GENERATE_KEYPAIR,
                HostCommand.CREATE_SESSION,
                HostCommand.SEND_ONE_TELEMETRY,
                HostCommand.SEND_ONE_TELEMETRY,
                HostCommand.READ_LAST_RESULT,
                HostCommand.ZEROIZE_SYSTEM,
            ],
        )

    def test_preflight_rejects_nonclean_start(self) -> None:
        client = FullFlowFakeClient()
        client.phase = "active"
        with self.assertRaisesRegex(
            HostProtocolError,
            "requires READY_NO_KEYPAIR",
        ):
            run_secure_telemetry_qualification(client)
        self.assertEqual(client.commands, [])


if __name__ == "__main__":
    unittest.main()
