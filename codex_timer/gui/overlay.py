"""Single-line compact desktop floating overlay (HUD Widget) with Dual-Layer Background Transparency & Solid Text."""
import datetime as dt
import time
import tkinter as tk
from tkinter import colorchooser, ttk
from typing import Callable, Optional, Dict, Any, Tuple

TRANS_KEY = '#000001'  # Reserved key color for 100% transparent text background


def adjust_color_hex(hex_color: str, factor: float = 1.35) -> str:
    """Helper to derive border color from background color."""
    try:
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 3:
            hex_color = ''.join(c * 2 for c in hex_color)
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        r = min(255, max(0, int(r * factor + 15)))
        g = min(255, max(0, int(g * factor + 15)))
        b = min(255, max(0, int(b * factor + 15)))
        return f'#{r:02x}{g:02x}{b:02x}'
    except Exception:
        return '#2F333A'


class SingleLineOverlay:
    """Dual-Layer Desktop HUD: Background opacity & color are freely adjustable while text is 100% solid & un-dimmed."""

    def __init__(self, root: tk.Tk, app_ref: Any):
        self.root = root
        self.app = app_ref
        self.overlay: Optional[tk.Toplevel] = None        # Foreground: 100% solid text & buttons
        self.bg_overlay: Optional[tk.Toplevel] = None     # Background: transparent/translucent colored card
        self.pinned = bool(self.app.config.get('overlay_pinned', True))

        # Color & Background Depth (Text is NEVER dimmed; only background alpha changes!)
        self.normal_bg_alpha = float(self.app.config.get('overlay_normal_bg_alpha', self.app.config.get('overlay_normal_alpha', 0.90)))
        self.pinned_bg_alpha = float(self.app.config.get('overlay_pinned_bg_alpha', self.app.config.get('overlay_pinned_alpha', 0.25)))
        self.bg_color = self.app.config.get('overlay_bg_color', '#181A1D')
        self.border_color = self.app.config.get('overlay_border_color', adjust_color_hex(self.bg_color))

        self.pos_x = self.app.config.get('overlay_x', 120)
        self.pos_y = self.app.config.get('overlay_y', 120)
        self.drag_x = 0
        self.drag_y = 0

        self._is_hovered = False
        self._leave_timer = None
        self._settings_dlg: Optional[tk.Toplevel] = None

    def _clamp_and_snap(self, x: int, y: int, snap_dist: int = 16) -> Tuple[int, int]:
        """Keep overlay within screen boundaries and apply edge snapping."""
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
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

        x = max(0, min(max_x, x))
        y = max(0, min(max_y, y))
        return x, y

    def show(self) -> None:
        if self.overlay and self.bg_overlay:
            try:
                self.bg_overlay.deiconify()
                self.overlay.deiconify()
                self.bg_overlay.lift()
                self.overlay.lift(self.bg_overlay)
                self._apply_visual_state()
                return
            except Exception:
                self.overlay = None
                self.bg_overlay = None

        self.pos_x, self.pos_y = self._clamp_and_snap(self.pos_x, self.pos_y)

        # ---------------------------------------------------------------------
        # 1. Background Window (Pure colored card, handles background transparency)
        # ---------------------------------------------------------------------
        self.bg_overlay = tk.Toplevel(self.root)
        self.bg_overlay.overrideredirect(True)
        self.bg_overlay.attributes('-topmost', True)
        self.bg_overlay.configure(bg=self.bg_color)
        self.bg_overlay.geometry(f'380x36+{self.pos_x}+{self.pos_y}')

        self.bg_border_frame = tk.Frame(self.bg_overlay, bg=self.border_color, padx=1, pady=1)
        self.bg_border_frame.pack(fill='both', expand=True)

        self.bg_main_f = tk.Frame(self.bg_border_frame, bg=self.bg_color)
        self.bg_main_f.pack(fill='both', expand=True)

        # ---------------------------------------------------------------------
        # 2. Foreground Window (100% Solid Text & Buttons, Never Dimmed!)
        # ---------------------------------------------------------------------
        self.overlay = tk.Toplevel(self.root)
        self.overlay.overrideredirect(True)
        self.overlay.attributes('-topmost', True)
        self.overlay.attributes('-transparentcolor', TRANS_KEY)
        self.overlay.configure(bg=TRANS_KEY)
        self.overlay.attributes('-alpha', 1.0)  # Text is ALWAYS 100% solid & vibrant!
        self.overlay.geometry(f'380x36+{self.pos_x}+{self.pos_y}')

        self.fg_f = tk.Frame(self.overlay, bg=TRANS_KEY, padx=8, pady=2)
        self.fg_f.pack(fill='both', expand=True)

        # 拖拽手柄 / 锁定标识
        self.lbl_drag = tk.Label(self.fg_f, text='🔒' if self.pinned else '⋮⋮',
                                 font=('Segoe UI', 9), bg=TRANS_KEY,
                                 fg='#38BDF8' if self.pinned else '#94A3B8',
                                 cursor='arrow' if self.pinned else 'fleur')
        self.lbl_drag.pack(side='left', padx=(0, 6))

        # 1. 倒计时
        self.lbl_cd = tk.Label(self.fg_f, text='⏳ --', font=('Consolas', 10, 'bold'),
                               bg=TRANS_KEY, fg='#38BDF8',
                               cursor='arrow' if self.pinned else 'fleur')
        self.lbl_cd.pack(side='left', padx=(0, 6))

        self.sep1 = tk.Label(self.fg_f, text='│', font=('Consolas', 9), bg=TRANS_KEY, fg='#4B5563')
        self.sep1.pack(side='left', padx=(0, 6))

        # 2. 短周期额度 (5H / 2H)
        self.lbl_5h = tk.Label(self.fg_f, text='5H: --', font=('Microsoft YaHei UI', 10, 'bold'),
                               bg=TRANS_KEY, fg='#10B981',
                               cursor='arrow' if self.pinned else 'fleur')
        self.lbl_5h.pack(side='left', padx=(0, 6))

        self.sep2 = tk.Label(self.fg_f, text='│', font=('Consolas', 9), bg=TRANS_KEY, fg='#4B5563')
        self.sep2.pack(side='left', padx=(0, 6))

        # 3. 周额度 (Week)
        self.lbl_wk = tk.Label(self.fg_f, text='Week: --', font=('Microsoft YaHei UI', 10, 'bold'),
                               bg=TRANS_KEY, fg='#10B981',
                               cursor='arrow' if self.pinned else 'fleur')
        self.lbl_wk.pack(side='left', padx=(0, 6))

        # ✕ 关闭按钮 (仅在 hover 或未固定时展示)
        self.btn_close = tk.Label(self.fg_f, text='✕', font=('Microsoft YaHei UI', 11, 'bold'),
                                  bg=TRANS_KEY, fg='#9CA3AF', cursor='hand2', padx=5, pady=1)
        self.btn_close.bind('<Button-1>', self._on_close_clicked)

        # 📌 固定/置顶切换按钮 (Hover 时展示)
        self.btn_pin = tk.Label(self.fg_f, text='📌', font=('Segoe UI Emoji', 11),
                                bg=TRANS_KEY, fg='#38BDF8' if self.pinned else '#64748B', cursor='hand2', padx=5, pady=1)
        self.btn_pin.bind('<Button-1>', self._on_pin_clicked)

        # ---------------------------------------------------------------------
        # Event Bindings for Dragging & Hovering
        # ---------------------------------------------------------------------
        # Dragging on text labels and on background windows
        drag_widgets = [self.fg_f, self.lbl_drag, self.lbl_cd, self.sep1, self.lbl_5h, self.sep2, self.lbl_wk,
                        self.bg_border_frame, self.bg_main_f]
        for w in drag_widgets:
            w.bind('<Button-1>', self._start_move)
            w.bind('<B1-Motion>', self._do_move)
            w.bind('<Button-3>', self._show_context_menu)
            w.bind('<MouseWheel>', self._on_mouse_wheel)
            w.bind('<Enter>', self._on_mouse_enter, add='+')
            w.bind('<Leave>', self._on_mouse_leave, add='+')

        # Action buttons dedicated events
        for btn in (self.btn_close, self.btn_pin):
            btn.bind('<Button-3>', self._show_context_menu)
            btn.bind('<Enter>', self._on_mouse_enter, add='+')
            btn.bind('<Leave>', self._on_mouse_leave, add='+')

        self.btn_close.bind('<Enter>', lambda e: self.btn_close.configure(fg='#EF4444'), add='+')
        self.btn_close.bind('<Leave>', lambda e: self.btn_close.configure(fg='#9CA3AF'), add='+')
        self.btn_pin.bind('<Enter>', lambda e: self.btn_pin.configure(fg='#38BDF8'), add='+')
        self.btn_pin.bind('<Leave>', lambda e: self.btn_pin.configure(fg='#38BDF8' if self.pinned else '#64748B'), add='+')

        # Tooltips
        self._bind_tooltip(self.lbl_cd, lambda: f"下次发送时间：{self.app.when.get()} (右键可唤起外观菜单)")
        self._bind_tooltip(self.lbl_5h, self.app.get_5h_tooltip)
        self._bind_tooltip(self.lbl_wk, self.app.get_wk_tooltip)
        self._bind_tooltip(self.lbl_drag, lambda: "🔒 已固定（不可移动，移开鼠标底色极淡）" if self.pinned else "⋮⋮ 自由拖拽模式")
        self._bind_tooltip(self.btn_pin, lambda: "📌 点击取消固定 (解锁为可拖拽)" if self.pinned else "📌 点击锁定固定 (锁定防误触+移开淡化底色)")
        self._bind_tooltip(self.btn_close, lambda: "✕ 关闭隐藏桌面悬浮条")

        # Lift foreground above background
        self.overlay.lift(self.bg_overlay)

        self._apply_visual_state()
        self.update()

    def _on_close_clicked(self, event=None) -> str:
        self.close()
        return "break"

    def _on_pin_clicked(self, event=None) -> str:
        self.toggle_pin()
        return "break"

    def _apply_visual_state(self) -> None:
        """Apply lock, adjust background opacity ONLY, while keeping text 100% solid."""
        if not self.overlay or not self.bg_overlay:
            return

        # Cursor
        cursor = 'arrow' if self.pinned else 'fleur'
        for w in (self.fg_f, self.lbl_drag, self.lbl_cd, self.lbl_5h, self.lbl_wk):
            w.configure(cursor=cursor)

        self.lbl_drag.configure(text='🔒' if self.pinned else '⋮⋮',
                                fg='#38BDF8' if self.pinned else '#6B7280')

        # Text layer ALWAYS stays 100% opaque!
        self.overlay.attributes('-alpha', 1.0)

        # Background layer ONLY fades / brightens:
        if self.pinned:
            if self._is_hovered:
                # Hovered while pinned: background lights up, show buttons
                self.bg_overlay.attributes('-alpha', self.normal_bg_alpha)
                self.btn_close.pack(side='right', padx=(4, 2))
                self.btn_pin.pack(side='right', padx=(2, 2))
                self.btn_pin.configure(fg='#38BDF8')  # Cyan active
            else:
                # Idle while pinned: background becomes faint / translucent, hide buttons
                self.bg_overlay.attributes('-alpha', self.pinned_bg_alpha)
                self.btn_pin.pack_forget()
                self.btn_close.pack_forget()
        else:
            # Unpinned: full normal background, pin button visible in inactive color
            self.bg_overlay.attributes('-alpha', self.normal_bg_alpha)
            self.btn_close.pack(side='right', padx=(4, 2))
            self.btn_pin.pack(side='right', padx=(2, 2))
            self.btn_pin.configure(fg='#64748B')  # Inactive gray

        # Keep foreground on top
        try:
            self.overlay.lift(self.bg_overlay)
        except Exception:
            pass

    def _on_mouse_enter(self, e=None) -> None:
        if hasattr(self, '_leave_timer') and self._leave_timer:
            try:
                self.overlay.after_cancel(self._leave_timer)
            except Exception:
                pass
            self._leave_timer = None
        if not self._is_hovered:
            self._is_hovered = True
            self._apply_visual_state()

    def _on_mouse_leave(self, e=None) -> None:
        if hasattr(self, '_leave_timer') and self._leave_timer:
            try:
                self.overlay.after_cancel(self._leave_timer)
            except Exception:
                pass
        if self.overlay:
            self._leave_timer = self.overlay.after(180, self._check_leave)

    def _check_leave(self) -> None:
        self._leave_timer = None
        if not self.overlay:
            return
        try:
            x, y = self.overlay.winfo_pointerxy()
            rx, ry = self.overlay.winfo_rootx(), self.overlay.winfo_rooty()
            rw, rh = self.overlay.winfo_width(), self.overlay.winfo_height()
            margin = 6
            if not (rx - margin <= x <= rx + rw + margin and ry - margin <= y <= ry + rh + margin):
                self._is_hovered = False
                self._apply_visual_state()
        except Exception:
            pass

    def apply_style(self, bg_color: str, pinned_bg_alpha: float, normal_bg_alpha: float, border_color: Optional[str] = None) -> None:
        """Update background colors and background depths dynamically in real-time (Text remains 100% solid)."""
        self.bg_color = bg_color
        self.border_color = border_color or adjust_color_hex(bg_color)
        self.pinned_bg_alpha = max(0.00, min(0.85, round(pinned_bg_alpha, 2)))
        self.normal_bg_alpha = max(0.20, min(1.00, round(normal_bg_alpha, 2)))

        # Save to config
        self.app.config.set('overlay_bg_color', self.bg_color, auto_save=False)
        self.app.config.set('overlay_border_color', self.border_color, auto_save=False)
        self.app.config.set('overlay_pinned_bg_alpha', self.pinned_bg_alpha, auto_save=False)
        self.app.config.set('overlay_pinned_alpha', self.pinned_bg_alpha, auto_save=False)
        self.app.config.set('overlay_normal_bg_alpha', self.normal_bg_alpha, auto_save=False)
        self.app.config.set('overlay_normal_alpha', self.normal_bg_alpha, auto_save=True)

        if self.bg_overlay:
            self.bg_overlay.configure(bg=self.bg_color)
            self.bg_border_frame.configure(bg=self.border_color)
            self.bg_main_f.configure(bg=self.bg_color)
            self._apply_visual_state()

    def toggle_pin(self) -> None:
        if not self.overlay:
            return
        self.pinned = not self.pinned
        self.app.config.set('overlay_pinned', self.pinned)
        self._apply_visual_state()
        status_txt = "已固定（不可移动，移开鼠标底色变淡，文字始终高亮）" if self.pinned else "已取消固定（可自由拖拽）"
        self.app.log(f"悬浮窗{status_txt}")

    def _start_move(self, e) -> None:
        if self.pinned:
            return  # Locked! Do not allow movement when pinned
        if self.overlay:
            self.drag_x = e.x_root - self.overlay.winfo_x()
            self.drag_y = e.y_root - self.overlay.winfo_y()

    def _do_move(self, e) -> None:
        if self.pinned:
            return  # Locked! Do not allow movement when pinned
        if self.overlay and self.bg_overlay:
            raw_x = e.x_root - self.drag_x
            raw_y = e.y_root - self.drag_y
            x, y = self._clamp_and_snap(raw_x, raw_y)
            self.overlay.geometry(f'+{x}+{y}')
            self.bg_overlay.geometry(f'+{x}+{y}')
            self.pos_x, self.pos_y = x, y
            self.app.config.set('overlay_x', x, auto_save=False)
            self.app.config.set('overlay_y', y, auto_save=True)

    def _on_mouse_wheel(self, e) -> None:
        """Wheel adjusts background opacity ONLY: text remains 100% solid."""
        if not self.bg_overlay:
            return
        delta = 0.04 if e.delta > 0 else -0.04
        if self.pinned:
            self.pinned_bg_alpha = max(0.00, min(0.85, round(self.pinned_bg_alpha + delta, 2)))
            self.app.config.set('overlay_pinned_bg_alpha', self.pinned_bg_alpha)
            if not self._is_hovered:
                self.bg_overlay.attributes('-alpha', self.pinned_bg_alpha)
        else:
            self.normal_bg_alpha = max(0.20, min(1.00, round(self.normal_bg_alpha + delta, 2)))
            self.app.config.set('overlay_normal_bg_alpha', self.normal_bg_alpha)
            self.bg_overlay.attributes('-alpha', self.normal_bg_alpha)

    def open_settings_dialog(self) -> None:
        """Open Appearance, Background Color & Background Opacity Settings Modal."""
        if self._settings_dlg:
            try:
                self._settings_dlg.lift()
                self._settings_dlg.focus_force()
                return
            except Exception:
                self._settings_dlg = None

        dlg = tk.Toplevel(self.root)
        dlg.title("🎨 悬浮窗底色与透明度设置")
        dlg.geometry("460x490")
        dlg.resizable(False, False)
        dlg.configure(bg='#F8FAFC')
        dlg.attributes('-topmost', True)
        self._settings_dlg = dlg

        # Header
        h_frame = tk.Frame(dlg, bg='#F8FAFC', padx=22, pady=16)
        h_frame.pack(fill='x')
        tk.Label(h_frame, text="🎨 悬浮窗底色与透明度", font=('Microsoft YaHei UI', 13, 'bold'), bg='#F8FAFC', fg='#0F172A').pack(anchor='w')
        tk.Label(h_frame, text="✨ 文字保持 100% 全饱和显示，调节仅改变背景底色，绝不弱化文字清晰度！",
                 font=('Microsoft YaHei UI', 9, 'bold'), bg='#F8FAFC', fg='#2563EB').pack(anchor='w', pady=(3, 0))

        content = tk.Frame(dlg, bg='#FFFFFF', padx=22, pady=16, highlightthickness=1, highlightbackground='#E2E8F0')
        content.pack(fill='both', expand=True, padx=18, pady=(0, 16))

        # 1. Color Presets
        tk.Label(content, text="底色背景颜色预设", font=('Microsoft YaHei UI', 10, 'bold'), bg='#FFFFFF', fg='#1E293B').pack(anchor='w')

        color_row = tk.Frame(content, bg='#FFFFFF')
        color_row.pack(fill='x', pady=(6, 12))

        presets = [
            ("经典冷灰", "#181A1D"),
            ("纯黑曜石", "#0D0F12"),
            ("极夜深蓝", "#0F172A"),
            ("极光深绿", "#052217"),
            ("极简全黑", "#000000"),
        ]

        color_var = tk.StringVar(value=self.bg_color)
        preview_box = tk.Frame(content, bg=self.bg_color, width=36, height=20, highlightthickness=1, highlightbackground='#94A3B8')

        def set_color(c: str):
            color_var.set(c)
            preview_box.configure(bg=c)
            self.apply_style(c, scale_pinned.get(), scale_normal.get())

        for name, col in presets:
            btn = tk.Button(color_row, text=name, bg=col, fg='#FFFFFF',
                            font=('Microsoft YaHei UI', 9), padx=7, pady=3, relief='flat', bd=0,
                            command=lambda c=col: set_color(c), cursor='hand2')
            btn.pack(side='left', padx=(0, 6))

        # Custom Color Picker Row
        custom_row = tk.Frame(content, bg='#FFFFFF')
        custom_row.pack(fill='x', pady=(0, 16))

        def pick_custom_color():
            picked = colorchooser.askcolor(color=color_var.get(), title="选择悬浮条底色")
            if picked and picked[1]:
                set_color(picked[1])

        btn_pick = tk.Button(custom_row, text="🌈 自定义底色...", bg='#F1F5F9', fg='#1E293B',
                             font=('Microsoft YaHei UI', 9, 'bold'), padx=10, pady=3, relief='flat',
                             command=pick_custom_color, cursor='hand2')
        btn_pick.pack(side='left', padx=(0, 10))

        tk.Label(custom_row, text="当前底色: ", font=('Microsoft YaHei UI', 9), bg='#FFFFFF', fg='#64748B').pack(side='left')
        preview_box.pack(side='left', padx=(4, 6))
        lbl_hex = tk.Label(custom_row, textvariable=color_var, font=('Consolas', 10, 'bold'), bg='#FFFFFF', fg='#0F172A')
        lbl_hex.pack(side='left')

        # 2. Pinned Faintness Slider (Background Opacity ONLY)
        pinned_row = tk.Frame(content, bg='#FFFFFF')
        pinned_row.pack(fill='x', pady=(0, 8))

        lbl_pinned_val = tk.Label(pinned_row, text=f"{int(self.pinned_bg_alpha * 100)}%", font=('Consolas', 10, 'bold'), bg='#FFFFFF', fg='#2563EB')
        lbl_pinned_val.pack(side='right')
        tk.Label(pinned_row, text="📌 固定时底色透明度 (0%为纯文字无底色，25%为淡淡微底)", font=('Microsoft YaHei UI', 9, 'bold'), bg='#FFFFFF', fg='#1E293B').pack(anchor='w')

        def on_pinned_slider(val):
            v = float(val)
            lbl_pinned_val.configure(text=f"{int(v * 100)}%")
            self.apply_style(color_var.get(), v, scale_normal.get())

        scale_pinned = ttk.Scale(content, from_=0.00, to=0.80, value=self.pinned_bg_alpha, command=on_pinned_slider)
        scale_pinned.pack(fill='x', pady=(0, 16))

        # 3. Normal / Active Opacity Slider (Background Opacity ONLY)
        normal_row = tk.Frame(content, bg='#FFFFFF')
        normal_row.pack(fill='x', pady=(0, 8))

        lbl_normal_val = tk.Label(normal_row, text=f"{int(self.normal_bg_alpha * 100)}%", font=('Consolas', 10, 'bold'), bg='#FFFFFF', fg='#2563EB')
        lbl_normal_val.pack(side='right')
        tk.Label(normal_row, text="✨ 悬停/日常底色浓度 (厚重纯色底)", font=('Microsoft YaHei UI', 9, 'bold'), bg='#FFFFFF', fg='#1E293B').pack(anchor='w')

        def on_normal_slider(val):
            v = float(val)
            lbl_normal_val.configure(text=f"{int(v * 100)}%")
            self.apply_style(color_var.get(), scale_pinned.get(), v)

        scale_normal = ttk.Scale(content, from_=0.20, to=1.00, value=self.normal_bg_alpha, command=on_normal_slider)
        scale_normal.pack(fill='x', pady=(0, 16))

        # Bottom Actions
        b_frame = tk.Frame(dlg, bg='#F8FAFC', padx=22, pady=10)
        b_frame.pack(fill='x')

        def reset_defaults():
            set_color('#181A1D')
            scale_pinned.set(0.25)
            scale_normal.set(0.90)
            lbl_pinned_val.configure(text="25%")
            lbl_normal_val.configure(text="90%")
            self.apply_style('#181A1D', 0.25, 0.90)

        btn_rst = tk.Button(b_frame, text="恢复默认", bg='#FFFFFF', fg='#64748B', font=('Microsoft YaHei UI', 9),
                            relief='flat', padx=12, pady=5, cursor='hand2', command=reset_defaults)
        btn_rst.pack(side='left')

        btn_ok = tk.Button(b_frame, text="完成并关闭", bg='#2563EB', fg='#FFFFFF', font=('Microsoft YaHei UI', 9, 'bold'),
                           relief='flat', padx=16, pady=5, cursor='hand2', command=dlg.destroy)
        btn_ok.pack(side='right')

    def hide(self) -> None:
        if self.overlay:
            try:
                self.overlay.destroy()
            except Exception:
                pass
            self.overlay = None
        if self.bg_overlay:
            try:
                self.bg_overlay.destroy()
            except Exception:
                pass
            self.bg_overlay = None

    def close(self) -> None:
        self.app.show_overlay.set(False)
        self.hide()
        self.app.config.set('show_overlay', False)

    def is_visible(self) -> bool:
        return self.overlay is not None

    def _show_context_menu(self, e) -> None:
        """Right-click context menu."""
        if not self.overlay:
            return
        menu = tk.Menu(self.overlay, tearoff=0, font=('Microsoft YaHei UI', 9))
        menu.add_command(label="⚡ 立即刷新额度", command=self.app.check)
        menu.add_command(label="📋 复制当前额度", command=self._copy_quota_summary)
        menu.add_separator()
        pin_label = "🔓 取消固定 (解锁为可拖拽)" if self.pinned else "📌 固定悬浮条 (锁定防误触+移开淡化底色)"
        menu.add_command(label=pin_label, command=self.toggle_pin)
        menu.add_command(label="🎨 悬浮窗底色与透明度...", command=self.open_settings_dialog)
        menu.add_separator()
        menu.add_command(label="🪟 打开主界面", command=self.app.restore_from_tray)
        menu.add_command(label="📦 隐藏悬浮窗", command=self.close)
        menu.add_separator()
        menu.add_command(label="❌ 彻底退出", command=self.app.quit_app)
        menu.tk_popup(e.x_root, e.y_root)

    def _copy_quota_summary(self) -> None:
        five_h, weekly = self.app.get_extracted_windows()
        rem_5h = max(0, min(100, 100 - five_h.get('usedPercent', 100))) if five_h else 0
        rem_wk = max(0, min(100, 100 - weekly.get('usedPercent', 100))) if weekly else 0
        txt = f"Codex 额度: 5H剩余 {rem_5h:g}%, 周额度剩余 {rem_wk:g}%, 下次自动发送: {self.app.when.get()}"
        self.root.clipboard_clear()
        self.root.clipboard_append(txt)
        self.app.log(f"已复制额度：{txt}")

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
            tk.Label(tw, text=txt, font=('Microsoft YaHei UI', 9), bg='#202227', fg='#E5E7EB',
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
            mins = five_h.get('windowDurationMins') or 300
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

        # Dirty-check cache to prevent redundant Tkinter redraws (0.0% CPU)
        if (cd_text, cd_fg) != getattr(self, '_last_cd', None):
            self.lbl_cd.configure(text=cd_text, fg=cd_fg)
            self._last_cd = (cd_text, cd_fg)

        fg_5h = '#10B981' if rem_5h > 30 else '#F59E0B' if rem_5h > 0 else '#EF4444'
        text_5h = f'{hours}H: {rem_5h:g}%' if five_h else '5H: --'
        if (text_5h, fg_5h) != getattr(self, '_last_5h', None):
            self.lbl_5h.configure(text=text_5h, fg=fg_5h)
            self._last_5h = (text_5h, fg_5h)

        fg_wk = '#10B981' if rem_wk > 30 else '#F59E0B' if rem_wk > 0 else '#EF4444'
        text_wk = f'Week: {rem_wk:g}%' if weekly else 'Week: --'
        if (text_wk, fg_wk) != getattr(self, '_last_wk', None):
            self.lbl_wk.configure(text=text_wk, fg=fg_wk)
            self._last_wk = (text_wk, fg_wk)
