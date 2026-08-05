from __future__ import annotations

from datetime import datetime
from pathlib import Path
import queue
import threading
import time
import traceback
from typing import Final

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
from .protocol import SystemState
from .serial_client import Sn32QualificationResult, TrinitySerialClient


APP_TITLE: Final[str] = "Trinity — FPGA/PQC Secure Telemetry Demo"
SCOPE_TEXT: Final[str] = "CORE DEMO • Tiny 1P5 chưa thuộc phạm vi"

C: Final[dict[str, str]] = {
    "navy": "#0F2747",
    "blue": "#1F6FEB",
    "blue_dark": "#1158C7",
    "green": "#1A7F37",
    "green_soft": "#DAFBE1",
    "red": "#CF222E",
    "red_soft": "#FFEBE9",
    "amber": "#9A6700",
    "amber_soft": "#FFF8C5",
    "text": "#24292F",
    "muted": "#57606A",
    "border": "#D0D7DE",
    "soft": "#EAEEF2",
    "bg": "#F6F8FA",
    "white": "#FFFFFF",
}

STAGES: Final[tuple[tuple[str, str, str], ...]] = (
    ("preflight", "1. Kiểm tra hệ thống", "Nhận dạng SN32, P1, P2 và xác nhận dual-SPI."),
    ("keygen", "2. Sinh khóa hậu lượng tử", "SN32 sinh cặp khóa ML-KEM-512 low-RAM."),
    ("session", "3. Thiết lập khóa phiên", "Encaps/Decaps, KDF và đồng bộ session P1/P2."),
    ("transmit", "4. Mã hóa và truyền", "P1 mã hóa Ascon-AEAD128 rồi phát frame UART."),
    ("verify", "5. Xác thực tại P2", "P2 kiểm tra tag, giải mã và trả plaintext xác thực."),
    ("zeroize", "6. Zeroize và liveness", "Xóa khóa/session và kiểm tra PING cuối."),
)

PROGRESS_PREFIXES: Final[tuple[tuple[str, str], ...]] = (
    ("Kiểm tra SN32", "preflight"),
    ("Sinh cặp khóa", "keygen"),
    ("Encaps/Decaps", "session"),
    ("P1 mã hóa", "transmit"),
    ("Đọc lại kết quả", "verify"),
    ("Zeroize", "zeroize"),
    ("Dọn trạng thái", "zeroize"),
)

FLOW: Final[tuple[tuple[str, str, str], ...]] = (
    ("pc", "PC HOST", "Plaintext 24 byte"),
    ("sn32", "SN32F407", "ML-KEM • KDF • Control"),
    ("p1", "PRIMER #1", "Ascon Encrypt"),
    ("uart", "UART", "Ciphertext + Tag"),
    ("p2", "PRIMER #2", "Verify + Decrypt"),
    ("result", "KẾT QUẢ", "Authenticated plaintext"),
)

STAGE_NODES: Final[dict[str, tuple[str, ...]]] = {
    "preflight": ("pc", "sn32", "p1", "p2"),
    "keygen": ("sn32",),
    "session": ("sn32", "p1", "p2"),
    "transmit": ("p1", "uart", "p2"),
    "verify": ("p2", "sn32", "result"),
    "zeroize": tuple(item[0] for item in FLOW),
}

STAGE_EXPLANATIONS: Final[dict[str, str]] = {
    "preflight": "SN32 đang kiểm tra identity và giao tiếp dual-SPI với cả hai Primer.",
    "keygen": "ML-KEM-512 tạo nền tảng trao đổi bí mật an toàn trước nguy cơ lượng tử.",
    "session": "SN32 thực hiện Encaps/Decaps, KDF và kích hoạt cùng session trên P1/P2.",
    "transmit": "P1 tạo ciphertext + authentication tag bằng Ascon-AEAD128 rồi phát UART.",
    "verify": "P2 chỉ trả plaintext khi tag hợp lệ, session đúng và sequence không replay.",
    "zeroize": "Vật liệu khóa/session được xóa; PING cuối chứng minh SN32 vẫn hoạt động.",
}


def stage_for_progress(message: str) -> str | None:
    for prefix, stage_id in PROGRESS_PREFIXES:
        if message.startswith(prefix):
            return stage_id
    return None


def grouped_hex(value: bytes | str, *, group_bytes: int = 4) -> str:
    raw = value.hex().upper() if isinstance(value, bytes) else value.replace(" ", "").upper()
    width = max(1, group_bytes) * 2
    return " ".join(raw[i:i + width] for i in range(0, len(raw), width))


def ready_mask_text(mask: int) -> str:
    names = []
    for bit, name in ((0x01, "SN32"), (0x02, "P1"), (0x04, "P2"), (0x08, "Tiny")):
        if mask & bit:
            names.append(name)
    return " • ".join(names) if names else "KHÔNG CÓ ENDPOINT"


