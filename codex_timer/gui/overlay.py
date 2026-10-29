"""Single-line compact desktop floating overlay (HUD Widget)."""
import datetime as dt
import time
import tkinter as tk
from typing import Callable, Optional, Dict, Any


class SingleLineOverlay:
    """Ultra-compact single-line desktop HUD with right-click menu & wheel alpha adjustment."""

    def __init__(self, root: tk.Tk, app_ref: Any):
        self.root = root
        self.app = app_ref
        self.overlay: Optional[tk.Toplevel] = None
        self.pinned = self.app.config.get('overlay_pinned', True)
        self.alpha = float(self.app.config.get('overlay_alpha', 0.94))
        self.pos_x = self.app.config.get('overlay_x', 120)
        self.pos_y = self.app.config.get('overlay_y', 120)
        self.drag_x = 0
        self.drag_y = 0

    def _clamp_and_snap(self, x: int, y: int, snap_dist: int = 16) -> tuple[int, int]:
        """Keep overlay within screen boundaries and apply edge snapping."""
        if not self.overlay:
            return x, y
        screen_w = self.overlay.winfo_screenwidth()
        screen_h = self.overlay.winfo_screenheight()
        w, h = 380, 36
        max_x = max(0, screen_w - w)
        max_y = max(0, screen_h - h - 48)  # Leave room for Windows taskbar

        # Magnetic edge snapping
        if abs(x) < snap_dist:
            x = 0
        elif abs(x - max_x) < snap_dist:
            x = max_x

        if abs(y) < snap_dist:
            y = 0
        elif abs(y - max_y) < snap_dist:
            y = max_y

        # Clamp strictly inside visible desktop area
        x = max(0, min(max_x, x))
        y = max(0, min(max_y, y))
        return x, y

    def show(self) -> None:
        if self.overlay:
            try:
                self.overlay.deiconify()
                self.overlay.lift()
                return
            except Exception:
                self.overlay = None

        self.overlay = tk.Toplevel(self.root)
        self.overlay.overrideredirect(True)
        self.overlay.attributes('-alpha', self.alpha)
        self.overlay.attributes('-topmost', self.pinned)
        self.overlay.configure(bg='#181A1D')
        self.pos_x, self.pos_y = self._clamp_and_snap(self.pos_x, self.pos_y)
        self.overlay.geometry(f'380x36+{self.pos_x}+{self.pos_y}')

        border = tk.Frame(self.overlay, bg='#2F333A', padx=1, pady=1)
        border.pack(fill='both', expand=True)

        main_f = tk.Frame(border, bg='#181A1D', padx=8, pady=2)
        main_f.pack(fill='both', expand=True)

        # 拖拽手柄
        lbl_drag = tk.Label(main_f, text='⋮⋮', font=('Segoe UI', 9), bg='#181A1D', fg='#6B7280', cursor='fleur')
        lbl_drag.pack(side='left', padx=(0, 6))

        # 1. 倒计时
        self.lbl_cd = tk.Label(main_f, text='⏳ --', font=('Consolas', 10, 'bold'), bg='#181A1D', fg='#38BDF8', cursor='fleur')
        self.lbl_cd.pack(side='left', padx=(0, 6))

        sep1 = tk.Label(main_f, text='│', font=('Consolas', 9), bg='#181A1D', fg='#374151')
        sep1.pack(side='left', padx=(0, 6))

        # 2. 短周期额度 (5H / 2H)
        self.lbl_5h = tk.Label(main_f, text='5H: --', font=('Microsoft YaHei UI', 9, 'bold'), bg='#181A1D', fg='#EF4444', cursor='fleur')
        self.lbl_5h.pack(side='left', padx=(0, 6))

        sep2 = tk.Label(main_f, text='│', font=('Consolas', 9), bg='#181A1D', fg='#374151')
        sep2.pack(side='left', padx=(0, 6))

        # 3. 周额度 (Week)
        self.lbl_wk = tk.Label(main_f, text='Week: --', font=('Microsoft YaHei UI', 9, 'bold'), bg='#181A1D', fg='#10B981', cursor='fleur')
        self.lbl_wk.pack(side='left', padx=(0, 6))

        # ✕ 关闭按钮
        btn_close = tk.Label(main_f, text='✕', font=('Microsoft YaHei UI', 9), bg='#181A1D', fg='#9CA3AF', cursor='hand2')
        btn_close.pack(side='right', padx=(4, 0))
        btn_close.bind('<Button-1>', lambda e: self.close())

        # 📌 固定/置顶切换按钮
        self.btn_pin = tk.Label(main_f, text='📌', font=('Segoe UI Emoji', 9), bg='#181A1D',
                                fg='#38BDF8' if self.pinned else '#64748B', cursor='hand2')
        self.btn_pin.pack(side='right', padx=(2, 0))
        self.btn_pin.bind('<Button-1>', lambda e: self.toggle_pin())

        # 绑定拖拽
        all_widgets = [border, main_f, lbl_drag, self.lbl_cd, sep1, self.lbl_5h, sep2, self.lbl_wk]
        for w in all_widgets:
            w.bind('<Button-1>', self._start_move)
            w.bind('<B1-Motion>', self._do_move)
            w.bind('<Button-3>', self._show_context_menu)
            w.bind('<MouseWheel>', self._on_mouse_wheel)

        # 悬停详细提示 (Tooltips)
        self._bind_tooltip(self.lbl_cd, lambda: f"下次发送时间：{self.app.when.get()}")
        self._bind_tooltip(self.lbl_5h, self.app.get_5h_tooltip)
        self._bind_tooltip(self.lbl_wk, self.app.get_wk_tooltip)

        self.update()

    def hide(self) -> None:
        if self.overlay:
            try:
                self.overlay.destroy()
            except Exception:
                pass
            self.overlay = None

    def close(self) -> None:
        self.app.show_overlay.set(False)
        self.hide()
        self.app.config.set('show_overlay', False)

    def is_visible(self) -> bool:
        return self.overlay is not None

    def toggle_pin(self) -> None:
        if not self.overlay:
            return
        self.pinned = not self.pinned
        self.overlay.attributes('-topmost', self.pinned)
        self.btn_pin.configure(fg='#38BDF8' if self.pinned else '#64748B')
        self.app.config.set('overlay_pinned', self.pinned)

    def _start_move(self, e) -> None:
        if self.overlay:
            self.drag_x = e.x_root - self.overlay.winfo_x()
            self.drag_y = e.y_root - self.overlay.winfo_y()

    def _do_move(self, e) -> None:
        if self.overlay:
            raw_x = e.x_root - self.drag_x
            raw_y = e.y_root - self.drag_y
            x, y = self._clamp_and_snap(raw_x, raw_y)
            self.overlay.geometry(f'+{x}+{y}')
            self.pos_x, self.pos_y = x, y
            self.app.config.set('overlay_x', x, auto_save=False)
            self.app.config.set('overlay_y', y, auto_save=True)

    def _on_mouse_wheel(self, e) -> None:
        """Scroll wheel adjusts transparency smoothly (0.40 ~ 1.00)."""
        if not self.overlay:
            return
        delta = 0.04 if e.delta > 0 else -0.04
        self.alpha = max(0.40, min(1.00, round(self.alpha + delta, 2)))
        self.overlay.attributes('-alpha', self.alpha)
        self.app.config.set('overlay_alpha', self.alpha)

    def _show_context_menu(self, e) -> None:
        """Right-click context menu."""
        menu = tk.Menu(self.overlay, tearoff=0, font=('Microsoft YaHei UI', 9))
        menu.add_command(label="⚡ 立即刷新额度", command=self.app.check)
        menu.add_command(label="📋 复制当前额度", command=self._copy_quota_summary)
        menu.add_separator()
        menu.add_command(label="🪟 打开主界面", command=self.app.restore_from_tray)
        menu.add_command(label="📦 隐藏到托盘", command=self.close)
        menu.add_separator()
        menu.add_command(label="❌ 彻底退出", command=self.app.quit_app)
        menu.tk_popup(e.x_root, e.y_root)

    def _copy_quota_summary(self) -> None:
        five_h, weekly = self.app.get_extracted_windows()
        rem_5h = max(0, 100 - five_h.get('usedPercent', 100)) if five_h else 0
        rem_wk = max(0, 100 - weekly.get('usedPercent', 100)) if weekly else 0
        txt = f"Codex 额度: 5H剩余 {rem_5h:g}%, 周额度剩余 {rem_wk:g}%, 下次自动发送: {self.app.when.get()}"
        self.root.clipboard_clear()
        self.root.clipboard_append(txt)
        self.app.log("已复制额度概要到剪贴板。")

    def _bind_tooltip(self, widget, text_func: Callable[[], str]) -> None:
        tip_ref = [None]

        def enter(e):
            if tip_ref[0] or not self.overlay:
                return
            txt = text_func() if callable(text_func) else str(text_func)
            if not txt:
                return
            x = widget.winfo_rootx()
            y = widget.winfo_rooty() + widget.winfo_height() + 5
            tw = tk.Toplevel(self.overlay)
            tw.wm_overrideredirect(True)
            tw.attributes('-topmost', True)
            tw.attributes('-alpha', 0.95)
            tw.wm_geometry(f"+{x}+{y}")
            tk.Label(tw, text=txt, font=('Microsoft YaHei UI', 8), bg='#202227', fg='#E5E7EB',
                     padx=8, pady=4, relief='flat', highlightthickness=1, highlightbackground='#374151').pack()
            tip_ref[0] = tw

        def leave(e):
            if tip_ref[0]:
                try:
                    tip_ref[0].destroy()
                except Exception:
                    pass
                tip_ref[0] = None

        widget.bind('<Enter>', enter, add='+')
        widget.bind('<Leave>', leave, add='+')

    def update(self) -> None:
        if not self.overlay:
            return

        five_h, weekly = self.app.get_extracted_windows()

        rem_5h = 0
        hours = 5
        if five_h:
            rem_5h = max(0, min(100, 100 - five_h.get('usedPercent', 100)))
            mins = five_h.get('windowDurationMins', 300)
            hours = mins // 60 if mins >= 60 else 5

        rem_wk = 0
        if weekly:
            rem_wk = max(0, min(100, 100 - weekly.get('usedPercent', 100)))

        if self.app.busy and self.app.exec_state == 'sending':
            cd_text = '⚡ 发送中'
            cd_fg = '#F59E0B'
        elif self.app.next_at:
            secs = max(0, int(self.app.next_at - time.time()))
            if secs >= 3600:
                cd_text = f'⏳ {secs//3600:02d}:{secs%3600//60:02d}:{secs%60:02d}'
            else:
                cd_text = f'⏳ {secs//60:02d}m{secs%60:02d}s'
            cd_fg = '#38BDF8'
        elif self.app.auto_active:
            cd_text = '🟢 待命中'
            cd_fg = '#10B981'
        else:
            cd_text = '⏸ 已暂停'
            cd_fg = '#9CA3AF'

        self.lbl_cd.configure(text=cd_text, fg=cd_fg)

        fg_5h = '#10B981' if rem_5h > 30 else '#F59E0B' if rem_5h > 0 else '#EF4444'
        self.lbl_5h.configure(text=f'{hours}H: {rem_5h:g}%', fg=fg_5h)

        fg_wk = '#10B981' if rem_wk > 30 else '#F59E0B' if rem_wk > 0 else '#EF4444'
        self.lbl_wk.configure(text=f'Week: {rem_wk:g}%', fg=fg_wk)
