from __future__ import annotations

from datetime import datetime
from pathlib import Path
import queue
import threading
import traceback
from typing import Callable

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError as exc:  # pragma: no cover - platform packaging issue
    raise RuntimeError("Tkinter is required for the Trinity demo GUI") from exc

try:
    from serial.tools import list_ports  # type: ignore
except ImportError:  # pragma: no cover - pyserial installation issue
    list_ports = None

from .demo_core import CoreDemoResult, run_core_demo
from .full_flow import DEFAULT_PLAINTEXTS, parse_plaintext_hex, zeroize
from .protocol import EventEnvelope, SystemState, ZeroizeScope
from .serial_client import TrinitySerialClient


class TrinityDemoApp:
    """Operator-focused GUI for the time-bounded SN32/P1/P2 core demo."""

    POLL_MS = 75

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Trinity — FPGA/PQC Secure Telemetry Demo")
        self.root.geometry("1100x760")
        self.root.minsize(980, 680)

        self._queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._worker: threading.Thread | None = None
        self._log_lines: list[str] = []

        self.port_var = tk.StringVar(value="COM3")
        self.plaintext_var = tk.StringVar(value=DEFAULT_PLAINTEXTS[0].hex().upper())
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_text_var = tk.StringVar(value="Sẵn sàng")
        self.overall_var = tk.StringVar(value="CHƯA CHẠY")

        self.sn32_var = tk.StringVar(value="—")
        self.p1_var = tk.StringVar(value="—")
        self.p2_var = tk.StringVar(value="—")
        self.state_var = tk.StringVar(value="—")
        self.session_var = tk.StringVar(value="—")
        self.sequence_var = tk.StringVar(value="—")

        self._configure_style()
        self._build_ui()
        self.refresh_ports()
        self.root.after(self.POLL_MS, self._drain_queue)

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Header.TLabel", font=("Segoe UI", 19, "bold"))
        style.configure("Subheader.TLabel", font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel", font=("Segoe UI", 9, "bold"))
        style.configure("CardValue.TLabel", font=("Consolas", 12, "bold"))
        style.configure("Pass.TLabel", font=("Segoe UI", 14, "bold"), foreground="#137333")
        style.configure("Fail.TLabel", font=("Segoe UI", 14, "bold"), foreground="#B3261E")
        style.configure("Pending.TLabel", font=("Segoe UI", 14, "bold"), foreground="#5F6368")
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 8))
        style.configure("TButton", padding=(10, 6))

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(outer)
        header.pack(fill=tk.X)
        ttk.Label(header, text="FPGA–PQC Secure Telemetry", style="Header.TLabel").pack(anchor=tk.W)
        ttk.Label(
            header,
            text="Core demo: PC ↔ SN32 ↔ Primer #1 → UART → Primer #2",
            style="Subheader.TLabel",
        ).pack(anchor=tk.W, pady=(2, 0))

        scope = tk.Frame(outer, bg="#FFF3CD", highlightbackground="#E0B84C", highlightthickness=1)
        scope.pack(fill=tk.X, pady=(12, 10))
        tk.Label(
            scope,
            bg="#FFF3CD",
            fg="#5F4500",
            font=("Segoe UI", 9, "bold"),
            text=(
                "PHẠM VI DEMO: Tiny 1P5 tạm thời không sử dụng. "
                "SN32 P3.8 phải nối trực tiếp tới SECURE_ENABLE/T12 của cả P1 và P2. "
                "Không tuyên bố full-system hoặc Tiny safety PASS."
            ),
            wraplength=1030,
            justify=tk.LEFT,
            padx=10,
            pady=8,
        ).pack(fill=tk.X)

        connection = ttk.LabelFrame(outer, text="Kết nối", padding=10)
        connection.pack(fill=tk.X)
        ttk.Label(connection, text="Cổng UART:").grid(row=0, column=0, sticky=tk.W)
        self.port_combo = ttk.Combobox(connection, textvariable=self.port_var, width=18)
        self.port_combo.grid(row=0, column=1, padx=(8, 8), sticky=tk.W)
        self.refresh_button = ttk.Button(connection, text="Làm mới", command=self.refresh_ports)
        self.refresh_button.grid(row=0, column=2, padx=(0, 14))
        self.preflight_button = ttk.Button(
            connection, text="Kiểm tra nhanh", command=self.start_preflight
        )
        self.preflight_button.grid(row=0, column=3, padx=(0, 8))
        ttk.Label(connection, text="Kết quả:").grid(row=0, column=4, padx=(16, 6))
        self.overall_label = ttk.Label(
            connection, textvariable=self.overall_var, style="Pending.TLabel"
        )
        self.overall_label.grid(row=0, column=5, sticky=tk.W)
        connection.columnconfigure(6, weight=1)

        cards = ttk.Frame(outer)
        cards.pack(fill=tk.X, pady=10)
        card_specs = (
            ("SN32", self.sn32_var),
            ("Primer #1", self.p1_var),
            ("Primer #2", self.p2_var),
            ("System state", self.state_var),
            ("Session ID", self.session_var),
            ("Sequence", self.sequence_var),
        )
        for column, (title, variable) in enumerate(card_specs):
            card = ttk.LabelFrame(cards, padding=(10, 8))
            card.grid(row=0, column=column, padx=(0 if column == 0 else 5, 5), sticky="nsew")
            ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor=tk.W)
            ttk.Label(card, textvariable=variable, style="CardValue.TLabel").pack(anchor=tk.W, pady=(5, 0))
            cards.columnconfigure(column, weight=1)

        demo = ttk.LabelFrame(outer, text="Demo một gói telemetry đã xác thực", padding=10)
        demo.pack(fill=tk.X)
        ttk.Label(demo, text="Plaintext 24 byte (hex):").grid(row=0, column=0, sticky=tk.W)
        self.plaintext_entry = ttk.Entry(demo, textvariable=self.plaintext_var, font=("Consolas", 10))
        self.plaintext_entry.grid(row=0, column=1, padx=(8, 8), sticky="ew")
        ttk.Button(
            demo,
            text="Mẫu mặc định",
            command=lambda: self.plaintext_var.set(DEFAULT_PLAINTEXTS[0].hex().upper()),
        ).grid(row=0, column=2, padx=(0, 8))
        self.run_button = ttk.Button(
            demo, text="CHẠY CORE DEMO", style="Primary.TButton", command=self.start_demo
        )
        self.run_button.grid(row=0, column=3, padx=(4, 0))
        demo.columnconfigure(1, weight=1)

        progress = ttk.Frame(outer)
        progress.pack(fill=tk.X, pady=(10, 8))
        self.progress_bar = ttk.Progressbar(
            progress, variable=self.progress_var, maximum=100.0, mode="determinate"
        )
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(progress, textvariable=self.progress_text_var, width=48).pack(
            side=tk.LEFT, padx=(10, 0)
        )

        log_frame = ttk.LabelFrame(outer, text="Nhật ký demo", padding=8)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_text = tk.Text(
            log_frame,
            height=18,
            wrap=tk.WORD,
            font=("Consolas", 9),
            state=tk.DISABLED,
            bg="#111827",
            fg="#E5E7EB",
            insertbackground="#E5E7EB",
            relief=tk.FLAT,
        )
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        footer = ttk.Frame(outer)
        footer.pack(fill=tk.X, pady=(8, 0))
        self.zeroize_button = ttk.Button(
            footer, text="Zeroize khẩn cấp", command=self.start_zeroize
        )
        self.zeroize_button.pack(side=tk.LEFT)
        ttk.Button(footer, text="Xóa log", command=self.clear_log).pack(side=tk.LEFT, padx=8)
        ttk.Button(footer, text="Xuất log…", command=self.export_log).pack(side=tk.LEFT)
        ttk.Label(
            footer,
            text="Deterministic KAT mode — phục vụ trình diễn và kiểm chứng lặp lại",
        ).pack(side=tk.RIGHT)

    def refresh_ports(self) -> None:
        if list_ports is None:
            self._append_log("Không tìm thấy pyserial; chạy: python -m pip install -e pc_host")
            return
        ports = [port.device for port in list_ports.comports()]
        self.port_combo["values"] = ports
        if ports and self.port_var.get() not in ports:
            self.port_var.set(ports[0])
        self._append_log("Cổng khả dụng: " + (", ".join(ports) if ports else "không có"))

    def _set_busy(self, busy: bool) -> None:
        state = tk.DISABLED if busy else tk.NORMAL
        for widget in (
            self.refresh_button,
            self.preflight_button,
            self.run_button,
            self.zeroize_button,
            self.plaintext_entry,
            self.port_combo,
        ):
            widget.configure(state=state)

    def _start_worker(self, name: str, target: Callable[[], None]) -> None:
        if self._worker is not None and self._worker.is_alive():
            messagebox.showwarning("Trinity", "Một tác vụ khác đang chạy.")
            return
        self._set_busy(True)
        self.overall_var.set("ĐANG CHẠY")
        self.overall_label.configure(style="Pending.TLabel")
        self.progress_var.set(0)
        self.progress_text_var.set(name)
        self._worker = threading.Thread(target=target, name=f"trinity-{name}", daemon=True)
        self._worker.start()

    def _client(self, event_handler: Callable[[EventEnvelope], None] | None = None) -> TrinitySerialClient:
        port = self.port_var.get().strip()
        if not port:
            raise ValueError("Chưa chọn cổng UART")
        return TrinitySerialClient(port, event_handler=event_handler)

    def _event_handler(self, event: EventEnvelope) -> None:
        text = f"EVENT {event.event_type.name} source={event.source.name} txid=0x{event.related_transaction_id:04X}"
        if event.progress_percent is not None:
            text += f" progress={event.progress_percent}%"
            self._queue.put(("progress", (event.progress_percent, text)))
        self._queue.put(("log", text))

    def start_preflight(self) -> None:
        def worker() -> None:
            try:
                with self._client(self._event_handler) as client:
                    uptime = client.ping()
                    info = client.get_system_info()
                    status = client.get_system_status()
                self._queue.put(("identity", (info, status)))
                self._queue.put(("log", f"PING PASS uptime={uptime} ms"))
                self._queue.put(("done", "PREFLIGHT PASS"))
            except Exception as exc:
                self._queue.put(("error", ("PREFLIGHT FAIL", exc, traceback.format_exc())))

        self._start_worker("Kiểm tra nhanh", worker)

    def start_demo(self) -> None:
        try:
            plaintext = parse_plaintext_hex(self.plaintext_var.get())
        except ValueError as exc:
            messagebox.showerror("Plaintext không hợp lệ", str(exc))
            return

        def progress(message: str, percent: int | None) -> None:
            self._queue.put(("log", message))
            if percent is not None:
                self._queue.put(("progress", (percent, message)))

        def worker() -> None:
            try:
                with self._client(self._event_handler) as client:
                    result = run_core_demo(
                        client,
                        plaintext=plaintext,
                        timeout=120.0,
                        on_progress=progress,
                    )
                self._queue.put(("demo_result", result))
                self._queue.put(("done", "CORE DEMO PASS"))
            except Exception as exc:
                self._queue.put(("error", ("CORE DEMO FAIL", exc, traceback.format_exc())))

        self._start_worker("Khởi động core demo", worker)

    def start_zeroize(self) -> None:
        def worker() -> None:
            try:
                with self._client(self._event_handler) as client:
                    txid = zeroize(client, scope=ZeroizeScope.ALL, timeout=30.0)
                    status = client.get_system_status()
                    uptime = client.ping()
                self._queue.put(("status_only", status))
                self._queue.put(("log", f"ZEROIZE PASS host_txid=0x{txid:04X}, uptime={uptime} ms"))
                self._queue.put(("done", "ZEROIZE PASS"))
            except Exception as exc:
                self._queue.put(("error", ("ZEROIZE FAIL", exc, traceback.format_exc())))

        self._start_worker("Zeroize", worker)

    def _update_identity(self, info: object, status: object) -> None:
        # Kept duck-typed so GUI rendering remains isolated from unit tests.
        self.sn32_var.set(
            f"{info.architecture_major}.{info.architecture_minor}.{info.architecture_patch}\n"
            f"0x{info.sn32_build_id:08X}"
        )
        self.p1_var.set(f"0x{info.primer1_build_id:08X}")
        self.p2_var.set(f"0x{info.primer2_build_id:08X}")
        self._update_status(status)

    def _update_status(self, status: object) -> None:
        self.state_var.set(status.system_state.name)
        self.session_var.set(f"0x{status.session_id:08X}")
        self.sequence_var.set(str(status.current_sequence))

    def _show_demo_result(self, result: CoreDemoResult) -> None:
        self._update_identity(result.info, result.status_final)
        self._append_log(
            "ML-KEM public-key hash: " + result.keypair.public_key_hash.hex()
        )
        self._append_log(f"Session activated: 0x{result.session.session_id:08X}")
        self._append_log(
            f"Authenticated telemetry: sequence={result.telemetry.sequence}, "
            f"plaintext={result.telemetry.plaintext.hex().upper()}"
        )
        self._append_log(
            f"Final zeroize: {result.status_final.system_state.name}; "
            f"PING uptime={result.final_uptime_ms} ms"
        )

    def _drain_queue(self) -> None:
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "log":
                    self._append_log(str(payload))
                elif kind == "progress":
                    percent, text = payload  # type: ignore[misc]
                    self.progress_var.set(float(percent))
                    self.progress_text_var.set(str(text))
                elif kind == "identity":
                    info, status = payload  # type: ignore[misc]
                    self._update_identity(info, status)
                elif kind == "status_only":
                    self._update_status(payload)
                elif kind == "demo_result":
                    self._show_demo_result(payload)  # type: ignore[arg-type]
                elif kind == "done":
                    self.overall_var.set(str(payload))
                    self.overall_label.configure(style="Pass.TLabel")
                    self.progress_var.set(100)
                    self.progress_text_var.set(str(payload))
                    self._set_busy(False)
                elif kind == "error":
                    title, exc, detail = payload  # type: ignore[misc]
                    self.overall_var.set(str(title))
                    self.overall_label.configure(style="Fail.TLabel")
                    self.progress_text_var.set(str(exc))
                    self._append_log(f"{title}: {exc}")
                    self._append_log(str(detail))
                    self._set_busy(False)
                    messagebox.showerror(str(title), str(exc))
        except queue.Empty:
            pass
        self.root.after(self.POLL_MS, self._drain_queue)

    def _append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}"
        self._log_lines.append(line)
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, line + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def clear_log(self) -> None:
        self._log_lines.clear()
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def export_log(self) -> None:
        default_name = f"trinity_core_demo_{datetime.now():%Y%m%d_%H%M%S}.txt"
        selected = filedialog.asksaveasfilename(
            title="Xuất nhật ký Trinity",
            initialfile=default_name,
            defaultextension=".txt",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*")),
        )
        if not selected:
            return
        Path(selected).write_text("\n".join(self._log_lines) + "\n", encoding="utf-8")
        self._append_log(f"Đã xuất log: {selected}")


def main() -> int:
    root = tk.Tk()
    TrinityDemoApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