class TrinityDemoApp:
    """Presentation-first dashboard for the SN32/P1/P2 no-Tiny core demo."""

    POLL_MS = 75

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title(APP_TITLE)
        root.geometry("1360x840")
        root.minsize(1080, 700)
        root.configure(bg=C["bg"])

        self._queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._worker: threading.Thread | None = None
        self._log_lines: list[str] = []
        self._stage_state = {stage_id: "waiting" for stage_id, _t, _d in STAGES}
        self._stage_started: dict[str, float] = {}
        self._stage_elapsed: dict[str, float] = {}
        self._current_stage: str | None = None
        self._flow_active: set[str] = set()
        self._flow_done: set[str] = set()
        self._operation_started: float | None = None

        self.port_var = tk.StringVar(value="COM3")
        self.payload_var = tk.StringVar(value=DEFAULT_PLAINTEXTS[0].hex().upper())
        self.result_var = tk.StringVar(value="CHƯA CHẠY")
        self.connection_var = tk.StringVar(value="CHƯA KIỂM TRA")
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_text_var = tk.StringVar(value="Sẵn sàng trình diễn")
        self.explanation_var = tk.StringVar(
            value="Demo chỉ PASS khi P2 trả đúng plaintext đã xác thực byte-exact."
        )
        self.sn32_var = tk.StringVar(value="—")
        self.p1_var = tk.StringVar(value="—")
        self.p2_var = tk.StringVar(value="—")
        self.state_var = tk.StringVar(value="—")
        self.ready_var = tk.StringVar(value="—")
        self.session_var = tk.StringVar(value="—")
        self.sequence_var = tk.StringVar(value="—")
        self.uptime_var = tk.StringVar(value="—")
        self.input_var = tk.StringVar(value=grouped_hex(DEFAULT_PLAINTEXTS[0]))
        self.output_var = tk.StringVar(value="—")
        self.match_var = tk.StringVar(value="CHƯA CÓ KẾT QUẢ")
        self.duration_var = tk.StringVar(value="—")

        self._configure_styles()
        self._build_ui()
        self.refresh_ports()
        root.after(self.POLL_MS, self._drain_queue)

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("App.TFrame", background=C["bg"])
        style.configure("Card.TFrame", background=C["white"])
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 9),
                        background=C["blue"], foreground=C["white"])
        style.map("Primary.TButton", background=[("active", C["blue_dark"]),
                                                  ("disabled", C["border"])])
        style.configure("Secondary.TButton", font=("Segoe UI", 9, "bold"), padding=(10, 7))
        style.configure("Danger.TButton", font=("Segoe UI", 9, "bold"), padding=(10, 7),
                        background=C["red"], foreground=C["white"])
        style.map("Danger.TButton", background=[("active", "#A40E26"),
                                                 ("disabled", C["border"])])
        style.configure("Demo.Horizontal.TProgressbar", troughcolor=C["soft"],
                        background=C["blue"], thickness=12)
        style.configure("Treeview", rowheight=46, font=("Segoe UI", 9),
                        background=C["white"], fieldbackground=C["white"])
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=(16, 8))

    def _card(self, parent: tk.Widget, *, padx: int = 12, pady: int = 10) -> tk.Frame:
        return tk.Frame(parent, bg=C["white"], highlightbackground=C["border"],
                        highlightthickness=1, padx=padx, pady=pady)

    def _title(self, parent: tk.Widget, title: str, subtitle: str = "") -> None:
        tk.Label(parent, text=title, bg=C["white"], fg=C["text"],
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")
        if subtitle:
            tk.Label(parent, text=subtitle, bg=C["white"], fg=C["muted"],
                     font=("Segoe UI", 8), justify="left", wraplength=920).pack(
                         anchor="w", pady=(2, 7))

    def _build_ui(self) -> None:
        self._build_header()
        shell = ttk.Frame(self.root, style="App.TFrame", padding=(14, 10, 14, 14))
        shell.pack(fill=tk.BOTH, expand=True)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(1, weight=1)
        self._build_connection(shell).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        tabs = ttk.Notebook(shell)
        tabs.grid(row=1, column=0, sticky="nsew")
        demo_tab = ttk.Frame(tabs, style="App.TFrame", padding=(0, 8, 0, 0))
        log_tab = ttk.Frame(tabs, style="App.TFrame", padding=(0, 8, 0, 0))
        tabs.add(demo_tab, text="TRÌNH DIỄN")
        tabs.add(log_tab, text="NHẬT KÝ KỸ THUẬT")
        self._build_demo_tab(demo_tab)
        self._build_log_tab(log_tab)

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=C["navy"], padx=20, pady=13)
        header.pack(fill=tk.X)
        header.columnconfigure(0, weight=1)
        left = tk.Frame(header, bg=C["navy"])
        left.grid(row=0, column=0, sticky="w")
        tk.Label(left, text="FPGA–PQC SECURE TELEMETRY", bg=C["navy"], fg=C["white"],
                 font=("Segoe UI", 20, "bold")).pack(anchor="w")
        tk.Label(left, text="ML-KEM-512 → KDF → Ascon-AEAD128 • Hardware end-to-end demo",
                 bg=C["navy"], fg="#C9D8EC", font=("Segoe UI", 10)).pack(anchor="w")
        tk.Label(header, text=SCOPE_TEXT, bg=C["amber_soft"], fg=C["amber"],
                 font=("Segoe UI", 9, "bold"), padx=11, pady=6).grid(row=0, column=1)

    def _build_connection(self, parent: tk.Widget) -> tk.Frame:
        bar = self._card(parent, padx=10, pady=8)
        bar.columnconfigure(6, weight=1)
        tk.Label(bar, text="UART", bg=C["white"], fg=C["muted"],
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=0, padx=(0, 6))
        self.port_combo = ttk.Combobox(bar, textvariable=self.port_var, width=13,
                                      state="normal", font=("Segoe UI", 10))
        self.port_combo.grid(row=0, column=1, padx=(0, 6))
        ttk.Button(bar, text="Làm mới", command=self.refresh_ports,
                   style="Secondary.TButton").grid(row=0, column=2, padx=(0, 5))
        self.preflight_button = ttk.Button(bar, text="Kiểm tra nhanh",
                                           command=self.start_preflight,
                                           style="Secondary.TButton")
        self.preflight_button.grid(row=0, column=3, padx=(0, 5))
        self.prepare_button = ttk.Button(bar, text="Chuẩn bị / Self-test",
                                         command=self.start_prepare,
                                         style="Secondary.TButton")
        self.prepare_button.grid(row=0, column=4, padx=(0, 10))
        self.connection_label = tk.Label(bar, textvariable=self.connection_var,
                                         bg=C["soft"], fg=C["muted"],
                                         font=("Segoe UI", 9, "bold"), padx=10, pady=5)
        self.connection_label.grid(row=0, column=5)
        self.top_result_label = tk.Label(bar, textvariable=self.result_var, bg=C["soft"],
                                         fg=C["muted"], font=("Segoe UI", 11, "bold"),
                                         padx=13, pady=6)
        self.top_result_label.grid(row=0, column=7, sticky="e")
        return bar

    def _build_demo_tab(self, tab: ttk.Frame) -> None:
        tab.columnconfigure(0, weight=7)
        tab.columnconfigure(1, weight=3)
        tab.rowconfigure(1, weight=1)
        self._build_flow(tab).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self._build_timeline(tab).grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        self._build_summary(tab).grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        self._build_algorithms(tab).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    def _build_flow(self, parent: tk.Widget) -> tk.Frame:
        card = self._card(parent, padx=10, pady=8)
        self._title(card, "ĐƯỜNG ĐI DỮ LIỆU",
                    "Khối xanh dương đang hoạt động; khối xanh lá đã hoàn thành.")
        self.flow_canvas = tk.Canvas(card, height=126, bg=C["white"], highlightthickness=0)
        self.flow_canvas.pack(fill=tk.X)
        self.flow_canvas.bind("<Configure>", lambda _e: self._draw_flow())
        tk.Label(card, text=("Cấu hình no-Tiny: SN32 P2.9 phải nối trực tiếp tới "
                             "T12/SECURE_ENABLE của P1/P2; P1 J2-11 nối P2 J2-11."),
                 bg=C["amber_soft"], fg=C["amber"], font=("Segoe UI", 8, "bold"),
                 padx=8, pady=5, justify="left", wraplength=1100).pack(fill=tk.X, pady=(4, 0))
        return card

    def _draw_flow(self) -> None:
        canvas = self.flow_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 820)
        n = len(FLOW)
        gap, margin = 12, 14
        node_w = min(150, max(108, (width - 2 * margin - gap * (n - 1)) / n))
        total = n * node_w + (n - 1) * gap
        start = max(margin, (width - total) / 2)
        boxes: list[tuple[float, float, float, float]] = []
        for idx, (node_id, title, subtitle) in enumerate(FLOW):
            x1 = start + idx * (node_w + gap)
            box = (x1, 26, x1 + node_w, 108)
            boxes.append(box)
            if node_id in self._flow_active:
                fill, outline, fg = "#DDF4FF", C["blue"], C["blue_dark"]
            elif node_id in self._flow_done:
                fill, outline, fg = C["green_soft"], C["green"], C["green"]
            else:
                fill, outline, fg = C["bg"], C["border"], C["text"]
            canvas.create_rectangle(*box, fill=fill, outline=outline, width=2)
            canvas.create_text((box[0] + box[2]) / 2, 51, text=title, fill=fg,
                               font=("Segoe UI", 9, "bold"), width=node_w - 10)
            canvas.create_text((box[0] + box[2]) / 2, 80, text=subtitle, fill=C["muted"],
                               font=("Segoe UI", 7), width=node_w - 10)
        for left, right in zip(boxes, boxes[1:]):
            canvas.create_line(left[2] + 2, 67, right[0] - 2, 67, fill="#8C959F",
                               width=2, arrow=tk.LAST, arrowshape=(8, 10, 4))
        canvas.create_text(width / 2, 10,
                           text="PC → SN32 → P1 Encrypt → UART → P2 Verify/Decrypt → PC",
                           fill=C["muted"], font=("Segoe UI", 8, "bold"))

    def _build_timeline(self, parent: tk.Widget) -> tk.Frame:
        card = self._card(parent)
        top = tk.Frame(card, bg=C["white"])
        top.pack(fill=tk.X)
        tk.Label(top, text="TIẾN TRÌNH DEMO", bg=C["white"], fg=C["text"],
                 font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT)
        tk.Label(top, textvariable=self.duration_var, bg=C["white"], fg=C["muted"],
                 font=("Segoe UI", 8, "bold")).pack(side=tk.RIGHT)

        self.stage_tree = ttk.Treeview(card, columns=("status", "stage", "detail", "time"),
                                       show="headings", selectmode="none", height=6)
        self.stage_tree.heading("status", text="TRẠNG THÁI")
        self.stage_tree.heading("stage", text="BƯỚC")
        self.stage_tree.heading("detail", text="Ý NGHĨA")
        self.stage_tree.heading("time", text="THỜI GIAN")
        self.stage_tree.column("status", width=95, anchor="center", stretch=False)
        self.stage_tree.column("stage", width=210, anchor="w", stretch=False)
        self.stage_tree.column("detail", width=430, anchor="w")
        self.stage_tree.column("time", width=75, anchor="e", stretch=False)
        self.stage_tree.pack(fill=tk.BOTH, expand=True, pady=(8, 8))
        self.stage_tree.tag_configure("waiting", foreground=C["muted"])
        self.stage_tree.tag_configure("running", background="#DDF4FF", foreground=C["blue_dark"])
        self.stage_tree.tag_configure("pass", background=C["green_soft"], foreground=C["green"])
        self.stage_tree.tag_configure("fail", background=C["red_soft"], foreground=C["red"])
        for stage_id, title, detail in STAGES:
            self.stage_tree.insert("", tk.END, iid=stage_id,
                                   values=("CHỜ", title, detail, ""), tags=("waiting",))

        tk.Label(card, textvariable=self.explanation_var, bg=C["bg"], fg=C["text"],
                 font=("Segoe UI", 9, "bold"), padx=10, pady=8, justify="left",
                 wraplength=760).pack(fill=tk.X)
        return card

    def _build_summary(self, parent: tk.Widget) -> tk.Frame:
        card = self._card(parent)
        self._title(card, "KẾT QUẢ TRÌNH DIỄN")
        self.big_result_label = tk.Label(card, textvariable=self.result_var, bg=C["soft"],
                                         fg=C["muted"], font=("Segoe UI", 17, "bold"),
                                         padx=10, pady=10)
        self.big_result_label.pack(fill=tk.X)
        ttk.Progressbar(card, variable=self.progress_var, maximum=100,
                        style="Demo.Horizontal.TProgressbar").pack(fill=tk.X, pady=(8, 4))
        tk.Label(card, textvariable=self.progress_text_var, bg=C["white"], fg=C["text"],
                 font=("Segoe UI", 8, "bold"), justify="left", wraplength=330).pack(anchor="w")

        info = tk.Frame(card, bg=C["white"])
        info.pack(fill=tk.X, pady=8)
        info.columnconfigure(1, weight=1)
        for row, (label, variable) in enumerate((
            ("SN32", self.sn32_var), ("Primer #1", self.p1_var), ("Primer #2", self.p2_var),
            ("System state", self.state_var), ("Endpoint ready", self.ready_var),
            ("Session ID", self.session_var), ("Sequence", self.sequence_var),
            ("SN32 uptime", self.uptime_var),
        )):
            tk.Label(info, text=label, bg=C["white"], fg=C["muted"],
                     font=("Segoe UI", 8, "bold")).grid(row=row, column=0, sticky="w", pady=1)
            tk.Label(info, textvariable=variable, bg=C["white"], fg=C["text"],
                     font=("Consolas", 8, "bold"), justify="right").grid(
                         row=row, column=1, sticky="e", pady=1)

        tk.Label(card, text="PLAINTEXT GỬI VÀO", bg=C["white"], fg=C["muted"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(card, textvariable=self.input_var, bg=C["bg"], fg=C["text"],
                 font=("Consolas", 8, "bold"), padx=7, pady=6, wraplength=330,
                 justify="left").pack(fill=tk.X, pady=(2, 5))
        tk.Label(card, text="PLAINTEXT P2 ĐÃ XÁC THỰC", bg=C["white"], fg=C["muted"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(card, textvariable=self.output_var, bg=C["bg"], fg=C["text"],
                 font=("Consolas", 8, "bold"), padx=7, pady=6, wraplength=330,
                 justify="left").pack(fill=tk.X, pady=(2, 5))
        self.match_label = tk.Label(card, textvariable=self.match_var, bg=C["soft"],
                                    fg=C["muted"], font=("Segoe UI", 9, "bold"),
                                    padx=8, pady=7)
        self.match_label.pack(fill=tk.X)

        tk.Label(card, text="Payload 24 byte (48 hex)", bg=C["white"], fg=C["muted"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(8, 0))
        entry = ttk.Entry(card, textvariable=self.payload_var, font=("Consolas", 9))
        entry.pack(fill=tk.X, pady=(3, 5))
        entry.bind("<KeyRelease>", lambda _e: self._preview_payload())
        presets = ttk.Frame(card, style="Card.TFrame")
        presets.pack(fill=tk.X, pady=(0, 7))
        ttk.Button(presets, text="Mẫu 00…17", command=lambda: self._set_payload(DEFAULT_PLAINTEXTS[0]),
                   style="Secondary.TButton").pack(side=tk.LEFT)
        ttk.Button(presets, text="Mẫu 80…97", command=lambda: self._set_payload(DEFAULT_PLAINTEXTS[1]),
                   style="Secondary.TButton").pack(side=tk.LEFT, padx=5)

        self.demo_button = ttk.Button(card, text="CHẠY CORE DEMO BẢO MẬT",
                                      command=self.start_demo, style="Primary.TButton")
        self.demo_button.pack(fill=tk.X, pady=(0, 5))
        self.zeroize_button = ttk.Button(card, text="ZEROIZE KHẨN CẤP",
                                         command=self.start_zeroize, style="Danger.TButton")
        self.zeroize_button.pack(fill=tk.X, pady=(0, 5))
        tools = ttk.Frame(card, style="Card.TFrame")
        tools.pack(fill=tk.X)
        ttk.Button(tools, text="Sao chép kết quả", command=self.copy_result,
                   style="Secondary.TButton").pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(tools, text="Xuất báo cáo", command=self.export_report,
                   style="Secondary.TButton").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        return card

    def _build_algorithms(self, parent: tk.Widget) -> tk.Frame:
        card = self._card(parent, padx=10, pady=8)
        grid = tk.Frame(card, bg=C["white"])
        grid.pack(fill=tk.X)
        for col, (name, text) in enumerate((
            ("ML-KEM-512", "Thiết lập bí mật dùng chung hậu lượng tử."),
            ("KDF", "Dẫn xuất Ascon key, nonce prefix và session ID."),
            ("Ascon-AEAD128", "Bảo mật nội dung và phát hiện sửa đổi/tag giả."),
            ("Zeroize", "Xóa khóa/session sau mỗi lượt demo."),
        )):
            grid.columnconfigure(col, weight=1)
            box = tk.Frame(grid, bg=C["bg"], highlightbackground=C["border"],
                           highlightthickness=1, padx=8, pady=6)
            box.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 5, 0))
            tk.Label(box, text=name, bg=C["bg"], fg=C["navy"],
                     font=("Segoe UI", 9, "bold")).pack(anchor="w")
            tk.Label(box, text=text, bg=C["bg"], fg=C["muted"], font=("Segoe UI", 8),
                     justify="left", wraplength=250).pack(anchor="w")
        return card

    def _build_log_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        head = self._card(parent)
        head.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self._title(head, "NHẬT KÝ CHI TIẾT",
                    "Tab này giữ toàn bộ tiến trình và traceback; màn hình trình diễn chỉ hiện kết luận dễ hiểu.")
        buttons = ttk.Frame(head, style="Card.TFrame")
        buttons.pack(fill=tk.X)
        ttk.Button(buttons, text="Xóa nhật ký", command=self.clear_log,
                   style="Secondary.TButton").pack(side=tk.LEFT)
        ttk.Button(buttons, text="Xuất log / báo cáo đầy đủ", command=self.export_report,
                   style="Secondary.TButton").pack(side=tk.RIGHT)

        body = self._card(parent, padx=5, pady=5)
        body.grid(row=1, column=0, sticky="nsew")
        self.log_text = tk.Text(body, wrap=tk.WORD, font=("Consolas", 9), bg="#0D1117",
                                fg="#C9D1D9", relief=tk.FLAT, state=tk.DISABLED)
        scroll = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.tag_configure("pass", foreground="#56D364")
        self.log_text.tag_configure("fail", foreground="#FF7B72")
        self.log_text.tag_configure("step", foreground="#79C0FF")
        self.log_text.tag_configure("muted", foreground="#8B949E")

    def refresh_ports(self) -> None:
        ports = [] if list_ports is None else [p.device for p in list_ports.comports()]
        self.port_combo["values"] = ports
        if ports and self.port_var.get() not in ports:
            self.port_var.set(ports[0])
        if ports:
            self.connection_var.set("CÓ CỔNG UART")
            self._paint_connection("idle")
        self._log("Đã làm mới danh sách cổng UART", "muted")

    def _set_payload(self, payload: bytes) -> None:
        self.payload_var.set(payload.hex().upper())
        self.input_var.set(grouped_hex(payload))

    def _preview_payload(self) -> None:
        try:
            self.input_var.set(grouped_hex(parse_plaintext_hex(self.payload_var.get())))
        except ValueError:
            self.input_var.set("Payload chưa hợp lệ — cần đúng 24 byte / 48 hex")

    def _open_client(self) -> TrinitySerialClient:
        port = self.port_var.get().strip()
        if not port:
            raise ValueError("Chưa chọn cổng UART")
        return TrinitySerialClient(port)

    def _set_busy(self, busy: bool) -> None:
        state = tk.DISABLED if busy else tk.NORMAL
        for button in (self.demo_button, self.preflight_button,
                       self.prepare_button, self.zeroize_button):
            button.configure(state=state)

    def _start_worker(self, name: str, target) -> None:
        if self._worker is not None and self._worker.is_alive():
            messagebox.showwarning("Trinity", "Một thao tác khác đang chạy")
            return
        self._operation_started = time.perf_counter()
        self.duration_var.set("Đang đo thời gian…")
        self.result_var.set("ĐANG CHẠY")
        self._paint_result("running")
        self._set_busy(True)
        self._worker = threading.Thread(target=self._worker_entry,
                                        args=(name, target), daemon=True)
        self._worker.start()

    def _worker_entry(self, name: str, target) -> None:
        try:
            self._queue.put(("success", (name, target())))
        except Exception as exc:  # pragma: no cover - hardware-dependent
            self._queue.put(("failure", (name, exc, traceback.format_exc())))

    def start_preflight(self) -> None:
        self.progress_var.set(10)
        self.progress_text_var.set("Đang đọc PING, identity và system status…")
        self.explanation_var.set("Kiểm tra nhanh chỉ xác nhận PC ↔ SN32 và snapshot hiện tại.")

        def work():
            with self._open_client() as client:
                return client.ping(), client.get_system_info(), client.get_system_status()

        self._start_worker("preflight", work)

    def start_prepare(self) -> None:
        self._reset_stages()
        self.progress_var.set(5)
        self.progress_text_var.set("Đang chạy live SPI và KAT P1/P2…")
        self._activate_stage("preflight")

        def work() -> Sn32QualificationResult:
            with self._open_client() as client:
                return client.run_sn32_hardware_qualification(
                    timeout=30.0, poll_interval=0.05, liveness_iterations=2)

        self._start_worker("prepare", work)

    def start_demo(self) -> None:
        try:
            plaintext = parse_plaintext_hex(self.payload_var.get())
        except ValueError as exc:
            messagebox.showerror("Payload không hợp lệ", str(exc))
            return
        self._reset_stages()
        self.input_var.set(grouped_hex(plaintext))
        self.output_var.set("Đang chờ authenticated result từ Primer #2…")
        self.match_var.set("ĐANG CHỜ XÁC THỰC")
        self._paint_match("waiting")
        self.progress_var.set(0)
        self.progress_text_var.set("Bắt đầu core demo")

        def on_progress(message: str, percent: int | None) -> None:
            self._queue.put(("progress", (message, percent)))

        def work() -> CoreDemoResult:
            with self._open_client() as client:
                return run_core_demo(client, plaintext=plaintext, timeout=120.0,
                                     on_progress=on_progress)

        self._start_worker("demo", work)

    def start_zeroize(self) -> None:
        self.progress_var.set(15)
        self.progress_text_var.set("Đang zeroize toàn hệ thống…")
        self._activate_stage("zeroize")

        def work():
            with self._open_client() as client:
                result = emergency_zeroize(client, timeout=30.0)
                return result, client.get_system_status(), client.ping()

        self._start_worker("zeroize", work)

    def _drain_queue(self) -> None:
        while True:
            try:
                kind, payload = self._queue.get_nowait()
            except queue.Empty:
                break
            if kind == "progress":
                message, percent = payload
                message = str(message)
                self.progress_text_var.set(message)
                if percent is not None:
                    self.progress_var.set(float(percent))
                stage_id = stage_for_progress(message)
                if stage_id:
                    self._activate_stage(stage_id)
                    self.explanation_var.set(STAGE_EXPLANATIONS[stage_id])
                self._log(message, "step")
            elif kind == "success":
                name, result = payload
                self._handle_success(str(name), result)
                self._set_busy(False)
            else:
                name, exc, trace = payload
                self._handle_failure(str(name), exc, str(trace))
                self._set_busy(False)
        self.root.after(self.POLL_MS, self._drain_queue)

    def _handle_success(self, name: str, result: object) -> None:
        if name == "preflight":
            uptime, info, status = result
            self._apply_identity(info)
            self._apply_status(status)
            self.uptime_var.set(f"{uptime:,} ms")
            self.connection_var.set("KẾT NỐI TỐT")
            self.result_var.set("PREFLIGHT PASS")
            self.progress_text_var.set("PC ↔ SN32 phản hồi tốt; identity và status đã đọc thành công.")
            self._log(f"PING PASS, uptime_ms={uptime}", "pass")
        elif name == "prepare":
            qualification = result
            self._apply_identity(qualification.dual_spi.info)
            self._apply_status(qualification.final_status)
            self.uptime_var.set(f"{qualification.final_uptime_ms:,} ms")
            self.connection_var.set("P1/P2 SẴN SÀNG")
            self.result_var.set("SELF-TEST PASS")
            self.progress_text_var.set("KAT P1/P2 PASS — hệ thống sẵn sàng cho phiên mới.")
            self._finish_stage("pass")
            self._log("SN32/P1/P2 SELF-TEST PASS", "pass")
        elif name == "demo":
            demo = result
            self._apply_identity(demo.info)
            self._apply_status(demo.status_final)
            self.session_var.set(f"0x{demo.session.session_id:08X}")
            self.sequence_var.set(str(demo.telemetry.sequence))
            self.uptime_var.set(f"{demo.final_uptime_ms:,} ms")
            self.output_var.set(grouped_hex(demo.telemetry.plaintext))
            self.match_var.set("KHỚP BYTE-EXACT • 24/24 BYTE • TAG HỢP LỆ")
            self._paint_match("pass")
            self.connection_var.set("HỆ THỐNG ỔN ĐỊNH")
            self.result_var.set("CORE DEMO PASS")
            if demo.status_final.system_state == SystemState.SELF_TEST_REQUIRED:
                self.progress_text_var.set(
                    "PASS — authenticated telemetry hoàn tất; zeroize sạch; cần self-test cho lượt mới.")
            else:
                self.progress_text_var.set("PASS — authenticated telemetry và zeroize hoàn tất.")
            self.explanation_var.set(
                "P2 đã xác thực tag Ascon, giải mã thành công và trả đúng plaintext ban đầu.")
            self._finish_stage("pass")
            for stage_id, _t, _d in STAGES:
                if self._stage_state[stage_id] == "waiting":
                    self._stage_state[stage_id] = "pass"
                    self._paint_stage(stage_id)
            self._flow_done = {node_id for node_id, _t, _s in FLOW}
            self._flow_active.clear()
            self._draw_flow()
            self._log("Authenticated plaintext=" + demo.telemetry.plaintext.hex().upper(), "pass")
            self._log(f"Final PING uptime_ms={demo.final_uptime_ms}", "pass")
        else:
            _txid, status, uptime = result
            self._apply_status(status)
            self.uptime_var.set(f"{uptime:,} ms")
            self.connection_var.set("ZEROIZE HOÀN TẤT")
            self.result_var.set("ZEROIZE PASS")
            self.progress_text_var.set("Zeroize PASS — session/sequence đã xóa; SN32 vẫn PING.")
            self._finish_stage("pass")
            self._log(f"EMERGENCY ZEROIZE PASS, final uptime_ms={uptime}", "pass")
        self.progress_var.set(100)
        self._paint_connection("pass")
        self._paint_result("pass")
        self._update_duration()

    def _handle_failure(self, name: str, exc: object, trace: str) -> None:
        self._finish_stage("fail")
        self.result_var.set("DEMO FAIL" if name == "demo" else "THAO TÁC FAIL")
        self.connection_var.set("CÓ LỖI")
        self.progress_text_var.set(str(exc))
        self.explanation_var.set("Hệ thống dừng fail-closed. Xem tab NHẬT KÝ KỸ THUẬT.")
        self._paint_connection("fail")
        self._paint_result("fail")
        self._log(f"{name.upper()} FAIL: {exc}", "fail")
        self._log(trace, "fail")
        self._update_duration()
        messagebox.showerror("Trinity", str(exc))

    def _apply_identity(self, info) -> None:
        self.sn32_var.set(f"v{info.architecture_major}.{info.architecture_minor}."
                          f"{info.architecture_patch} / 0x{info.sn32_build_id:08X}")
        self.p1_var.set(f"0x{info.primer1_build_id:08X}")
        self.p2_var.set(f"0x{info.primer2_build_id:08X}")

    def _apply_status(self, status) -> None:
        self.state_var.set(status.system_state.name)
        self.ready_var.set(ready_mask_text(status.target_ready_mask))
        self.sequence_var.set(str(status.current_sequence))
        if status.session_id:
            self.session_var.set(f"0x{status.session_id:08X}")
        elif self.session_var.get() == "—":
            self.session_var.set("0x00000000")

    def _reset_stages(self) -> None:
        self._stage_state = {stage_id: "waiting" for stage_id, _t, _d in STAGES}
        self._stage_started.clear()
        self._stage_elapsed.clear()
        self._current_stage = None
        self._flow_active.clear()
        self._flow_done.clear()
        for stage_id, _t, _d in STAGES:
            self._paint_stage(stage_id)
        self._draw_flow()

    def _activate_stage(self, stage_id: str) -> None:
        if stage_id not in self._stage_state or self._current_stage == stage_id:
            return
        self._finish_stage("pass")
        self._current_stage = stage_id
        self._stage_state[stage_id] = "running"
        self._stage_started[stage_id] = time.perf_counter()
        self._paint_stage(stage_id)
        order = [item[0] for item in STAGES]
        index = order.index(stage_id)
        self._flow_done = set().union(*(STAGE_NODES[s] for s in order[:index])) if index else set()
        self._flow_active = set(STAGE_NODES[stage_id])
        self._draw_flow()

    def _finish_stage(self, state: str) -> None:
        if self._current_stage is None:
            return
        stage_id = self._current_stage
        if stage_id in self._stage_started:
            self._stage_elapsed[stage_id] = time.perf_counter() - self._stage_started[stage_id]
        self._stage_state[stage_id] = state
        self._paint_stage(stage_id)
        if state == "pass":
            self._flow_done.update(STAGE_NODES[stage_id])
            self._flow_active.clear()
            self._draw_flow()
        self._current_stage = None

    def _paint_stage(self, stage_id: str) -> None:
        state = self._stage_state[stage_id]
        status = {"waiting": "CHỜ", "running": "ĐANG CHẠY", "pass": "PASS", "fail": "FAIL"}[state]
        _sid, title, detail = next(item for item in STAGES if item[0] == stage_id)
        elapsed = self._stage_elapsed.get(stage_id)
        self.stage_tree.item(stage_id,
                             values=(status, title, detail, f"{elapsed:.2f}s" if elapsed else ""),
                             tags=(state,))

    def _paint_result(self, state: str) -> None:
        palette = {"running": ("#DDF4FF", C["blue_dark"]),
                   "pass": (C["green_soft"], C["green"]),
                   "fail": (C["red_soft"], C["red"]),
                   "idle": (C["soft"], C["muted"])}
        bg, fg = palette[state]
        self.top_result_label.configure(bg=bg, fg=fg)
        self.big_result_label.configure(bg=bg, fg=fg)

    def _paint_connection(self, state: str) -> None:
        palette = {"pass": (C["green_soft"], C["green"]),
                   "fail": (C["red_soft"], C["red"]),
                   "idle": (C["soft"], C["muted"])}
        bg, fg = palette[state]
        self.connection_label.configure(bg=bg, fg=fg)

    def _paint_match(self, state: str) -> None:
        palette = {"pass": (C["green_soft"], C["green"]),
                   "fail": (C["red_soft"], C["red"]),
                   "waiting": (C["soft"], C["muted"])}
        bg, fg = palette[state]
        self.match_label.configure(bg=bg, fg=fg)

    def _update_duration(self) -> None:
        if self._operation_started is not None:
            self.duration_var.set(f"Tổng: {time.perf_counter() - self._operation_started:.2f} s")

    def _log(self, message: str, tag: str = "") -> None:
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
        self._log_lines.append(line)
        if hasattr(self, "log_text"):
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, line + "\n", tag)
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)

    def clear_log(self) -> None:
        self._log_lines.clear()
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)
        self._log("Đã xóa nhật ký trên màn hình", "muted")

    def copy_result(self) -> None:
        text = self.output_var.get().replace(" ", "")
        if text == "—" or "Đang chờ" in text:
            messagebox.showinfo("Trinity", "Chưa có authenticated plaintext để sao chép")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update_idletasks()
        self._log("Đã sao chép authenticated plaintext", "muted")

    def _report_text(self) -> str:
        lines = [
            "TRINITY — FPGA/PQC SECURE TELEMETRY DEMO REPORT",
            "=" * 64,
            f"Thời gian: {datetime.now().isoformat(timespec='seconds')}",
            f"Phạm vi: {SCOPE_TEXT}",
            f"UART: {self.port_var.get().strip()}",
            "",
            f"KẾT LUẬN: {self.result_var.get()}",
            f"SN32: {self.sn32_var.get()}",
            f"Primer #1: {self.p1_var.get()}",
            f"Primer #2: {self.p2_var.get()}",
            f"Final state: {self.state_var.get()}",
            f"Endpoint ready: {self.ready_var.get()}",
            f"Session ID: {self.session_var.get()}",
            f"Sequence: {self.sequence_var.get()}",
            f"Input plaintext: {self.input_var.get()}",
            f"Authenticated plaintext: {self.output_var.get()}",
            f"So sánh: {self.match_var.get()}",
            "",
            "CÁC BƯỚC",
            "-" * 64,
        ]
        for stage_id, title, detail in STAGES:
            state = self._stage_state[stage_id].upper()
            elapsed = self._stage_elapsed.get(stage_id)
            suffix = f" ({elapsed:.2f}s)" if elapsed is not None else ""
            lines.extend((f"[{state}]{suffix} {title}", f"  {detail}"))
        lines.extend((
            "", "TUYÊN BỐ PHẠM VI", "-" * 64,
            "PASS chứng minh core path PC → SN32 → P1 → UART → P2 → SN32 → PC.",
            "Tiny 1P5 chưa tham gia nên chưa phải full-system qualification.",
            "", "NHẬT KÝ KỸ THUẬT", "-" * 64, *self._log_lines, "",
        ))
        return "\n".join(lines)

    def export_report(self) -> None:
        filename = filedialog.asksaveasfilename(
            title="Xuất báo cáo Trinity", defaultextension=".txt",
            initialfile="trinity_demo_report_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt",
            filetypes=(("Text", "*.txt"), ("All files", "*.*")))
        if not filename:
            return
        Path(filename).write_text(self._report_text(), encoding="utf-8")
        self._log(f"Đã xuất báo cáo: {filename}", "muted")


def main() -> int:
    root = tk.Tk()
    TrinityDemoApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
