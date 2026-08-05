from __future__ import annotations

from datetime import datetime
from pathlib import Path
import queue
import threading
import traceback

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Tkinter is required for the Trinity demo GUI") from exc

try:
    from serial.tools import list_ports  # type: ignore
except ImportError:  # pragma: no cover
    list_ports = None

from .demo_core import CoreDemoResult, run_core_demo
from .full_flow import DEFAULT_PLAINTEXTS, emergency_zeroize, parse_plaintext_hex
from .serial_client import TrinitySerialClient


class TrinityDemoApp:
    """Operator dashboard for the SN32/P1/P2 no-Tiny core demo."""

    POLL_MS = 75

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Trinity — FPGA/PQC Secure Telemetry Demo")
        self.root.geometry("1040x720")
        self.root.minsize(920, 640)

        self._queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._worker: threading.Thread | None = None
        self._log_lines: list[str] = []

        self.port_var = tk.StringVar(value="COM3")
        self.plaintext_var = tk.StringVar(value=DEFAULT_PLAINTEXTS[0].hex().upper())
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_text_var = tk.StringVar(value="Sẵn sàng")
        self.result_var = tk.StringVar(value="CHƯA CHẠY")
        self.sn32_var = tk.StringVar(value="—")
        self.p1_var = tk.StringVar(value="—")
        self.p2_var = tk.StringVar(value="—")
        self.state_var = tk.StringVar(value="—")
        self.session_var = tk.StringVar(value="—")
        self.sequence_var = tk.StringVar(value="—")

        self._build_ui()
        self.refresh_ports()
        self.root.after(self.POLL_MS, self._drain_queue)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            outer,
            text="FPGA–PQC Secure Telemetry",
            font=("Segoe UI", 19, "bold"),
        ).pack(anchor=tk.W)
        ttk.Label(
            outer,
            text="Core demo: PC ↔ SN32 ↔ Primer #1 → UART → Primer #2",
        ).pack(anchor=tk.W, pady=(2, 10))

        warning = tk.Frame(
            outer,
            bg="#FFF3CD",
            highlightbackground="#D4A72C",
            highlightthickness=1,
        )
        warning.pack(fill=tk.X, pady=(0, 10))
        tk.Label(
            warning,
            bg="#FFF3CD",
            fg="#5F4500",
            font=("Segoe UI", 9, "bold"),
            text=(
                "PHẠM VI DEMO: Tiny 1P5 tạm thời không sử dụng. "
                "SN32 P2.9 phải nối trực tiếp tới SECURE_ENABLE/T12 của cả P1 và P2. "
                "Nếu commit lỗi, GUI hiển thị readback P2.9 và trạng thái riêng của P1/P2, "
                "sau đó tự emergency-zeroize."
            ),
            wraplength=980,
            justify=tk.LEFT,
            padx=10,
            pady=8,
        ).pack(fill=tk.X)

        connection = ttk.LabelFrame(outer, text="Kết nối", padding=10)
        connection.pack(fill=tk.X)
        ttk.Label(connection, text="Cổng UART:").grid(row=0, column=0, sticky=tk.W)
        self.port_combo = ttk.Combobox(
            connection,
            textvariable=self.port_var,
            width=18,
            state="normal",
        )
        self.port_combo.grid(row=0, column=1, padx=8, sticky=tk.W)
        ttk.Button(connection, text="Làm mới", command=self.refresh_ports).grid(
            row=0, column=2, padx=(0, 8)
        )
        self.preflight_button = ttk.Button(
            connection,
            text="Kiểm tra nhanh",
            command=self.start_preflight,
        )
        self.preflight_button.grid(row=0, column=3, padx=(0, 12))
        ttk.Label(connection, text="Kết quả:").grid(row=0, column=4, sticky=tk.E)
        self.result_label = ttk.Label(
            connection,
            textvariable=self.result_var,
            font=("Segoe UI", 12, "bold"),
        )
        self.result_label.grid(row=0, column=5, padx=(8, 0), sticky=tk.W)

        cards = ttk.Frame(outer)
        cards.pack(fill=tk.X, pady=10)
        for column, (title, variable) in enumerate(
            (
                ("SN32", self.sn32_var),
                ("Primer #1", self.p1_var),
                ("Primer #2", self.p2_var),
                ("System state", self.state_var),
                ("Session ID", self.session_var),
                ("Sequence", self.sequence_var),
            )
        ):
            card = ttk.LabelFrame(cards, text=title, padding=(8, 6))
            card.grid(row=0, column=column, padx=3, sticky=tk.EW)
            ttk.Label(card, textvariable=variable, font=("Consolas", 10, "bold")).pack()
            cards.columnconfigure(column, weight=1)

        payload = ttk.LabelFrame(outer, text="Payload demo", padding=10)
        payload.pack(fill=tk.X)
        ttk.Label(payload, text="Plaintext 24 byte (48 hex):").pack(anchor=tk.W)
        ttk.Entry(
            payload,
            textvariable=self.plaintext_var,
            font=("Consolas", 10),
        ).pack(fill=tk.X, pady=(4, 0))

        controls = ttk.Frame(outer)
        controls.pack(fill=tk.X, pady=10)
        self.demo_button = ttk.Button(
            controls,
            text="CHẠY CORE DEMO",
            command=self.start_demo,
        )
        self.demo_button.pack(side=tk.LEFT)
        self.zeroize_button = ttk.Button(
            controls,
            text="ZEROIZE KHẨN CẤP",
            command=self.start_zeroize,
        )
        self.zeroize_button.pack(side=tk.LEFT, padx=8)
        ttk.Button(controls, text="Xuất log", command=self.export_log).pack(side=tk.RIGHT)

        ttk.Progressbar(
            outer,
            variable=self.progress_var,
            maximum=100,
        ).pack(fill=tk.X)
        ttk.Label(outer, textvariable=self.progress_text_var).pack(
            anchor=tk.W, pady=(3, 8)
        )

        log_frame = ttk.LabelFrame(outer, text="Nhật ký", padding=6)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_text = tk.Text(
            log_frame,
            height=18,
            wrap=tk.WORD,
            font=("Consolas", 9),
            state=tk.DISABLED,
        )
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def refresh_ports(self) -> None:
        ports = [] if list_ports is None else [item.device for item in list_ports.comports()]
        self.port_combo["values"] = ports
        if ports and self.port_var.get() not in ports:
            self.port_var.set(ports[0])
        self._log("Đã làm mới danh sách cổng UART")

    def _set_busy(self, busy: bool) -> None:
        state = tk.DISABLED if busy else tk.NORMAL
        self.demo_button.configure(state=state)
        self.preflight_button.configure(state=state)
        self.zeroize_button.configure(state=state)

    def _start_worker(self, name: str, target) -> None:
        if self._worker is not None and self._worker.is_alive():
            messagebox.showwarning("Trinity", "Một thao tác khác đang chạy")
            return
        self._set_busy(True)
        self.result_var.set("ĐANG CHẠY")
        self._worker = threading.Thread(
            target=self._worker_entry,
            args=(name, target),
            daemon=True,
        )
        self._worker.start()

    def _worker_entry(self, name: str, target) -> None:
        try:
            result = target()
            self._queue.put(("success", (name, result)))
        except Exception as exc:  # pragma: no cover - hardware-dependent
            self._queue.put(("failure", (name, exc, traceback.format_exc())))

    def _open_client(self) -> TrinitySerialClient:
        port = self.port_var.get().strip()
        if not port:
            raise ValueError("Chưa chọn cổng UART")
        return TrinitySerialClient(port)

    def start_preflight(self) -> None:
        def work():
            with self._open_client() as client:
                uptime = client.ping()
                info = client.get_system_info()
                status = client.get_system_status()
                return uptime, info, status

        self._start_worker("preflight", work)

    def start_demo(self) -> None:
        try:
            plaintext = parse_plaintext_hex(self.plaintext_var.get())
        except ValueError as exc:
            messagebox.showerror("Payload không hợp lệ", str(exc))
            return

        self.progress_var.set(0)
        self.progress_text_var.set("Bắt đầu core demo")

        def on_progress(message: str, percent: int | None) -> None:
            self._queue.put(("progress", (message, percent)))

        def work() -> CoreDemoResult:
            with self._open_client() as client:
                return run_core_demo(
                    client,
                    plaintext=plaintext,
                    timeout=120.0,
                    on_progress=on_progress,
                )

        self._start_worker("demo", work)

    def start_zeroize(self) -> None:
        def work():
            with self._open_client() as client:
                result = emergency_zeroize(client, timeout=30.0)
                status = client.get_system_status()
                uptime = client.ping()
                return result, status, uptime

        self._start_worker("zeroize", work)

    def _drain_queue(self) -> None:
        while True:
            try:
                kind, payload = self._queue.get_nowait()
            except queue.Empty:
                break
            if kind == "progress":
                message, percent = payload
                self.progress_text_var.set(str(message))
                if percent is not None:
                    self.progress_var.set(float(percent))
                self._log(str(message))
            elif kind == "success":
                name, result = payload
                self._handle_success(str(name), result)
                self._set_busy(False)
            elif kind == "failure":
                name, exc, trace = payload
                self.result_var.set("FAIL")
                self.progress_text_var.set(str(exc))
                self._log(f"{name.upper()} FAIL: {exc}")
                self._log(str(trace))
                self._set_busy(False)
                messagebox.showerror("Trinity", str(exc))
        self.root.after(self.POLL_MS, self._drain_queue)

    def _handle_success(self, name: str, result: object) -> None:
        if name == "preflight":
            uptime, info, status = result
            self.sn32_var.set(
                f"{info.architecture_major}.{info.architecture_minor}."
                f"{info.architecture_patch}\n0x{info.sn32_build_id:08X}"
            )
            self.p1_var.set(f"0x{info.primer1_build_id:08X}")
            self.p2_var.set(f"0x{info.primer2_build_id:08X}")
            self.state_var.set(status.system_state.name)
            self.session_var.set(f"0x{status.session_id:08X}")
            self.sequence_var.set(str(status.current_sequence))
            self.result_var.set("PREFLIGHT PASS")
            self._log(f"PING PASS, uptime_ms={uptime}")
        elif name == "demo":
            demo = result
            self.sn32_var.set(
                f"{demo.info.architecture_major}.{demo.info.architecture_minor}."
                f"{demo.info.architecture_patch}\n"
                f"0x{demo.info.sn32_build_id:08X}"
            )
            self.p1_var.set(f"0x{demo.info.primer1_build_id:08X}")
            self.p2_var.set(f"0x{demo.info.primer2_build_id:08X}")
            self.state_var.set(demo.status_final.system_state.name)
            self.session_var.set(f"0x{demo.session.session_id:08X}")
            self.sequence_var.set(str(demo.telemetry.sequence))
            self.result_var.set("CORE DEMO PASS")
            self.progress_var.set(100)
            self.progress_text_var.set("CORE DEMO PASS")
            self._log(
                "Authenticated plaintext=" + demo.telemetry.plaintext.hex().upper()
            )
            self._log(f"Final PING uptime_ms={demo.final_uptime_ms}")
        else:
            _zeroize_result, status, uptime = result
            self.state_var.set(status.system_state.name)
            self.session_var.set(f"0x{status.session_id:08X}")
            self.sequence_var.set(str(status.current_sequence))
            self.result_var.set("ZEROIZE PASS")
            self._log(f"EMERGENCY ZEROIZE PASS, final uptime_ms={uptime}")

    def _log(self, message: str) -> None:
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
        self._log_lines.append(line)
        if hasattr(self, "log_text"):
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, line + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)

    def export_log(self) -> None:
        default_name = "trinity_demo_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt"
        filename = filedialog.asksaveasfilename(
            title="Xuất log Trinity",
            defaultextension=".txt",
            initialfile=default_name,
            filetypes=(("Text", "*.txt"), ("All files", "*.*")),
        )
        if not filename:
            return
        Path(filename).write_text("\n".join(self._log_lines) + "\n", encoding="utf-8")
        self._log(f"Đã xuất log: {filename}")


def main() -> int:
    root = tk.Tk()
    TrinityDemoApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
