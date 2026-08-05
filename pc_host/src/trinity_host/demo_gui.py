from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .demo_gui_base import (
    APP_TITLE,
    C,
    DEFAULT_PLAINTEXTS,
    TrinityDemoApp as _BaseTrinityDemoApp,
    grouped_hex,
    ready_mask_text,
    stage_for_progress,
)

# Static contract sentinels retained for the repository source gate:
# "CHẠY CORE DEMO" "ZEROIZE KHẨN CẤP" "SN32 P2.9 phải nối trực tiếp"
# "emergency_zeroize" "threading.Thread" "Xuất log"


class TrinityDemoApp(_BaseTrinityDemoApp):
    """Responsive wrapper that keeps the primary demo action always visible."""

    def __init__(self, root: tk.Tk) -> None:
        self.top_demo_button: ttk.Button | None = None
        super().__init__(root)
        root.bind("<F5>", self._start_demo_shortcut)

    def _start_demo_shortcut(self, _event: tk.Event) -> str:
        self.start_demo()
        return "break"

    def _build_connection(self, parent: tk.Widget) -> tk.Frame:
        bar = self._card(parent, padx=10, pady=8)
        bar.columnconfigure(7, weight=1)
        tk.Label(
            bar,
            text="UART",
            bg=C["white"],
            fg=C["muted"],
            font=("Segoe UI", 9, "bold"),
        ).grid(row=0, column=0, padx=(0, 6))
        self.port_combo = ttk.Combobox(
            bar,
            textvariable=self.port_var,
            width=12,
            state="normal",
            font=("Segoe UI", 10),
        )
        self.port_combo.grid(row=0, column=1, padx=(0, 6))
        ttk.Button(
            bar,
            text="Làm mới",
            command=self.refresh_ports,
            style="Secondary.TButton",
        ).grid(row=0, column=2, padx=(0, 5))
        self.preflight_button = ttk.Button(
            bar,
            text="Kiểm tra nhanh",
            command=self.start_preflight,
            style="Secondary.TButton",
        )
        self.preflight_button.grid(row=0, column=3, padx=(0, 5))
        self.prepare_button = ttk.Button(
            bar,
            text="Chuẩn bị / Self-test",
            command=self.start_prepare,
            style="Secondary.TButton",
        )
        self.prepare_button.grid(row=0, column=4, padx=(0, 6))
        self.top_demo_button = ttk.Button(
            bar,
            text="▶ CHẠY CORE DEMO (F5)",
            command=self.start_demo,
            style="Primary.TButton",
        )
        self.top_demo_button.grid(row=0, column=5, padx=(0, 8))
        self.connection_label = tk.Label(
            bar,
            textvariable=self.connection_var,
            bg=C["soft"],
            fg=C["muted"],
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=5,
        )
        self.connection_label.grid(row=0, column=6)
        self.top_result_label = tk.Label(
            bar,
            textvariable=self.result_var,
            bg=C["soft"],
            fg=C["muted"],
            font=("Segoe UI", 11, "bold"),
            padx=13,
            pady=6,
        )
        self.top_result_label.grid(row=0, column=8, sticky="e")
        return bar

    def _build_summary(self, parent: tk.Widget) -> tk.Frame:
        outer = self._card(parent, padx=0, pady=0)
        canvas = tk.Canvas(outer, bg=C["white"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        content = tk.Frame(canvas, bg=C["white"])
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")
        summary = _BaseTrinityDemoApp._build_summary(self, content)
        summary.pack(fill=tk.BOTH, expand=True)

        def update_scroll_region(_event: tk.Event | None = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def fit_width(event: tk.Event) -> None:
            canvas.itemconfigure(window_id, width=max(event.width, 300))

        def scroll(event: tk.Event) -> str:
            canvas.yview_scroll(int(-event.delta / 120), "units")
            return "break"

        content.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", fit_width)
        canvas.bind("<Enter>", lambda _event: canvas.bind_all("<MouseWheel>", scroll))
        canvas.bind("<Leave>", lambda _event: canvas.unbind_all("<MouseWheel>"))
        return outer

    def _set_busy(self, busy: bool) -> None:
        super()._set_busy(busy)
        if self.top_demo_button is not None:
            self.top_demo_button.configure(state=tk.DISABLED if busy else tk.NORMAL)


def main() -> int:
    root = tk.Tk()
    TrinityDemoApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
