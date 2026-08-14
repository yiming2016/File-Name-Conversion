# -*- coding: utf-8 -*-
"""tkinter 图形界面。"""

import copy
import csv
import os
import queue
import subprocess
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog, font as tkfont, messagebox, scrolledtext, ttk

from . import config as cfg_mod
from .core import (
    apply_plan,
    append_rename_log,
    build_plan,
    detect_script_language,
    discover_entries,
    split_targets,
    undo_plan,
)
from .engines import (
    CustomHttpEngine,
    EngineError,
    GoogleEngine,
    engine_choices,
    get_engine,
    list_ai_models,
    query_ai_balance,
    test_proxy_connectivity,
)
from . import glossary as glossary_mod
from .ipinfo import get_ip_info


try:
    import ctypes

    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass


EXTENSION_PRESETS = {
    "全部文件": "*",
    "视频文件": ".mp4,.mkv,.avi,.mov,.wmv,.flv,.webm,.m4v,.ts,.rmvb,.mpg,.mpeg,.3gp",
    "音频文件": ".mp3,.wav,.flac,.aac,.ogg,.m4a,.wma,.ape,.opus",
    "图片文件": ".jpg,.jpeg,.png,.gif,.bmp,.webp,.svg,.tif,.tiff,.ico,.heic",
    "文档文件": ".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.md,.csv,.epub",
}

TAB_BG = "#d6e4fa"
TAB_BG_SEL = "#fefefe"
TAB_BG_OK = "#c6f0c6"
TAB_BG_FAIL = "#ffcfcf"
TAB_BG_DEFAULT = "#b7e6b7"
TAB_FG = "#202020"
APP_BG = "#eef3fb"
PRIMARY = "#2f6fed"
APP_VERSION = "2.1"

# 标题层级：1~5 级各一个颜色，文字逐级缩小（文件文字固定大小）
TITLE_COLORS = ["#1e40af", "#2f6fed", "#0d9488", "#7c3aed", "#d97706"]
TITLE_FONTS = [
    ("Microsoft YaHei UI", 13, "bold"),
    ("Microsoft YaHei UI", 11, "bold"),
    ("Microsoft YaHei UI", 10, "bold"),
    ("Microsoft YaHei UI", 9, "bold"),
    ("Microsoft YaHei UI", 9, "bold"),
]

# 翻译框（预览表）单元格文字颜色
TREE_FG_NORMAL = "#1d2b44"   # 默认黑色
TREE_FG_OK = "#1e7e34"       # 翻译成功：原文件名绿色
TREE_FG_ERROR = "#d93025"    # 翻译失败：原文件名红色
TREE_FG_MANUAL = "#1e7e34"   # 手动修改过的新文件名绿色


def setup_styles():
    """彩色 UI 样式（clam 主题支持控件背景色）。"""
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(".", font=("Microsoft YaHei UI", 9))
    style.configure("TFrame", background=APP_BG)
    style.configure("TLabel", background=APP_BG, foreground="#1d2b44")
    style.configure("TLabelframe", background=APP_BG, bordercolor="#b9cbea")
    style.configure("TLabelframe.Label", background=APP_BG, foreground=PRIMARY, font=("Microsoft YaHei UI", 10, "bold"))
    style.configure("TButton", padding=(10, 4), background="#dfe9fb", foreground="#12315f")
    style.map("TButton", background=[("active", "#cbdaf5"), ("disabled", "#eef1f6")])
    style.configure("Accent.TButton", background=PRIMARY, foreground="white")
    style.map("Accent.TButton", background=[("active", "#2456c4")])
    style.configure("Green.TButton", background="#34a853", foreground="white")
    style.map("Green.TButton", background=[("active", "#2c8f46")])
    style.configure("Orange.TButton", background="#f9a825", foreground="white")
    style.map("Orange.TButton", background=[("active", "#d98e0a")])
    style.configure("Red.TButton", background="#d9534f", foreground="white")
    style.map("Red.TButton", background=[("active", "#bd3f3b")])
    style.configure("TEntry", fieldbackground="white")
    style.configure("TCombobox", fieldbackground="white", background="white")
    style.configure("TCheckbutton", background=APP_BG, foreground="#1d2b44")
    style.configure("TSpinbox", fieldbackground="white")
    style.configure("TProgressbar", background=PRIMARY, troughcolor="#d9e5f8")
    style.configure("Treeview", background="white", fieldbackground="white", rowheight=24, bordercolor="#c9d7ec")
    style.configure("Treeview.Heading", background=PRIMARY, foreground="white", font=("Microsoft YaHei UI", 9, "bold"))
    style.map("Treeview.Heading", background=[("active", "#2456c4")])
    style.configure("TPanedwindow", background=APP_BG)


def center_window(win, width=None, height=None):
    """把窗口居中显示在屏幕中心。"""
    win.update_idletasks()
    w = width or win.winfo_width()
    h = height or win.winfo_height()
    x = max(0, (win.winfo_screenwidth() - w) // 2)
    y = max(0, (win.winfo_screenheight() - h) // 2)
    win.geometry(f"{w}x{h}+{x}+{y}")


def show_error_dialog(parent, title, message):
    """红色文字的错误弹窗。"""
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.configure(bg=APP_BG)
    dlg.transient(parent)
    dlg.grab_set()
    center_window(dlg, 400, 170)
    tk.Label(
        dlg,
        text="✗ " + title,
        bg=APP_BG,
        fg="#d93025",
        font=("Microsoft YaHei UI", 11, "bold"),
    ).pack(pady=(14, 4))
    tk.Label(dlg, text=message, bg=APP_BG, fg="#d93025", wraplength=360).pack(pady=(0, 10))
    RoundedButton(dlg, "确定", dlg.destroy, style="red").pack(pady=(0, 12))


class StatusNotebook(tk.Frame):
    """自定义页签条：每个页签可独立变色（绿色=测试成功，红色=测试失败）。"""

    def __init__(self, parent, on_select=None):
        super().__init__(parent, bg="#f2f2f2", highlightthickness=0, bd=0)
        self.on_select = on_select
        self.on_reorder = None
        self.bar = tk.Frame(self, bg=PRIMARY, highlightthickness=0, bd=0)
        self.bar.pack(fill="x", padx=1, pady=(1, 0))
        self.body = tk.Frame(self, bg="#f2f2f2", highlightthickness=0, bd=0)
        self.body.pack(fill="both", expand=True)
        self.bar.bind("<Configure>", lambda _e: self._relayout_tabs())
        self.frames = []
        self.texts = []
        self.labels = []
        self.statuses = {}
        self.current = -1
        self.default_tab = None
        self.group_titles = {}
        self.group_order = []
        self.group_members = {}
        self.group_labels = {}
        self._rows = {}
        self._row_bands = {}
        self._drag = None
        self._drag_after = None

    def set_group_titles(self, titles):
        self.group_titles = dict(titles)
        for group in self.group_order:
            self._ensure_group_header(group)
        self._relayout_tabs()

    def add(self, frame, text, group=0):
        self.frames.append(frame)
        self.texts.append(text)
        idx = len(self.frames) - 1
        lbl = tk.Label(
            self.bar,
            text=text,
            padx=14,
            pady=6,
            bg=TAB_BG,
            fg=TAB_FG,
            cursor="hand2",
            font=("Microsoft YaHei UI", 9),
        )
        lbl.bind(
            "<Button-1>",
            lambda e, l=lbl: (self.select(self.labels.index(l)), self._on_tab_press(e, l)),
        )
        lbl.bind("<B1-Motion>", lambda e, l=lbl: self._on_tab_motion(e, l))
        lbl.bind("<ButtonRelease-1>", lambda e, l=lbl: self._on_tab_release(e, l))
        self.labels.append(lbl)
        self.statuses[text] = None
        if group not in self.group_order:
            self.group_order.append(group)
        self.group_members.setdefault(group, []).append(idx)
        self._ensure_group_header(group)
        self._relayout_tabs()
        return frame

    def _ensure_group_header(self, group):
        if group in self.group_labels:
            return
        title = self.group_titles.get(group, f"组 {group + 1}")
        lbl = tk.Label(
            self.bar,
            text=title,
            padx=4,
            pady=8,
            bg="#dfe9fb",
            fg=PRIMARY,
            font=("Microsoft YaHei UI", 11, "bold"),
            cursor="arrow",
            justify="center",
            width=2,
        )
        self.group_labels[group] = lbl

    def _relayout_tabs(self, _event=None):
        """页签按两组排布：组标题竖排显示在每组左侧，页签在其右侧流式换行。"""
        if not self.labels:
            return
        w = max(self.bar.winfo_width(), 2)
        y = 2
        self._rows = {}
        self._row_bands = {}
        for group in self.group_order:
            header = self.group_labels.get(group)
            members = self.group_members.get(group, [])
            if header is None or not members:
                continue
            vw = header.winfo_reqwidth()
            x0 = 2 + vw + 8
            x = x0
            y0 = y
            row_h = 0
            rows = []
            bands = []
            current_row = []
            row_top = y
            for idx in members:
                lbl = self.labels[idx]
                lw = lbl.winfo_reqwidth()
                lh = lbl.winfo_reqheight()
                # 放不下时提前换行，避免页签被窗口右缘裁切
                if x > x0 and x + lw > w - 4:
                    rows.append(current_row)
                    bands.append((row_top, y + row_h))
                    current_row = []
                    x = x0
                    y += row_h + 2
                    row_h = 0
                    row_top = y
                lbl.place(x=x, y=y, anchor="nw")
                current_row.append(idx)
                x += lw + 2
                row_h = max(row_h, lh)
            if current_row:
                rows.append(current_row)
                bands.append((row_top, y + row_h))
            self._rows[group] = rows
            self._row_bands[group] = bands
            group_h = max(header.winfo_reqheight(), (y + row_h) - y0)
            header.place(x=2, y=y0, anchor="nw", width=vw, height=group_h)
            y = y0 + group_h + 6
        self.bar.configure(height=max(y - 2, 12))

    # ---------------- 长按拖动排序 ----------------
    def _group_of_index(self, idx):
        for g, members in self.group_members.items():
            if idx in members:
                return g
        return None

    def _on_tab_press(self, event, lbl):
        self._drag = {"label": lbl, "active": False, "x0": event.x_root, "y0": event.y_root}
        if self._drag_after is not None:
            try:
                self.after_cancel(self._drag_after)
            except tk.TclError:
                pass
        self._drag_after = self.after(400, self._drag_activate)

    def _drag_activate(self):
        self._drag_after = None
        if self._drag is not None and not self._drag["active"]:
            self._drag["active"] = True
            try:
                self._drag["label"].lift()
            except tk.TclError:
                pass

    def _on_tab_motion(self, event, lbl):
        if self._drag is None or not self._drag.get("active"):
            return
        src_idx = self.labels.index(lbl)
        group = self._group_of_index(src_idx)
        if group is None:
            return
        try:
            bx = self.bar.winfo_rootx()
        except tk.TclError:
            return
        px = event.x_root - bx
        # 找到被拖页签所在的“行”，拖动只在本行内排序
        rows = self._rows.get(group) or []
        src_row_i = next((i for i, row in enumerate(rows) if src_idx in row), None)
        if src_row_i is None:
            return
        bands = self._row_bands.get(group) or []
        if src_row_i >= len(bands):
            return
        y0, y1 = bands[src_row_i]
        try:
            lw = lbl.winfo_width()
            lh = lbl.winfo_height()
        except tk.TclError:
            return
        # 纵向吸附回本行（限制大范围拖动），横向跟随指针
        lbl.place(x=max(0, px - lw // 2), y=max(0, y0 + (y1 - y0 - lh) // 2))
        # 同行内实时排序：按指针 X 决定插入位置
        row = rows[src_row_i]
        others = [i for i in row if i != src_idx]
        insert_before = None
        for i in others:
            try:
                cx = self.labels[i].winfo_rootx() + self.labels[i].winfo_width() / 2 - bx
            except tk.TclError:
                continue
            if px < cx:
                insert_before = i
                break
        new_row = []
        for i in others:
            if i == insert_before:
                new_row.append(src_idx)
            new_row.append(i)
        if insert_before is None:
            new_row.append(src_idx)
        members = self.group_members[group]
        row_set = set(row)
        start = next((k for k, x in enumerate(members) if x in row_set), None)
        if start is None:
            return
        end = start
        while end < len(members) and members[end] in row_set:
            end += 1
        if new_row != members[start:end]:
            members[start:end] = new_row
            self._relayout_tabs()
            # 重排后让被拖页签继续吸附在本行
            try:
                lbl.lift()
                rows2 = self._rows.get(group) or []
                bands2 = self._row_bands.get(group) or []
                for i, row2 in enumerate(rows2):
                    if src_idx in row2 and i < len(bands2):
                        yy0, yy1 = bands2[i]
                        lbl.place(
                            x=max(0, px - lw // 2),
                            y=max(0, yy0 + (yy1 - yy0 - lh) // 2),
                        )
                        break
            except tk.TclError:
                pass

    def _on_tab_release(self, event, lbl):
        if self._drag_after is not None:
            try:
                self.after_cancel(self._drag_after)
            except tk.TclError:
                pass
            self._drag_after = None
        d = self._drag
        self._drag = None
        if d is None or not d.get("active"):
            return
        src_idx = self.labels.index(lbl)
        group = self._group_of_index(src_idx)
        # 拖动过程中已实时吸附排序，这里只需归位并保存顺序
        self._relayout_tabs()
        if group is not None and self.on_reorder:
            try:
                self.on_reorder(group, [self.texts[i] for i in self.group_members[group]])
            except Exception:
                pass

    def tabs(self):
        return list(self.frames)

    def tab(self, frame, option=None):
        idx = self.frames.index(frame)
        if option is None or option == "text":
            return self.texts[idx]
        return None

    def select(self, idx):
        self.current = idx
        for i, f in enumerate(self.frames):
            if i == idx:
                f.pack(fill="both", expand=True)
            else:
                f.pack_forget()
        self._paint()
        if self.on_select:
            try:
                self.on_select(self.texts[idx], idx)
            except Exception:
                pass

    def set_status(self, text, status):
        if text in self.statuses:
            self.statuses[text] = status
            self._paint()

    def set_default(self, text):
        """标记“设为默认”的页签（标题栏显示绿色）。"""
        self.default_tab = text
        self._paint()

    def _paint(self):
        for i, lbl in enumerate(self.labels):
            st = self.statuses[self.texts[i]]
            is_default = self.default_tab and self.texts[i] == self.default_tab
            if st == "ok":
                bg = TAB_BG_OK
            elif st == "fail":
                bg = TAB_BG_FAIL
            elif is_default:
                bg = TAB_BG_DEFAULT
            elif i == self.current:
                bg = TAB_BG_SEL
            else:
                bg = TAB_BG
            lbl.config(bg=bg)


class RoundedButton(tk.Canvas):
    """圆角按钮（Canvas 自绘，支持悬停变色与禁用态）。"""

    COLORS = {
        "green": ("#34a853", "#2c8f46", "white"),
        "blue": ("#2f6fed", "#2456c4", "white"),
        "orange": ("#f9a825", "#d98e0a", "white"),
        "red": ("#d9534f", "#bd3f3b", "white"),
        "gray": ("#dfe9fb", "#cbdaf5", "#12315f"),
    }
    DISABLED_BG = "#cdd6e3"
    DISABLED_FG = "#8a94a6"

    def __init__(self, master, text, command=None, style="gray", width=None, height=34, radius=14, state="normal"):
        if width is None:
            width = max(84, 20 * len(text) + 28)
        super().__init__(
            master,
            width=width,
            height=height,
            bg=APP_BG,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.text = text
        self.command = command
        self.radius = radius
        self._state = state
        self._hover = False
        base, active, fg = self.COLORS.get(style, self.COLORS["gray"])
        self.base = base
        self.active = active
        self.fg = fg
        self.font = ("Microsoft YaHei UI", 9)
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", lambda _e: self._set_hover(True))
        self.bind("<Leave>", lambda _e: self._set_hover(False))
        self._draw()

    def _fill(self):
        return self.active if self._hover else self.base

    def _draw(self):
        self.delete("all")
        w = max(self.winfo_width(), 2)
        h = max(self.winfo_height(), 2)
        r = min(self.radius, h // 2)
        pts = [r, 0, w - r, 0, w, r, w, h - r, w - r, h, r, h, 0, h - r, 0, r]
        if self._state == "disabled":
            fill, fg = self.DISABLED_BG, self.DISABLED_FG
        else:
            fill, fg = self._fill(), self.fg
        self.create_polygon(pts, smooth=True, fill=fill, outline="")
        self.create_text(w / 2, h / 2, text=self.text, fill=fg, font=self.font)

    def _set_hover(self, on):
        self._hover = on
        self._draw()

    def _on_click(self, _e):
        if self._state == "normal" and self.command:
            self.command()

    def set_state(self, state):
        self._state = state
        self._draw()


class PlayPauseButton(tk.Canvas):
    """播放器按钮：无任务=灰色三角；待运行=绿色三角；运行中=红色方块；暂停=绿色三角。"""

    def __init__(self, master, command=None, size=40):
        super().__init__(
            master,
            width=size,
            height=size,
            bg=APP_BG,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.command = command
        self.state = "idle"
        self.bind("<Button-1>", self._on_click)
        self.bind("<Configure>", lambda _e: self._draw())
        self._draw()

    def set_state(self, state):
        self.state = state
        self._draw()

    def _draw(self):
        self.delete("all")
        w = max(self.winfo_width(), 2)
        h = max(self.winfo_height(), 2)
        cx, cy = w / 2, h / 2
        if self.state == "running":
            # 红色方块（暂停）
            self.create_rectangle(cx - 8, cy - 8, cx + 8, cy + 8, fill="#d93025", outline="")
        else:
            # 横向三角（播放）
            color = "#b0b8c4" if self.state == "idle" else "#34a853"
            self.create_polygon(
                cx - 5, cy - 10, cx - 5, cy + 10, cx + 10, cy,
                fill=color,
                outline="",
            )

    def _on_click(self, _e):
        if self.state != "idle" and self.command:
            self.command()


class LogWindow(tk.Toplevel):
    """独立日志查看窗口。"""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("日志")
        self.configure(bg=APP_BG)
        self.geometry("780x480")
        center_window(self)
        self.text = scrolledtext.ScrolledText(self, state="disabled", font=("Microsoft YaHei UI", 9))
        self.text.pack(fill="both", expand=True, padx=8, pady=8)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.append_text("".join(app._log_lines))

    def append_text(self, content):
        self.text.config(state="normal")
        self.text.insert("end", content)
        self.text.see("end")
        self.text.config(state="disabled")

    def _close(self):
        self.app._log_window = None
        self.destroy()


class TaskDetailWindow(tk.Toplevel):
    """任务详情窗口：表格展示任务文件；勾选＝参与翻译，鼠标选中＋Del/右键删除＝移出队列。"""

    COLUMNS = (
        ("chk", 50, "center"),
        ("loc", 560, "w"),
        ("fmt", 80, "center"),
        ("name", 430, "w"),
    )

    def __init__(self, parent, app, task_index):
        super().__init__(parent)
        self.app = app
        self.task_index = task_index
        self.task = app._tasks[task_index]
        n = len(self.task.get("files", []))
        self.checked = set(range(n))
        self.current = None
        self._sort_col = None
        self._sort_rev = False
        self._dlg_history = []
        self._dlg_redo = []
        self.title(f"任务 {task_index + 1} 内容")
        self.configure(bg=APP_BG)
        self.transient(parent)
        self._build_ui()
        self._refresh()
        self._fit_loc_width()  # 每次进入时按实际路径自动调整一次；之后可手动拖动
        center_window(self, 1240, 960)
        self.after(30, self._grab_focus)  # 打开后立即把键盘焦点移到表格，方向键直接可用
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        self.app._refresh_tasks()  # 关闭时同步主界面任务队列的文件数/选中数
        self.destroy()

    def _grab_focus(self):
        try:
            self.lift()
            self.focus_force()
            self.tree.focus_set()
            children = self.tree.get_children()
            if children:
                self.tree.focus(children[0])
        except tk.TclError:
            pass

    def _build_ui(self):
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)
        head = ttk.Frame(frame)
        head.pack(fill="x")
        ttk.Label(frame, text=f"任务 {self.task_index + 1}", font=("Microsoft YaHei UI", 13, "bold")).pack(anchor="w")
        self.count_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.count_var, foreground=PRIMARY, font=("Microsoft YaHei UI", 10, "bold")).pack(
            anchor="e", pady=(2, 0)
        )
        self.selected_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.selected_var, foreground=PRIMARY, font=("Microsoft YaHei UI", 10, "bold")).pack(
            anchor="e", pady=(2, 0)
        )
        ttk.Label(
            frame,
            text="勾选＝参与翻译；鼠标选中后按 Del 或右键“删除”＝移出任务队列；Ctrl+点击多选，Ctrl+A 全选",
            foreground="#888888",
        ).pack(anchor="w", pady=(4, 4))
        ttk.Label(
            frame,
            text="快捷键：空格勾选 · 回车打开位置 · 方向键移动选择 · Del 删除 · Ctrl+A 全选",
            foreground="#888888",
        ).pack(anchor="w", pady=(0, 4))
        table = ttk.Frame(frame)
        table.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            table,
            columns=[c[0] for c in self.COLUMNS],
            show="headings",
            selectmode="extended",
        )
        for cid, width, anchor in self.COLUMNS:
            # 勾选/格式列宽度固定不可压缩；位置列自动适配；文件名列伸缩吸收窗口变化
            self.tree.column(cid, width=width, minwidth=width, anchor=anchor, stretch=(cid == "name"))
            self.tree.heading(cid, text="")
        self.tree.heading("chk", command=self._toggle_all)
        self.tree.heading("loc", text="位置", command=lambda: self._sort_by("loc"))
        self.tree.heading("fmt", text="格式", command=lambda: self._sort_by("fmt"))
        self.tree.heading("name", text="文件名", command=lambda: self._sort_by("name"))
        vsb = ThumbScrollbar(table, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Button-1>", self._on_click)
        self.tree.bind("<Button-3>", self._on_right_click)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Delete>", self._on_delete_key)
        self.tree.bind("<Control-a>", self._select_all)
        self.tree.bind("<Control-A>", self._select_all)
        self.tree.bind("<space>", self._on_space)
        self.tree.bind("<Return>", self._on_enter)
        self.tree.bind("<Control-z>", self._on_dlg_undo)
        self.tree.bind("<Control-Z>", self._on_dlg_redo)
        self.tree.bind("<Control-y>", self._on_dlg_redo)
        for key in ("Up", "Down", "Left", "Right"):
            self.tree.bind(f"<{key}>", self._on_arrow)
        self.tree.bind("<MouseWheel>", self._on_wheel)

    def _iter_rows(self):
        for i, path in enumerate(self.task.get("files", [])):
            folder = os.path.dirname(path) or ""
            stem, ext = os.path.splitext(os.path.basename(path))
            yield i, folder, ext, stem

    def _refresh(self):
        rows = list(self._iter_rows())
        saved = set(self.tree.selection())
        focus = self.tree.focus()
        if self._sort_col == "loc":
            rows.sort(key=lambda r: (r[1].lower(), r[3].lower()), reverse=self._sort_rev)
        elif self._sort_col == "fmt":
            rows.sort(key=lambda r: (r[2].lower(), r[3].lower()), reverse=self._sort_rev)
        elif self._sort_col == "name":
            rows.sort(key=lambda r: (r[3].lower(), r[1].lower()), reverse=self._sort_rev)
        for item in self.tree.get_children():
            self.tree.delete(item)
        for i, folder, ext, stem in rows:
            self.tree.insert("", "end", iid=str(i), values=("☑" if i in self.checked else "☐", folder, ext, stem))
        keep = [i for i in saved if self.tree.exists(i)]
        if keep:
            self.tree.selection_set(keep)
        if focus and self.tree.exists(focus):
            self.tree.focus(focus)
        elif keep:
            self.tree.focus(keep[0])
        n = len(rows)
        all_on = bool(rows) and len(self.checked) == n
        self.tree.heading("chk", text="☑" if all_on else "☐")
        for cid, label in (("loc", "位置"), ("fmt", "格式"), ("name", "文件名")):
            if self._sort_col == cid:
                text = label + (" ▲" if not self._sort_rev else " ▼")
            else:
                text = label
            self.tree.heading(cid, text=text)
        self.count_var.set(f"文件数量：{n}")
        self.selected_var.set(f"选中：{len(self.checked)}")

    def _fit_loc_width(self):
        """“位置”列按当前文件路径实际长度自动调整宽度（每次进入/刷新时）。"""
        try:
            spec = ttk.Style(self).lookup("Treeview", "font") or "TkDefaultFont"
            f = tkfont.Font(font=spec)
        except tk.TclError:
            f = tkfont.Font(family="Microsoft YaHei UI", size=9)
        maxw = 120
        for _i, path in enumerate(self.task.get("files", [])):
            folder = os.path.dirname(path) or ""
            maxw = max(maxw, f.measure(folder) + 24)
        maxw = min(maxw, 900)
        self.tree.column("loc", width=maxw, minwidth=min(maxw, 140))

    def _apply_checked(self):
        self.task["checked"] = sorted(self.checked)
        self.app._refresh_tasks()  # 主界面任务队列实时更新“选中xx个”

    def _toggle_all(self):
        n = len(self.task.get("files", []))
        if n and len(self.checked) == n:
            self.checked.clear()
        else:
            self.checked = set(range(n))
        self._apply_checked()
        self._refresh()

    def _sort_by(self, col):
        # 若该列所有值都相同，点击不调整排序方式
        values = set()
        for _i, path in enumerate(self.task.get("files", [])):
            if col == "loc":
                v = (os.path.dirname(path) or "").lower()
            elif col == "fmt":
                v = os.path.splitext(os.path.basename(path))[1].lower()
            else:
                v = os.path.splitext(os.path.basename(path))[0].lower()
            values.add(v)
        if len(values) <= 1:
            return
        if self._sort_col != col:
            self._sort_col = col
            self._sort_rev = False
        else:
            self._sort_rev = not self._sort_rev
        self._refresh()

    def _on_click(self, event):
        self.tree.focus_set()
        region = self.tree.identify("region", event.x, event.y)
        if region == "heading":
            return
        if region == "separator":
            # 只允许拖动“位置”列右侧分隔线自定义宽度；勾选/格式/文件名列仍锁定
            widths = [int(self.tree.column(c, "width")) for c in ("chk", "loc", "fmt")]
            loc_right = widths[0] + widths[1]
            if abs(event.x - loc_right) <= 8:
                return None
            return "break"
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        idx = int(iid)
        if self.tree.identify_column(event.x) == "#1":
            # 勾选列只切换“参与翻译”，不改变鼠标选中状态
            if idx in self.checked:
                self.checked.discard(idx)
            else:
                self.checked.add(idx)
            self._apply_checked()
            self._refresh()
            return "break"
        # 其余列交给 Treeview 原生 extended 模式：单击单选、Ctrl+点击多选/少选、Shift+点击范围选择
        self.current = idx
        return None

    def _on_delete_key(self, _event=None):
        self._delete_selected()
        return "break"

    def _select_all(self, _event=None):
        self.tree.selection_set(self.tree.get_children())
        return "break"

    def _on_space(self, _event=None):
        """空格：切换选中行最左侧的对勾（勾选/取消勾选）。"""
        self.tree.focus_set()
        sel = self.tree.selection()
        if not sel:
            return "break"
        for iid in sel:
            idx = int(iid)
            if idx in self.checked:
                self.checked.discard(idx)
            else:
                self.checked.add(idx)
        self._apply_checked()
        self._refresh()
        return "break"

    def _on_enter(self, _event=None):
        """弹窗按回车：打开选中文件所在位置。"""
        self._open_file_location()
        return "break"

    def _on_double_click(self, event):
        """弹窗双击行：打开该文件所在位置。"""
        if self.tree.identify_column(event.x) == "#1":
            return "break"
        iid = self.tree.identify_row(event.y)
        if not iid:
            return "break"
        self.tree.selection_set(iid)
        self.current = int(iid)
        self._open_file_location()
        return "break"

    def _on_arrow(self, event):
        """上下左右移动选择（不依赖原生焦点，空格/勾选刷新后仍可用）。"""
        children = self.tree.get_children()
        if not children:
            return "break"
        sel = self.tree.selection()
        if sel:
            cur = sel[0]
        else:
            cur = self.tree.focus() or children[0]
        try:
            idx = children.index(cur)
        except ValueError:
            idx = 0
        if event.keysym in ("Up", "Left"):
            idx = max(0, idx - 1)
        else:
            idx = min(len(children) - 1, idx + 1)
        target = children[idx]
        self.tree.selection_set(target)
        self.tree.focus(target)
        self.tree.see(target)
        self.current = int(target)
        return "break"

    def _delete_selected(self):
        indices = [int(i) for i in self.tree.selection()]
        if not indices:
            return
        self._push_dlg_history()
        files = self.task.get("files", [])
        children = self.tree.get_children()
        positions = [children.index(str(i)) for i in indices if str(i) in children]
        base = max(positions) if positions else 0
        # 删除后自动选中“下方一项”；若删除的是最后一项则选中“上方一项”
        target_path = None
        if base + 1 < len(children):
            ti = int(children[base + 1])
            if 0 <= ti < len(files):
                target_path = files[ti]
        elif base - 1 >= 0:
            ti = int(children[base - 1])
            if 0 <= ti < len(files):
                target_path = files[ti]
        remove = set(indices)
        kept = []
        new_checked = set()
        shift = 0
        for i, f in enumerate(files):
            if i in remove:
                shift += 1
                continue
            kept.append(f)
            if i in self.checked:
                new_checked.add(i - shift)
        self.task["files"] = kept
        self.task["checked"] = sorted(new_checked)
        self.checked = new_checked
        self.app._refresh_tasks()
        self._refresh()
        if target_path is not None:
            try:
                new_idx = self.task["files"].index(target_path)
            except ValueError:
                return
            iid = str(new_idx)
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.current = new_idx

    def _push_dlg_history(self):
        self._dlg_history.append((
            list(self.task.get("files", [])),
            sorted(self.checked),
            [int(i) for i in self.tree.selection() if i.isdigit()],
            self.tree.yview()[0],
        ))
        if len(self._dlg_history) > 50:
            self._dlg_history.pop(0)
        self._dlg_redo.clear()

    def _restore_dlg_state(self, state):
        self.task["files"] = list(state[0])
        self.task["checked"] = sorted(state[1])
        self.checked = set(state[1])
        self.app._refresh_tasks()
        self._refresh()
        # 选中恢复的文件（旧索引 → 新索引）
        keep = []
        for old_idx in state[2]:
            if 0 <= old_idx < len(state[0]):
                path = state[0][old_idx]
                try:
                    new_idx = self.task["files"].index(path)
                except ValueError:
                    continue
                keep.append(str(new_idx))
        if keep:
            self.tree.selection_set(keep)
            self.tree.focus(keep[0])
            self.current = int(keep[0])
        try:
            self.tree.yview_moveto(float(state[3]))
        except (ValueError, tk.TclError):
            pass

    def _on_dlg_undo(self, _event=None):
        """详情弹窗 Ctrl+Z：撤销上一次删除文件操作。"""
        if not self._dlg_history:
            return "break"
        state = self._dlg_history.pop()
        self._dlg_redo.append((
            list(self.task.get("files", [])),
            sorted(self.checked),
            [int(i) for i in self.tree.selection() if i.isdigit()],
            self.tree.yview()[0],
        ))
        self._restore_dlg_state(state)
        return "break"

    def _on_dlg_redo(self, _event=None):
        """详情弹窗 Ctrl+Y / Ctrl+Shift+Z：重做被撤销的删除操作。"""
        if not self._dlg_redo:
            return "break"
        state = self._dlg_redo.pop()
        self._dlg_history.append((
            list(self.task.get("files", [])),
            sorted(self.checked),
            [int(i) for i in self.tree.selection() if i.isdigit()],
            self.tree.yview()[0],
        ))
        self._restore_dlg_state(state)
        return "break"

    def _on_right_click(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            idx = int(iid)
            self.current = idx
            # 不在当前选中集内则选中该行；已在选中集内则保持多选
            if iid not in self.tree.selection():
                self.tree.selection_set(iid)
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="删除", command=self._delete_selected)
        menu.add_command(label="打开文件所在位置", command=self._open_file_location)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _open_file_location(self):
        sel = self.tree.selection()
        idx = int(sel[0]) if sel else self.current
        if idx is None or idx >= len(self.task.get("files", [])):
            return
        path = self.task["files"][idx]
        if os.path.isfile(path):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else:
            folder = os.path.dirname(path)
            if folder and os.path.isdir(folder):
                subprocess.Popen(["explorer", os.path.normpath(folder)])

    def _on_wheel(self, event):
        self.tree.yview_scroll(int(-event.delta / 120), "units")
        return "break"


class RowList(tk.Canvas):
    """可滚动的行列表：支持勾选列、序号列或格式列，点击选中变蓝，DEL 删除选中行。"""

    ROW_H = 26

    def __init__(
        self,
        master,
        on_delete=None,
        on_hover=None,
        on_open=None,
        open_label="打开文件所在位置",
        height_rows=8,
        width=300,
        checkable=False,
        number_col=True,
        fmt_col=False,
        sortable=False,
        header_bg=None,
        ctrl_toggles_check=True,
    ):
        super().__init__(
            master,
            bg="white",
            highlightthickness=1,
            highlightbackground="#b9cbea",
            width=width,
            height=height_rows * self.ROW_H + 4,
        )
        self.on_delete = on_delete
        self.on_hover = on_hover
        self.on_open = on_open
        self.open_label = open_label
        self.checkable = checkable
        self._number_col = number_col
        self._fmt_col = fmt_col
        self._sortable = sortable
        self._header_bg = header_bg
        self._ctrl_toggles_check = ctrl_toggles_check
        self.rows = []
        self._row_keys = []
        self.selected = set()
        self.checked = set()
        self._hovered = None
        self._marquee_anchor = None
        self._top_pad = 24 if checkable else 2
        self._sort_col = None
        self._sort_rev = False
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", lambda _e: setattr(self, "_marquee_anchor", None))
        self.bind("<Button-3>", self._on_right_click)
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda _e: self._hover(None))
        self.bind("<Delete>", self._on_delete_key)
        for key in ("Up", "Down", "Left", "Right"):
            self.bind(f"<{key}>", self._on_arrow)
        self.bind("<space>", self._on_space)
        self.bind("<MouseWheel>", self._on_wheel)

    def set_rows(self, rows, keys=None):
        self.rows = list(rows)
        self._row_keys = list(keys) if keys is not None else list(range(len(self.rows)))
        self.selected.clear()
        self.checked.clear()
        self._hovered = None
        self._sort_col = None
        self._sort_rev = False
        if self.on_hover:
            self.on_hover(None)
        self._draw()

    def checked_indices(self):
        """返回勾选行的稳定键（任务索引）。"""
        return [self._row_keys[i] for i in sorted(self.checked)]

    def set_checked(self, keys):
        self.checked = {self._row_keys.index(k) for k in keys if k in self._row_keys}
        self._draw()

    def check_all(self, checked=True):
        """全部勾选（或全部取消），同时选中对应行。"""
        if not self.checkable:
            return
        if checked:
            self.checked = set(range(len(self.rows)))
            self.selected = set(self.checked)
        else:
            self.checked.clear()
            self.selected.clear()
        self._draw()

    def _toggle_all_checked(self):
        if self.checkable and self.rows:
            if len(self.checked) == len(self.rows):
                self.checked.clear()
                self.selected.clear()
            else:
                self.checked = set(range(len(self.rows)))
                self.selected = set(self.checked)
            self._draw()

    def add_row(self, text):
        self.rows.append(text)
        self._draw()

    def _on_wheel(self, event):
        if self.yview()[0] == 0.0 and event.delta > 0:
            return
        self.yview_scroll(int(-event.delta / 120), "units")
        self._draw()  # 滚动后重绘固定表头

    def _scroll_offset(self):
        """当前滚动后在画布坐标系中的内容偏移量。"""
        try:
            region = self.cget("scrollregion")
            _x0, _y0, _x1, y1 = [float(v) for v in region.split()]
        except Exception:
            return 0
        return self.yview()[0] * y1

    def _row_at(self, y):
        """根据鼠标 y 坐标（考虑滚动偏移）计算所在行位置。"""
        return int((y + self._scroll_offset() - self._top_pad) // self.ROW_H)

    def _on_press(self, event):
        self.focus_set()
        if self.checkable and event.y < self._top_pad:
            # 固定表头区域（始终位于视口顶部）
            if event.x < 26:
                self._toggle_all_checked()  # 顶部全选方块
            elif self._sortable and self._fmt_col:
                fw = self._fmt_width()
                if event.x < 28 + fw:
                    self.sort_rows("fmt")  # 格式
                else:
                    self.sort_rows("text")  # 文件名
            elif self._sortable and event.x < 82:
                self.sort_rows("key")  # 序号
            elif self._sortable:
                self.sort_rows("text")  # 文件名
            return
        idx = self._row_at(event.y)
        if 0 <= idx < len(self.rows):
            ctrl = (event.state & 0x0004) != 0
            if self.checkable and event.x < 26:
                # 行首勾选方块：切换勾选
                if idx in self.checked:
                    self.checked.discard(idx)
                    self.selected.discard(idx)
                else:
                    self.checked.add(idx)
                    self.selected.add(idx)
            elif ctrl and self._ctrl_toggles_check:
                # 任务队列：Ctrl+点击行内任意位置切换勾选
                if idx in self.checked:
                    self.checked.discard(idx)
                    self.selected.discard(idx)
                else:
                    self.checked.add(idx)
                    self.selected.add(idx)
            elif ctrl:
                # 文件栏：Ctrl+点击只切换选中（多选/少选），不影响勾选
                if idx in self.selected:
                    self.selected.discard(idx)
                else:
                    self.selected.add(idx)
            else:
                self.selected = {idx}
            self._marquee_anchor = None
            self._draw()
            self._hover(idx)
        else:
            # 长按空白处：开始框选
            anchor = max(0, min(idx, len(self.rows) - 1)) if self.rows else 0
            self._marquee_anchor = anchor
            if (event.state & 0x0004) == 0:
                self.selected = set()
            self._draw()

    def _on_drag(self, event):
        if self._marquee_anchor is None:
            return
        idx = self._row_at(event.y)
        idx = max(0, min(idx, len(self.rows) - 1)) if self.rows else 0
        lo, hi = sorted((self._marquee_anchor, idx))
        self.selected = set(range(lo, hi + 1))
        self._draw()

    def _on_right_click(self, event):
        self.focus_set()
        idx = self._row_at(event.y)
        if 0 <= idx < len(self.rows) and idx not in self.selected:
            self.selected = {idx}
            self._draw()
            self._hover(idx)
        if not self.selected:
            return
        indices = sorted(self.selected)
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="删除", command=lambda: self._delete_selected(indices))
        if self.on_open:
            menu.add_command(label=self.open_label, command=lambda: self.on_open(indices))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _delete_selected(self, indices):
        if self.on_delete:
            self.on_delete(list(indices))

    def _on_motion(self, event):
        idx = self._row_at(event.y)
        if 0 <= idx < len(self.rows):
            self._hover(idx)

    def sort_rows(self, by):
        """按序号(key)、格式(fmt)或文件名(text)排序，点击切换方向。"""
        if not self.rows:
            return
        if self._sort_col != by:
            self._sort_col = by
            self._sort_rev = False
        else:
            self._sort_rev = not self._sort_rev
        self._do_sort(by, self._sort_rev)

    def _do_sort(self, by, rev):
        """按指定列和方向应用排序（不切换方向）。"""
        if not self.rows:
            return
        if by == "key":
            values = [self._row_keys[i] for i in range(len(self.rows))]
        elif by == "fmt":
            values = [self._row_fmt(i).lower() for i in range(len(self.rows))]
        else:
            values = [self._row_sort_text(i).lower() for i in range(len(self.rows))]
        if len(set(values)) <= 1:
            return  # 该列所有值相同，点击不调整排序方式
        if by == "key":
            order = sorted(range(len(self.rows)), key=lambda i: self._row_keys[i], reverse=rev)
        elif by == "fmt":
            order = sorted(
                range(len(self.rows)),
                key=lambda i: (self._row_fmt(i).lower(), self._row_sort_text(i).lower()),
                reverse=rev,
            )
        else:
            order = sorted(
                range(len(self.rows)),
                key=lambda i: self._row_sort_text(i).lower(),
                reverse=rev,
            )
        new_rows = [self.rows[i] for i in order]
        new_keys = [self._row_keys[i] for i in order]
        pos_map = {old: new for new, old in enumerate(order)}
        self.selected = {pos_map[i] for i in self.selected if i in pos_map}
        self.checked = {pos_map[i] for i in self.checked if i in pos_map}
        self._hovered = pos_map.get(self._hovered)
        self.rows = new_rows
        self._row_keys = new_keys
        self._draw()

    def _row_fmt(self, i):
        """取行的格式值（扩展名）。"""
        row = self.rows[i]
        return row[0] if isinstance(row, tuple) else ""

    def _row_sort_text(self, i):
        """取用于排序的文本：去掉行首“N. ”序号前缀。"""
        text = self.rows[i]
        if isinstance(text, tuple):
            return str(text[1])
        head, sep, rest = text.partition(". ")
        if sep and head.isdigit():
            return rest
        return text

    def _fmt_width(self):
        """“格式”列宽度按内容自动计算，文字居中，不可调整。"""
        try:
            f = tkfont.nametofont("TkDefaultFont")
        except tk.TclError:
            f = tkfont.Font(family="Microsoft YaHei UI", size=9)
        maxw = 46
        for row in self.rows:
            fmt = row[0] if isinstance(row, tuple) else ""
            maxw = max(maxw, f.measure(fmt) + 14)
        return maxw

    def _hover(self, idx):
        if idx != self._hovered:
            self._hovered = idx
            if self.on_hover:
                self.on_hover(idx)

    def _on_arrow(self, event):
        """上下左右移动选择；Ctrl+方向键为追加选择。"""
        self.focus_set()
        if not self.rows:
            return "break"
        key = event.keysym
        delta = -1 if key in ("Up", "Left") else 1
        if self.selected:
            cur = max(self.selected)
        else:
            cur = -1 if delta < 0 else 0
        new = max(0, min(len(self.rows) - 1, cur + delta))
        if (event.state & 0x0004) != 0:
            self.selected.add(new)
        else:
            self.selected = {new}
        self._draw()
        self._hover(new)
        self._ensure_visible(new)
        return "break"

    def _ensure_visible(self, idx):
        """滚动让指定行进入可见区域（表头固定，行不会滚到表头下方）。"""
        if not (0 <= idx < len(self.rows)):
            return
        top = self._top_pad + idx * self.ROW_H
        bottom = top + self.ROW_H
        try:
            region = self.cget("scrollregion")
            _x0, _y0, _x1, y1 = [float(v) for v in region.split()]
        except Exception:
            return
        if y1 <= 0:
            return
        h = max(self.winfo_height(), 2)
        lo, _hi = self.yview()
        view_top = lo * y1
        if bottom > view_top + h:
            self.yview_moveto(min(1.0, max(0.0, (bottom - h) / y1)))
        elif top < view_top + self._top_pad:
            self.yview_moveto(max(0.0, (top - self._top_pad) / y1))
        self._draw()

    def selected_indices(self):
        return sorted(self.selected)

    def selected_keys(self):
        """返回选中行的稳定键（列表顺序）。"""
        return [self._row_keys[i] for i in sorted(self.selected) if 0 <= i < len(self._row_keys)]

    def select_keys(self, keys, scroll_frac=None):
        """按稳定键选中行，并可选恢复到指定滚动位置。"""
        self.selected = {self._row_keys.index(k) for k in keys if k in self._row_keys}
        if scroll_frac is not None:
            try:
                self.yview_moveto(float(scroll_frac))
            except (ValueError, tk.TclError):
                pass
        self._draw()

    def keys_for_indices(self, indices):
        """把行位置列表转换为稳定键（任务索引），越界行忽略。"""
        return [self._row_keys[i] for i in indices if 0 <= i < len(self._row_keys)]

    def delete_indices(self, indices):
        for i in sorted(indices, reverse=True):
            if 0 <= i < len(self.rows):
                del self.rows[i]
                del self._row_keys[i]
        self.selected.clear()
        self.checked.clear()
        self._hovered = None
        if self.on_hover:
            self.on_hover(None)
        self._draw()

    def _on_delete_key(self, _event):
        if self.selected and self.on_delete:
            self.on_delete(sorted(self.selected, reverse=True))
        return "break"

    def _on_space(self, _event=None):
        """空格：切换选中行最左侧的对勾（勾选/取消勾选）。"""
        if not self.checkable or not self.selected:
            return "break"
        for idx in list(self.selected):
            if idx in self.checked:
                self.checked.discard(idx)
            else:
                self.checked.add(idx)
        self._draw()
        return "break"

    def _draw(self):
        self.delete("all")
        w = max(self.winfo_width(), 2)
        fw = self._fmt_width() if (self.checkable and self._fmt_col) else 0
        if self._header_bg:
            hdr_fill = "white"
            arrow_fill = "white"
            box_outline = "#ffffff"
            overlay_bg = self._header_bg
        else:
            hdr_fill = "#44506a"
            arrow_fill = "#2f6fed"
            box_outline = "#7a8699"
            overlay_bg = "white"
        all_checked = bool(self.rows) and self.checkable and len(self.checked) == len(self.rows)
        y = self._top_pad
        for i, text in enumerate(self.rows):
            sel = i in self.selected
            fill = "#e3edff" if sel else "white"
            outline = "#2f6fed" if sel else "#c9d7ec"
            self.create_rectangle(
                4, y, w - 4, y + self.ROW_H - 4,
                fill=fill, outline=outline, width=2 if sel else 1,
            )
            tx = 10
            if self.checkable:
                self.create_rectangle(8, y + 4, 20, y + 16, fill="white", outline="#7a8699", width=1)
                if i in self.checked:
                    self.create_text(14, y + 10, text="✓", fill="#2f6fed")
                if self._number_col:
                    # 序号列：与表头“序号”对齐，加粗，无“.”后缀
                    self.create_text(
                        28, y + self.ROW_H // 2 - 2, text=str(self._row_keys[i] + 1),
                        anchor="w", fill="#1d2b44", font=("Microsoft YaHei UI", 9, "bold"),
                    )
                    tx = 84
                elif self._fmt_col:
                    fmt, name = text if isinstance(text, tuple) else ("", text)
                    # 格式列：居中，宽度自动，不可调整
                    self.create_text(
                        28 + fw // 2, y + self.ROW_H // 2 - 2, text=fmt,
                        anchor="center", fill="#1d2b44",
                    )
                    tx = 28 + fw + 8
                    text = name
                else:
                    tx = 26
            self.create_text(tx, y + self.ROW_H // 2 - 2, text=text, anchor="w", fill="#1d2b44")
            y += self.ROW_H
        if self.checkable:
            # 固定表头：按当前滚动偏移绘制，始终显示在视口顶部、不随滚动消失
            off = self._scroll_offset()
            self.create_rectangle(0, off, w, off + self._top_pad, fill=overlay_bg, outline="")
            self.create_rectangle(8, off + 4, 20, off + 16, fill="white", outline=box_outline, width=1)
            if all_checked:
                self.create_text(14, off + 10, text="✓", fill="#2f6fed")
            if self._number_col:
                self.create_text(
                    28, off + 10, text="序号", anchor="w", fill=hdr_fill,
                    font=("Microsoft YaHei UI", 9, "bold"),
                )
            elif self._fmt_col:
                self.create_text(
                    28 + fw // 2, off + 10, text="格式", anchor="center", fill=hdr_fill,
                    font=("Microsoft YaHei UI", 9, "bold"),
                )
            name_x = 28 + fw + 8 if self._fmt_col else 84
            self.create_text(
                name_x, off + 10, text="文件名", anchor="w", fill=hdr_fill,
                font=("Microsoft YaHei UI", 9, "bold"),
            )
            arrow = "▲" if not self._sort_rev else "▼"
            if self._sortable and self._sort_col == "key":
                self.create_text(52, off + 10, text=arrow, anchor="w", fill=arrow_fill)
            elif self._sortable and self._sort_col == "fmt":
                self.create_text(28 + fw // 2 + 22, off + 10, text=arrow, anchor="w", fill=arrow_fill)
            elif self._sortable and self._sort_col == "text":
                ax = name_x + 50 if self._fmt_col else 134
                self.create_text(ax, off + 10, text=arrow, anchor="w", fill=arrow_fill)
        self.configure(scrollregion=(0, 0, w, max(y + 4, self.winfo_height())))


def make_checkbutton(parent, text, var, bg=APP_BG, fg="#1d2b44"):
    """原生 tk 复选框：选中时显示 ✓（而非 ×）。"""
    return tk.Checkbutton(
        parent,
        text=text,
        variable=var,
        bg=bg,
        fg=fg,
        activebackground=bg,
        activeforeground=fg,
        selectcolor="white",
        anchor="w",
        bd=0,
        highlightthickness=0,
        font=("Microsoft YaHei UI", 9),
        cursor="hand2",
    )


class ThumbScrollbar(tk.Canvas):
    """自绘滚动条：滑块为实心深色圆角块，始终可见；支持点击翻页与拖动。"""

    def __init__(
        self,
        master,
        command=None,
        width=16,
        track="#e9eef6",
        thumb="#5a6b82",
        thumb_active="#3d4a5d",
    ):
        super().__init__(
            master,
            width=width,
            height=10,
            bg=track,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.command = command
        self.track_color = track
        self.thumb_color = thumb
        self.thumb_active = thumb_active
        self._lo = 0.0
        self._hi = 1.0
        self._dragging = False
        self._drag_offset_px = 0
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Button-1>", self._on_click)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", lambda _e: self._set_drag(False))

    def set(self, lo, hi):
        try:
            lo, hi = float(lo), float(hi)
        except (TypeError, ValueError):
            return
        self._lo = lo
        self._hi = hi
        self._draw()

    def _thumb_rect(self):
        h = max(self.winfo_height(), 2)
        span = h - 6
        size = max(26, (self._hi - self._lo) * span)
        y0 = 3 + self._lo * span
        y1 = min(h - 3, y0 + size)
        return y0, y1

    def _draw(self):
        self.delete("all")
        w = max(self.winfo_width(), 2)
        self.configure(bg=self.track_color)
        if self._hi - self._lo >= 0.995:
            return  # 内容未超出，不画滑块
        y0, y1 = self._thumb_rect()
        fill = self.thumb_active if self._dragging else self.thumb_color
        # 胶囊形滑块：中间矩形 + 上下两个半圆
        x0, x1 = 2, w - 2
        r = (x1 - x0) / 2
        self.create_rectangle(x0, y0 + r, x1, y1 - r, fill=fill, outline="")
        self.create_oval(x0, y0, x1, y0 + 2 * r, fill=fill, outline="")
        self.create_oval(x0, y1 - 2 * r, x1, y1, fill=fill, outline="")

    def _on_click(self, event):
        y0, y1 = self._thumb_rect()
        if y0 <= event.y <= y1:
            self._set_drag(True)
            self._drag_offset_px = event.y - y0
        elif event.y < y0:
            if self.command:
                self.command("scroll", "-1", "pages")
        else:
            if self.command:
                self.command("scroll", "1", "pages")

    def _on_drag(self, event):
        if not self._dragging:
            return
        h = max(self.winfo_height(), 2)
        span = h - 6
        new_lo = (event.y - self._drag_offset_px - 3) / span
        new_lo = max(0.0, min(1.0, new_lo))
        if self.command:
            self.command("moveto", str(new_lo))

    def _set_drag(self, on):
        self._dragging = on
        self._draw()


def lang_display(cfg):
    return cfg_mod.LANG_NAMES.get(cfg, cfg)


def log_time():
    return time.strftime("%H:%M:%S")


def plain_error(message):
    """把技术性错误翻译成白话提示。"""
    m = str(message).lower()
    if "429" in m or "too many" in m or "rate limit" in m:
        return "翻译源限流（请求太频繁），请稍后重试或更换翻译源"
    if "timeout" in m or "timed out" in m:
        return "请求超时，请检查网络或代理"
    if "connection" in m or "连接被" in m or "无法直连" in m or "reset" in m or "aborted" in m:
        return "网络连接失败，请检查代理或网络设置"
    if "401" in m or "403" in m or "unauthorized" in m or "没有权限" in m or "invalid key" in m:
        return "API Key 无效或没有权限，请检查密钥"
    if "未配置" in m and ("api key" in m or "密钥" in m or "appid" in m):
        return "未配置 API Key，请到“管理翻译源”填写"
    if "invalid source language" in m or "autodetect" in m:
        return "该翻译源不支持自动检测源语言，请选择具体源语言"
    if "404" in m or "not found" in m:
        return "接口地址有误，请检查翻译源配置"
    return "翻译失败，请检查网络或翻译源设置"


class FileTranslatorApp:
    def __init__(self, root):
        self.root = root
        setup_styles()
        root.configure(bg=APP_BG)
        self._apply_icon()
        self.cfg = cfg_mod.load_config()
        cfg_mod.ensure_ai_providers(self.cfg)
        try:
            glossary_mod.ensure_glossary_file()
            glossary_mod.ensure_glossary_structure()
            if self.cfg.get("glossary", {}).get("files") is None:
                # 首次运行：默认勾选词库目录下的全部文件（含两个 GitHub 词库）
                self.cfg["glossary"]["files"] = sorted(info["rel"] for info in glossary_mod.scan_glossary_files())
                cfg_mod.save_config(self.cfg)
        except Exception:
            pass
        self.queue = queue.Queue()
        self.worker = None
        self.stop_flag = threading.Event()
        self.plan = []
        self.iid_to_index = {}
        self._stream_index = 0
        self.disabled_indices = set()
        self.removed_indices = set()
        self._tree_history = []
        self._tree_redo = []
        self._cell_labels = {}
        self._cell_refresh_scheduled = False
        self._tree_editor_entry = None
        self._tree_drag_anchor = None
        self._sel_bg = "#c9d7ec"
        self._sort_state = {}
        self.last_applied = []
        self.engine_display_to_key = {}
        self.busy = False
        self._log_lines = []
        self._log_window = None
        self._selected_files = []
        self._files_history = []
        self._files_redo = []
        self._tasks = []
        self._tasks_history = []
        self._tasks_redo = []
        self.translate_paused = False
        self.pause_flag = threading.Event()
        self.last_undone = []

        root.title("文件名翻译器")
        root.minsize(1100, 900)
        self._build_ui()
        self._refresh_engine_combo()
        self._restore_state()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ================================================================ 界面构建
    def _build_ui(self):
        root = self.root
        pad = {"padx": 6, "pady": 3}

        # ---- 主体：左设置 + 右预览
        main = ttk.Frame(root)
        main.pack(fill="both", expand=True, padx=8, pady=(2, 4))
        left = ttk.Frame(main, width=630)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)
        right = ttk.Frame(main)
        right.pack(side="left", fill="both", expand=True)

        # ---- 左列第一行：选择文件夹（置顶）
        top = ttk.Frame(left, padding=(6, 2))
        top.pack(fill="x")
        self.folder_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.folder_var, font=("Microsoft YaHei UI", 10)).pack(
            side="left", fill="x", expand=True, padx=(0, 6)
        )
        RoundedButton(top, "选择文件夹", self._pick_folder, style="gray").pack(side="left", padx=2)
        self.recursive_var = tk.BooleanVar(value=True)  # 每次打开默认勾选“子文件夹”
        make_checkbutton(top, "子文件夹", self.recursive_var).pack(side="left", padx=(8, 0))

        # ---- 左列第二行：文件类型（紧贴文件夹行）
        ttk.Label(
            left,
            text="扩展名用英文逗号分隔；* 表示全部文件",
            foreground="#888888",
            wraplength=450,
            justify="left",
        ).pack(anchor="w", padx=4)
        ext_frame = ttk.Frame(left, padding=(6, 2))
        ext_frame.pack(fill="x")
        self.ext_text = tk.Text(
            ext_frame,
            height=3,
            width=24,
            font=("Microsoft YaHei UI", 10),
            wrap="char",
            bg="white",
            relief="solid",
            bd=1,
            highlightthickness=0,
        )
        self.ext_text.pack(
            side="left", fill="both", expand=True, padx=(0, 4)
        )
        ext_vsb = ThumbScrollbar(ext_frame, command=self.ext_text.yview)
        self.ext_text.configure(yscrollcommand=ext_vsb.set)
        ext_vsb.pack(side="left", fill="y", padx=(0, 4))
        self.preset_var = tk.StringVar(value="全部文件")
        self._set_extensions("*")
        preset_box = ttk.Combobox(
            ext_frame,
            textvariable=self.preset_var,
            values=list(EXTENSION_PRESETS.keys()),
            state="readonly",
            width=12,
        )
        preset_box.pack(side="left", padx=2)
        preset_box.bind("<<ComboboxSelected>>", self._apply_extension_preset)

        # ---- 左列第三行：文件（可多选，框选列表，DEL 删除）
        ttk.Label(
            left,
            text="Ctrl+A 全选 · Ctrl+Z/Y 撤销重做 · 空格勾选 · Del 删除",
            foreground="#888888",
            wraplength=450,
            justify="left",
        ).pack(anchor="w", padx=4)
        files_frame = ttk.Frame(left, padding=(6, 2))
        files_frame.pack(fill="x", pady=(6, 0))
        self.files_list = RowList(
            files_frame,
            on_delete=self._on_files_delete,
            on_open=self._on_files_open,
            height_rows=12,
            width=280,
            checkable=True,
            number_col=False,
            fmt_col=True,
            sortable=True,
            header_bg=PRIMARY,
            ctrl_toggles_check=False,
        )
        self.files_list.pack(side="left", fill="both", expand=True, padx=(0, 4))
        files_vsb = ThumbScrollbar(
            files_frame,
            command=lambda *a: (self.files_list.yview(*a), self.files_list._draw()),
        )
        self.files_list.configure(yscrollcommand=files_vsb.set)
        files_vsb.pack(side="left", fill="y", padx=(0, 4))
        self.files_list.bind("<Double-1>", self._on_files_double_click)
        self.files_list.bind("<Return>", self._on_files_enter)
        self.files_list.bind("<Control-a>", self._on_files_select_all)
        self.files_list.bind("<Control-A>", self._on_files_select_all)
        self.files_list.bind("<Control-z>", self._on_files_undo)
        self.files_list.bind("<Control-Z>", self._on_files_redo)
        self.files_list.bind("<Control-y>", self._on_files_redo)
        files_right = ttk.Frame(files_frame)
        files_right.pack(side="left", fill="y", anchor="n")
        self.files_count_var = tk.StringVar(value="")
        ttk.Label(files_right, textvariable=self.files_count_var, foreground=PRIMARY).pack(anchor="w", pady=(2, 4))
        RoundedButton(files_right, "选择文件", self._pick_files, style="gray", height=44).pack(anchor="w")
        RoundedButton(files_right, "添加任务", self._add_task, style="green", height=44).pack(anchor="w", pady=(6, 0))

        # ---- 左列第四行：翻译设置
        trans = ttk.Frame(left, padding=(6, 2))
        trans.pack(fill="x")

        ttk.Label(trans, text="翻译源:", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, sticky="w", **pad)
        self.engine_var = tk.StringVar()
        self.engine_box = ttk.Combobox(trans, textvariable=self.engine_var, state="readonly", width=14)
        self.engine_box.grid(row=0, column=1, sticky="w", **pad)
        RoundedButton(trans, "管理翻译源...", self._open_settings, style="gray").grid(row=0, column=2, **pad)

        ttk.Label(trans, text="源语言:", font=("Microsoft YaHei UI", 11, "bold")).grid(row=1, column=0, sticky="w", **pad)
        self.source_summary_var = tk.StringVar(value="")
        ttk.Label(trans, textvariable=self.source_summary_var, foreground=PRIMARY, font=("Microsoft YaHei UI", 9, "bold")).grid(
            row=1, column=1, sticky="w", **pad
        )
        RoundedButton(trans, "选择源语言...", self._open_source_langs, style="gray").grid(row=1, column=2, **pad)
        ttk.Label(trans, text="目标语言:", font=("Microsoft YaHei UI", 11, "bold")).grid(row=2, column=0, sticky="w", **pad)
        self.target_var = tk.StringVar()
        target_box = ttk.Combobox(
            trans,
            textvariable=self.target_var,
            values=[cfg_mod.LANG_NAMES[c] for c, _ in cfg_mod.LANGUAGES],
            state="readonly",
            width=12,
        )
        target_box.grid(row=2, column=1, sticky="w", **pad)
        RoundedButton(trans, "跳过语言...", self._open_skip_langs, style="gray").grid(row=2, column=2, **pad)
        self.skip_lang_summary_var = tk.StringVar(value="")
        ttk.Label(
            trans,
            textvariable=self.skip_lang_summary_var,
            foreground=PRIMARY,
            font=("Microsoft YaHei UI", 9, "bold"),
        ).grid(row=2, column=3, sticky="w", **pad)
        self.skip_var = tk.BooleanVar(value=bool(self.cfg.get("skip_target", True)))
        make_checkbutton(trans, "跳过已经属于目标语言的文件（如已是中文的文件）", self.skip_var).grid(
            row=3, column=0, columnspan=3, sticky="w", **pad
        )
        self.glossary_enabled_var = tk.BooleanVar(value=bool(self.cfg.get("glossary", {}).get("enabled", True)))
        make_checkbutton(trans, "启用自定义词库（与云端翻译配合，词库优先）", self.glossary_enabled_var).grid(
            row=4, column=0, columnspan=2, sticky="w", **pad
        )
        RoundedButton(trans, "管理词库...", lambda: self._open_settings("glossary"), style="gray").grid(row=4, column=2, **pad)

        # ---- 任务队列（翻译设置下方，至少 8 行，DEL 删除选中任务）
        task_frame = ttk.Frame(left, padding=(6, 2))
        task_frame.pack(fill="x", pady=(6, 0))
        ttk.Label(task_frame, text="任务队列", foreground="#555", font=("Microsoft YaHei UI", 9, "bold")).pack(anchor="w")
        ttk.Label(
            task_frame,
            text="Ctrl+Z/Y 撤销重做 · 回车/双击查看任务 · 空格勾选 · Del 删除",
            foreground="#888888",
        ).pack(anchor="w", pady=(0, 2))
        self.task_list = RowList(
            task_frame,
            on_delete=self._on_tasks_delete,
            on_open=self._on_tasks_open,
            open_label="打开文件夹",
            height_rows=8,
            width=300,
            checkable=True,
            number_col=True,
            sortable=True,
            header_bg=PRIMARY,
        )
        self.task_list.pack(side="left", fill="both", expand=True, padx=(0, 4))
        task_vsb = ThumbScrollbar(
            task_frame,
            command=lambda *a: (self.task_list.yview(*a), self.task_list._draw()),
        )
        self.task_list.configure(yscrollcommand=task_vsb.set)
        task_vsb.pack(side="right", fill="y")
        self.task_list.bind("<Double-1>", self._on_tasks_double_click)
        self.task_list.bind("<Return>", self._on_tasks_enter)
        self.task_list.bind("<Control-z>", self._on_tasks_undo)
        self.task_list.bind("<Control-Z>", self._on_tasks_redo)
        self.task_list.bind("<Control-y>", self._on_tasks_redo)

        self.root.bind("<Control-z>", self._on_shortcut_undo)
        self.root.bind("<Control-y>", self._on_shortcut_redo)

        # ---- 右列：操作按钮
        actions = ttk.Frame(right)
        actions.pack(fill="x", pady=(0, 4))
        self.preview_btn = PlayPauseButton(actions, command=self._play_btn_click, size=52)
        self.preview_btn.pack(side="left", padx=(0, 6))
        self.rename_btn = RoundedButton(actions, "保存修改", self._confirm_rename, style="blue", state="disabled")
        self.rename_btn.pack(side="left", padx=4)
        self.undo_btn = RoundedButton(actions, "取消修改", self._confirm_undo, style="orange", state="disabled")
        self.undo_btn.pack(side="left", padx=4)
        self.clear_btn = RoundedButton(actions, "清空列表", self._clear_list, style="gray")
        self.clear_btn.pack(side="left", padx=4)

        # ---- 右列：状态与进度（紧跟按钮，置顶）
        progress_frame = ttk.Frame(right)
        progress_frame.pack(fill="x", pady=(0, 4))
        self.status_var = tk.StringVar(value="就绪。选择文件夹后点击“重命名”开始翻译。")
        ttk.Label(progress_frame, textvariable=self.status_var).pack(side="left")
        self.progress = ttk.Progressbar(progress_frame, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=8)

        # ---- 右列：预览表格
        ttk.Label(
            right,
            text="翻译框快捷键：空格勾选 · Ctrl+点击多选 · Del/右键移除队列 · 回车打开位置 · Ctrl+Z/Y 撤销重做",
            foreground="#888888",
        ).pack(anchor="w")
        table_frame = ttk.LabelFrame(right, text="", padding=4)
        table_frame.pack(fill="both", expand=True, pady=(0, 4))
        columns = ("sel", "old", "new")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
        self.tree.heading("sel", text="选择")
        self.tree.heading("old", text="原文件名")
        self.tree.heading("new", text="新文件名")
        self.tree.column("sel", width=46, anchor="center", stretch=False)
        self.tree.column("old", width=280, anchor="w")
        self.tree.column("new", width=300, anchor="w")
        try:
            mapped = ttk.Style().map("Treeview", "background") or []
            for states, color in mapped:
                if "selected" in states and color:
                    self._sel_bg = color
                    break
        except Exception:
            pass
        vsb = ThumbScrollbar(table_frame, command=self.tree.yview)
        self.tree.configure(yscrollcommand=lambda lo, hi: (vsb.set(lo, hi), self._refresh_cell_labels()))
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<Button-3>", self._on_tree_right_click)
        self.tree.bind("<space>", self._on_tree_space)
        self.tree.bind("<Return>", self._on_tree_enter)
        self.tree.bind("<Delete>", self._on_tree_delete)
        self.tree.bind("<Control-z>", self._on_tree_undo)
        self.tree.bind("<Control-Z>", self._on_tree_redo)
        self.tree.bind("<Control-y>", self._on_tree_redo)
        self.tree.bind("<Configure>", lambda _e: self._refresh_cell_labels())
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._refresh_cell_labels())

        # ---- 右列：命名规则提示
        ttk.Label(
            right,
            text="命名规则：仅翻译文件名主体，保留扩展名；重名自动追加 (2)；非法字符自动清理。",
            foreground="#888888",
            justify="left",
            wraplength=620,
        ).pack(anchor="w")

        # ---- 底部右下角：版本号 + GitHub 版权链接
        bottom_bar = ttk.Frame(root)
        bottom_bar.pack(fill="x", padx=10, pady=(4, 6))
        RoundedButton(bottom_bar, "日志", self._open_log, style="gray").pack(side="right", padx=(0, 10))
        self.github_img = None
        gp = self._find_asset("github.png")
        if gp:
            try:
                self.github_img = tk.PhotoImage(file=gp)
                gh_icon = tk.Label(bottom_bar, image=self.github_img, bg=APP_BG, cursor="hand2")
                gh_icon.pack(side="right")
                gh_icon.bind(
                    "<Button-1>",
                    lambda _e: webbrowser.open("https://github.com/yiming2016/File-Name-Conversion"),
                )
            except tk.TclError:
                self.github_img = None
        gh_link = tk.Label(
            bottom_bar,
            text="@yiming2016",
            fg="#0645ad",
            cursor="hand2",
            font=("Microsoft YaHei UI", 9, "underline"),
            bg=APP_BG,
        )
        gh_link.pack(side="right", padx=(2, 2))
        gh_link.bind(
            "<Button-1>",
            lambda _e: webbrowser.open("https://github.com/yiming2016/File-Name-Conversion"),
        )
        tk.Label(bottom_bar, text=f"v{APP_VERSION}", fg="#666666", bg=APP_BG).pack(side="right", padx=(0, 8))

        self.root.after(80, self._poll)

    # ================================================================ 图标与资源
    def _find_asset(self, name):
        for p in (
            os.path.join(cfg_mod.get_app_dir(), name),
            os.path.join(cfg_mod.get_app_dir(), "app", name),
        ):
            if os.path.exists(p):
                return p
        return None

    def _apply_icon(self):
        # 优先使用用户提供的 logo.ico（exe 图标一致）
        for p in (
            os.path.join(cfg_mod.get_app_dir(), "logo.ico"),
            os.path.join(cfg_mod.get_app_dir(), "app", "logo.ico"),
        ):
            if os.path.exists(p):
                try:
                    self.root.iconbitmap(default=p)
                    return
                except tk.TclError:
                    pass
        # 回退：logo.png
        p = self._find_asset("logo.png")
        if not p:
            return
        try:
            img = tk.PhotoImage(file=p)
            self.root.iconphoto(True, img)
            self.root._icon_ref = img
        except tk.TclError:
            pass

    # ================================================================ 状态恢复
    def _restore_state(self):
        self.folder_var.set(self.cfg.get("last_folder", ""))
        self._selected_files = [p for p in split_targets(self.cfg.get("last_files", "")) if os.path.isfile(p)]
        self._refresh_files_list()
        self.source_summary_var.set(self._source_summary(self.cfg.get("source_langs") or ["auto"]))
        self.target_var.set(lang_display(self.cfg.get("target_lang", "zh-CN")))
        self.skip_lang_summary_var.set(self._skip_summary(self.cfg.get("skip_langs") or []))
        try:
            w, h = self.cfg.get("window_size", [1500, 1050])
            self.root.geometry(f"{w}x{h}")
        except Exception:
            pass
        center_window(self.root)

    def _save_runtime_state(self):
        self.cfg["recursive"] = bool(self.recursive_var.get())
        self.cfg["extensions"] = self._get_extensions() or "*"
        self.cfg["source_langs"] = list(self.cfg.get("source_langs") or ["auto"])
        self.cfg["source_lang"] = self.cfg["source_langs"][0] if self.cfg["source_langs"] else "auto"
        self.cfg["target_lang"] = self._lang_code(self.target_var.get())
        self.cfg["skip_langs"] = list(self.cfg.get("skip_langs") or [])
        self.cfg["skip_target"] = bool(self.skip_var.get())
        self.cfg["glossary"]["enabled"] = bool(self.glossary_enabled_var.get())
        self.cfg["last_folder"] = self.folder_var.get().strip()
        self.cfg["last_files"] = ";".join(self._selected_files)
        try:
            self.cfg["window_size"] = [self.root.winfo_width(), self.root.winfo_height()]
        except Exception:
            pass

    def _lang_code(self, display):
        for code, name in cfg_mod.LANGUAGES:
            if name == display:
                return code
        return "auto"

    def _source_summary(self, langs):
        langs = langs or ["auto"]
        if "auto" in langs:
            return "自动检测（全部语言）"
        return "、".join(cfg_mod.LANG_NAMES.get(c, c) for c in langs)

    def _open_source_langs(self):
        """源语言多选弹窗：可滚动、勾选实时显示、自动检测与具体语言互斥。"""
        current = set(self.cfg.get("source_langs") or ["auto"])
        dlg = tk.Toplevel(self.root)
        dlg.title("选择源语言（可多选）")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.configure(bg=APP_BG)
        # 默认高度：屏幕够高时给 640，小屏幕自动压缩，保证窗口完整可见
        screen_h = dlg.winfo_screenheight()
        default_h = min(640, max(460, screen_h - 160))
        dlg.geometry(f"400x{default_h}")
        dlg.minsize(380, 460)
        dlg.update_idletasks()
        w, h = dlg.winfo_width(), dlg.winfo_height()
        x = max(0, (self.root.winfo_screenwidth() - w) // 2)
        y = max(0, (self.root.winfo_screenheight() - h) // 2)
        # 窗口不能超出屏幕底部（否则底部按钮被顶出屏幕）
        y = max(0, min(y, self.root.winfo_screenheight() - h - 8))
        dlg.geometry(f"+{x}+{y}")
        dlg.lift()
        dlg.focus_force()

        header = ttk.Frame(dlg)
        header.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(header, text="选择需要翻译的源语言（可多选）：").pack(anchor="w")
        self._src_live_var = tk.StringVar(value="")
        ttk.Label(
            header,
            textvariable=self._src_live_var,
            foreground=PRIMARY,
            font=("Microsoft YaHei UI", 9, "bold"),
        ).pack(anchor="w", pady=(4, 0))

        body = ttk.Frame(dlg)
        body.pack(fill="both", expand=True, padx=(10, 0), pady=4)
        canvas = tk.Canvas(body, bg="white", highlightthickness=1, highlightbackground="#b9cbea")
        scroll = ThumbScrollbar(body, command=canvas.yview)
        inner = tk.Frame(canvas, bg="white")
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win_id, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        # 先 pack 滚动条（靠右），再 pack 画布，保证滚动条一定可见
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # 鼠标滚轮滚动（事件冒泡到弹窗，覆盖列表与复选框区域）
        def on_wheel(event):
            if canvas.yview()[0] == 0.0 and event.delta > 0:
                return
            canvas.yview_scroll(int(-event.delta / 120), "units")

        dlg.bind("<MouseWheel>", on_wheel)

        vars_map = {}
        options = [("auto", "自动检测（全部语言）")] + [
            (code, name) for code, name in cfg_mod.LANGUAGES if code != "auto"
        ]

        def refresh(clicked=None):
            """勾选后实时刷新摘要；自动检测与具体语言互斥（不能同时勾选）。"""
            if clicked == "auto":
                for code, var in vars_map.items():
                    if code != "auto":
                        var.set(False)
            elif clicked and clicked != "auto":
                vars_map["auto"].set(False)
            selected = [code for code, var in vars_map.items() if var.get()]
            if selected:
                self._src_live_var.set("当前选择：" + self._source_summary(selected))
            else:
                self._src_live_var.set("当前选择：未选择任何语言")

        for code, name in options:
            var = tk.BooleanVar(value=code in current)
            vars_map[code] = var
            cb = make_checkbutton(inner, name, var, bg="white")
            cb.config(command=lambda c=code: refresh(c))
            cb.pack(anchor="w", padx=8, pady=1)
        refresh()

        bottom = ttk.Frame(dlg)
        bottom.pack(fill="x", padx=10, pady=8)

        def ok():
            selected = [code for code, var in vars_map.items() if var.get()]
            if not selected:
                messagebox.showwarning("提示", "请至少选择一种源语言。", parent=dlg)
                return
            self.cfg["source_langs"] = selected
            self.source_summary_var.set(self._source_summary(selected))
            dlg.destroy()

        RoundedButton(bottom, "确定", ok, style="blue").pack(side="right", padx=4)
        RoundedButton(bottom, "取消", dlg.destroy, style="gray").pack(side="right", padx=4)

    def _open_skip_langs(self):
        """跳过语言多选弹窗：翻译时检测到这些源语言的文件会被跳过。"""
        current = set(self.cfg.get("skip_langs") or [])
        dlg = tk.Toplevel(self.root)
        dlg.title("选择跳过语言（可多选，不选则不过滤）")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.configure(bg=APP_BG)
        screen_h = dlg.winfo_screenheight()
        default_h = min(600, max(420, screen_h - 180))
        dlg.geometry(f"400x{default_h}")
        dlg.minsize(380, 420)
        dlg.update_idletasks()
        w, h = dlg.winfo_width(), dlg.winfo_height()
        x = max(0, (self.root.winfo_screenwidth() - w) // 2)
        y = max(0, (self.root.winfo_screenheight() - h) // 2)
        y = max(0, min(y, self.root.winfo_screenheight() - h - 8))
        dlg.geometry(f"+{x}+{y}")
        dlg.lift()
        dlg.focus_force()

        header = ttk.Frame(dlg)
        header.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(
            header,
            text="翻译时检测到属于这些语言的文件会被跳过（不翻译、不改名）：",
        ).pack(anchor="w")
        self._skip_live_var = tk.StringVar(value="")
        ttk.Label(
            header,
            textvariable=self._skip_live_var,
            foreground=PRIMARY,
            font=("Microsoft YaHei UI", 9, "bold"),
        ).pack(anchor="w", pady=(4, 0))

        body = ttk.Frame(dlg)
        body.pack(fill="both", expand=True, padx=(10, 0), pady=4)
        canvas = tk.Canvas(body, bg="white", highlightthickness=1, highlightbackground="#b9cbea")
        scroll = ThumbScrollbar(body, command=canvas.yview)
        inner = tk.Frame(canvas, bg="white")
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win_id, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        def on_wheel(event):
            if canvas.yview()[0] == 0.0 and event.delta > 0:
                return
            canvas.yview_scroll(int(-event.delta / 120), "units")

        dlg.bind("<MouseWheel>", on_wheel)

        vars_map = {}
        options = [(code, name) for code, name in cfg_mod.LANGUAGES if code != "auto"]
        for code, name in options:
            var = tk.BooleanVar(value=code in current)
            vars_map[code] = var
            cb = make_checkbutton(inner, name, var, bg="white")
            cb.config(command=lambda: self._skip_live_var.set("当前选择：" + self._skip_summary(
                [c for c, v in vars_map.items() if v.get()]
            )))
            cb.pack(anchor="w", padx=8, pady=1)

        def refresh():
            self._skip_live_var.set("当前选择：" + self._skip_summary(
                [code for code, var in vars_map.items() if var.get()]
            ))

        refresh()

        bottom = ttk.Frame(dlg)
        bottom.pack(fill="x", padx=10, pady=8)

        def ok():
            selected = [code for code, var in vars_map.items() if var.get()]
            self.cfg["skip_langs"] = selected
            self.skip_lang_summary_var.set(self._skip_summary(selected))
            cfg_mod.save_config(self.cfg)
            dlg.destroy()

        RoundedButton(bottom, "确定", ok, style="blue").pack(side="right", padx=4)
        RoundedButton(bottom, "取消", dlg.destroy, style="gray").pack(side="right", padx=4)

    def _skip_summary(self, langs):
        """跳过语言的摘要文字。"""
        if not langs:
            return "跳过语言：无"
        names = [cfg_mod.LANG_NAMES.get(c, c) for c in langs]
        return "跳过语言：" + "、".join(names)

    def _refresh_engine_combo(self):
        choices = engine_choices(self.cfg)
        self.engine_display_to_key = {display: key for key, display in choices}
        displays = [display for _key, display in choices]
        self.engine_box["values"] = displays
        current = self.cfg.get("engine", "google")
        display = next((d for k, d in choices if k == current), None)
        if display is None and displays:
            display = displays[0]
        self.engine_var.set(display)

    # ================================================================ 事件处理
    def _pick_folder(self):
        folder = filedialog.askdirectory(initialdir=self.folder_var.get() or os.path.expanduser("~"))
        if folder:
            self.folder_var.set(folder)
            # 重新选择文件夹时，始终用新文件夹内匹配的文件刷新文件框，
            # 避免出现“新文件夹路径 + 旧文件列表”不一致
            try:
                paths, _invalid = discover_entries(
                    folder,
                    bool(self.recursive_var.get()),
                    self._get_extensions(),
                )
                self._push_files_history()
                self._selected_files = list(paths)
                self._refresh_files_list()
            except OSError:
                pass

    def _pick_files(self):
        initial = os.path.expanduser("~")
        folder = self.folder_var.get().strip()
        if os.path.isdir(folder):
            initial = folder
        elif self._selected_files:
            first = self._selected_files[0]
            initial = os.path.dirname(first) or initial
        files = filedialog.askopenfilenames(
            title="选择要翻译的文件（可多选）",
            initialdir=initial,
        )
        if files:
            self._push_files_history()
            self._selected_files = list(dict.fromkeys(files))  # 去重保序
            # 自动填入上方“选择文件夹”：所有文件同目录则用该目录，否则用第一个文件的目录
            dirs = {os.path.dirname(f) for f in files}
            target_dir = dirs.pop() if len(dirs) == 1 else os.path.dirname(files[0])
            self.folder_var.set(target_dir)
            self._refresh_files_list()

    def _update_files_count(self):
        self.files_count_var.set(f"{len(self._selected_files)} 个文件")

    def _refresh_files_list(self):
        """在文件列表里每行显示：勾选框 + 格式 + 文件名（不含扩展名）。"""
        rows = []
        for f in self._selected_files:
            base = os.path.basename(f)
            stem, ext = os.path.splitext(base)
            rows.append((ext, stem))
        self.files_list.set_rows(rows, keys=list(range(len(self._selected_files))))
        self.files_list.set_checked(list(range(len(self._selected_files))))
        self._update_files_count()

    def _push_files_history(self):
        self._files_history.append((
            list(self._selected_files),
            self.files_list.checked_indices(),
            self.files_list.selected_keys(),
            self.files_list.yview()[0],
        ))
        if len(self._files_history) > 50:
            self._files_history.pop(0)
        self._files_redo.clear()

    def _on_files_delete(self, indices):
        keys = self.files_list.keys_for_indices(indices)
        if not keys:
            return
        rows_before = len(self.files_list.rows)
        base = max(indices) if indices else 0
        # 删除后自动选中“下方一项”；若删除的是最后一项则选中“上方一项”
        target_path = None
        if base + 1 < rows_before:
            k = self.files_list._row_keys[base + 1]
            if 0 <= k < len(self._selected_files):
                target_path = self._selected_files[k]
        elif base - 1 >= 0:
            k = self.files_list._row_keys[base - 1]
            if 0 <= k < len(self._selected_files):
                target_path = self._selected_files[k]
        self._push_files_history()
        for k in sorted(keys, reverse=True):
            if 0 <= k < len(self._selected_files):
                del self._selected_files[k]
        self._refresh_files_list()
        if target_path is not None:
            try:
                pos = self._selected_files.index(target_path)
            except ValueError:
                return
            self.files_list.selected = {pos}
            self.files_list._draw()

    def _on_files_double_click(self, event):
        """双击文件行：等同于打开文件所在位置。"""
        if event.x < 26:
            return
        idx = self.files_list._row_at(event.y)
        keys = self.files_list.keys_for_indices([idx])
        if keys:
            self._on_files_open(keys)

    def _on_files_enter(self, _event=None):
        """文件框按回车：打开选中文件所在位置。"""
        sel = sorted(self.files_list.selected)
        if not sel:
            return "break"
        keys = self.files_list.keys_for_indices(sel)
        if keys:
            self._on_files_open(keys)
        return "break"

    def _on_files_select_all(self, _event=None):
        self.files_list.check_all(True)
        return "break"

    def _on_files_undo(self, _event=None):
        """文件列表 Ctrl+Z：撤销上一次增删文件操作。"""
        if not self._files_history:
            return "break"
        state = self._files_history.pop()
        self._files_redo.append((
            list(self._selected_files),
            self.files_list.checked_indices(),
            self.files_list.selected_keys(),
            self.files_list.yview()[0],
        ))
        self._selected_files = list(state[0])
        self._refresh_files_list()
        self.files_list.set_checked(state[1])
        self.files_list.select_keys(state[2], state[3])
        return "break"

    def _on_files_redo(self, _event=None):
        """文件列表 Ctrl+Y / Ctrl+Shift+Z：重做被撤销的操作。"""
        if not self._files_redo:
            return "break"
        state = self._files_redo.pop()
        self._files_history.append((
            list(self._selected_files),
            self.files_list.checked_indices(),
            self.files_list.selected_keys(),
            self.files_list.yview()[0],
        ))
        self._selected_files = list(state[0])
        self._refresh_files_list()
        self.files_list.set_checked(state[1])
        self.files_list.select_keys(state[2], state[3])
        return "break"

    def _on_files_open(self, indices):
        if not indices:
            return
        paths = [self._selected_files[i] for i in indices if 0 <= i < len(self._selected_files)]
        if not paths:
            return
        if len(paths) == 1:
            subprocess.Popen(["explorer", "/select,", os.path.normpath(paths[0])])
        else:
            subprocess.Popen(["explorer", os.path.normpath(os.path.dirname(paths[0]))])

    def _add_task(self):
        folder = self.folder_var.get().strip()
        if not self._selected_files:
            show_error_dialog(self.root, "添加失败", "当前没有文件，请先选择文件夹或选择文件。")
            return
        checked_keys = self.files_list.checked_indices()
        files = [self._selected_files[i] for i in checked_keys if 0 <= i < len(self._selected_files)]
        if not files:
            show_error_dialog(self.root, "添加失败", "当前没有勾选文件，请先勾选要翻译的文件。")
            return
        self._push_files_history()
        self._push_tasks_history()
        self._tasks.append(
            {
                "folder": folder,
                "files": files,
            }
        )
        self._refresh_tasks()
        self.task_list.set_checked(list(range(len(self._tasks))))
        self._log(f"添加任务：{folder or '（仅文件）'}（{len(files)} 个文件）")
        self._refresh_play_button()
        # 清空文件选择，便于添加下一个任务
        self._selected_files = []
        self._refresh_files_list()

    def _refresh_tasks(self):
        rows = []
        for i, t in enumerate(self._tasks, 1):
            folder = t.get("folder", "")
            files = t.get("files", [])
            n = len(files)
            incl = t.get("checked")
            sel = len(incl) if incl else n
            if folder:
                label = os.path.basename(folder.rstrip("/\\")) or folder
            else:
                label = "仅文件"
            rows.append(f"{label}（{n} 个文件、选中 {sel} 个）")
        checked = self.task_list.checked_indices()  # 保留任务勾选状态
        sort_col, sort_rev = self.task_list._sort_col, self.task_list._sort_rev  # 保留排序状态
        self.task_list.set_rows(rows, keys=list(range(len(self._tasks))))
        self.task_list.set_checked(checked)
        if sort_col:
            self.task_list._sort_col = sort_col
            self.task_list._sort_rev = sort_rev
            self.task_list._do_sort(sort_col, sort_rev)

    def _task_active_files(self, t):
        """任务中勾选参与翻译的文件；未勾选过的任务默认全部。"""
        files = t.get("files", [])
        incl = t.get("checked")
        if not incl:
            return list(files)
        return [f for i, f in enumerate(files) if i in incl]

    def _on_tasks_delete(self, indices):
        keys = self.task_list.keys_for_indices(indices)
        if not keys:
            return
        rows_before = len(self.task_list.rows)
        base = max(indices) if indices else 0
        # 删除后自动选中“下方一项”；若删除的是最后一项则选中“上方一项”
        target_task = None
        if base + 1 < rows_before:
            k = self.task_list._row_keys[base + 1]
            if 0 <= k < len(self._tasks):
                target_task = self._tasks[k]
        elif base - 1 >= 0:
            k = self.task_list._row_keys[base - 1]
            if 0 <= k < len(self._tasks):
                target_task = self._tasks[k]
        self._push_tasks_history()
        for i in sorted(keys, reverse=True):
            if 0 <= i < len(self._tasks):
                del self._tasks[i]
        self._refresh_tasks()
        self._refresh_play_button()
        if target_task is not None:
            pos = next((i for i, t in enumerate(self._tasks) if t is target_task), None)
            if pos is not None:
                self.task_list.selected = {pos}
                self.task_list._draw()

    def _push_tasks_history(self):
        self._tasks_history.append((
            copy.deepcopy(self._tasks),
            self.task_list.checked_indices(),
            self.task_list.selected_keys(),
            self.task_list.yview()[0],
        ))
        if len(self._tasks_history) > 50:
            self._tasks_history.pop(0)
        self._tasks_redo.clear()

    def _on_tasks_undo(self, _event=None):
        """任务队列 Ctrl+Z：撤销上一次添加/删除任务操作。"""
        if not self._tasks_history:
            return "break"
        state = self._tasks_history.pop()
        self._tasks_redo.append((
            copy.deepcopy(self._tasks),
            self.task_list.checked_indices(),
            self.task_list.selected_keys(),
            self.task_list.yview()[0],
        ))
        self._tasks = state[0]
        self._refresh_tasks()
        self.task_list.set_checked(state[1])
        self.task_list.select_keys(state[2], state[3])
        self._refresh_play_button()
        return "break"

    def _on_tasks_redo(self, _event=None):
        """任务队列 Ctrl+Y / Ctrl+Shift+Z：重做被撤销的操作。"""
        if not self._tasks_redo:
            return "break"
        state = self._tasks_redo.pop()
        self._tasks_history.append((
            copy.deepcopy(self._tasks),
            self.task_list.checked_indices(),
            self.task_list.selected_keys(),
            self.task_list.yview()[0],
        ))
        self._tasks = state[0]
        self._refresh_tasks()
        self.task_list.set_checked(state[1])
        self.task_list.select_keys(state[2], state[3])
        self._refresh_play_button()
        return "break"

    def _on_tasks_enter(self, _event=None):
        """任务队列按回车：打开选中任务的内容设置弹窗。"""
        sel = sorted(self.task_list.selected)
        if not sel:
            return "break"
        keys = self.task_list.keys_for_indices([sel[0]])
        if keys and keys[0] < len(self._tasks):
            TaskDetailWindow(self.root, self, keys[0])
        return "break"

    def _on_tasks_open(self, indices):
        keys = self.task_list.keys_for_indices(indices)
        if not keys or keys[0] >= len(self._tasks):
            return
        folder = self._tasks[keys[0]].get("folder", "")
        if folder and os.path.isdir(folder):
            subprocess.Popen(["explorer", os.path.normpath(folder)])

    def _on_tasks_double_click(self, event):
        """双击任务：弹出表格形式的新窗口查看任务内容。"""
        if event.x < 26:
            return
        idx = self.task_list._row_at(event.y)
        keys = self.task_list.keys_for_indices([idx])
        if not keys or keys[0] >= len(self._tasks):
            return
        TaskDetailWindow(self.root, self, keys[0])

    def _open_folder(self):
        text = self.folder_var.get().strip()
        if not text:
            text = ";".join(self._selected_files)
        if not text:
            return
        parts = split_targets(text)
        if not parts:
            return
        first = parts[0]
        if os.path.isdir(first):
            subprocess.Popen(["explorer", os.path.normpath(first)])
        elif os.path.isfile(first):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(first)])

    def _apply_extension_preset(self, _event=None):
        name = self.preset_var.get()
        if name in EXTENSION_PRESETS:
            self._set_extensions(EXTENSION_PRESETS[name])

    def _set_extensions(self, text):
        self.ext_text.delete("1.0", "end")
        self.ext_text.insert("1.0", text or "")

    def _get_extensions(self):
        return self.ext_text.get("1.0", "end").strip()

    def _open_settings(self, tab=None):
        if tab == "glossary":
            SettingsWindow(self.root, self.cfg, on_saved=self._on_settings_saved, glossary_only=True)
        else:
            SettingsWindow(self.root, self.cfg, on_saved=self._on_settings_saved, exclude_glossary=True)

    def _on_settings_saved(self):
        self._refresh_engine_combo()

    def _on_tree_click(self, event):
        if self.tree.identify("region", event.x, event.y) == "heading":
            self._on_tree_heading_click(event)
            return
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        col = self.tree.identify_column(event.x)
        if col != "#1":
            return  # 其余列交给原生 extended 模式：单击单选、Ctrl+点击多选/少选
        idx = self.iid_to_index.get(iid)
        if idx is None or idx >= len(self.plan):
            return "break"
        item = self.plan[idx]
        if not self._row_ready(item) or idx in self.removed_indices:
            return "break"
        self._push_tree_history()
        if idx in self.disabled_indices:
            self.disabled_indices.discard(idx)
        else:
            self.disabled_indices.add(idx)
        self._update_row(iid, item, done=False)
        self._refresh_rename_button()
        return "break"

    def _on_tree_double_click(self, event):
        """双击“新文件名”列：就地编辑新的文件名。"""
        col = self.tree.identify_column(event.x)
        if col != "#3":  # 新文件名列
            return
        row = self.tree.identify_row(event.y)
        if not row:
            return
        idx = self.iid_to_index.get(row)
        if idx is None or idx >= len(self.plan):
            return
        item = self.plan[idx]
        if item["status"] not in ("ok", "error"):
            return
        bbox = self.tree.bbox(row, col)
        if not bbox:
            return
        x, y, w, h = bbox
        entry = tk.Entry(self.tree, font=("Microsoft YaHei UI", 9))
        self._tree_editor_entry = entry
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, os.path.basename(item["new_path"]))
        entry.focus_set()
        entry.select_range(0, "end")

        def commit(_e=None):
            if self._tree_editor_entry is not entry:
                return
            val = entry.get().strip()
            entry.destroy()
            self._tree_editor_entry = None
            if not val:
                return
            item["new_name"] = val
            item["new_path"] = os.path.join(item["folder"], val)
            item["manual_edit"] = True
            self._update_row(row, item)
            self._refresh_rename_button()

        def cancel(_e=None):
            if self._tree_editor_entry is not entry:
                return
            entry.destroy()
            self._tree_editor_entry = None

        entry.bind("<Return>", commit)
        entry.bind("<FocusOut>", commit)
        entry.bind("<Escape>", cancel)

    def _on_tree_heading_click(self, event):
        col = self.tree.identify_column(event.x)
        if col not in ("#1", "#2", "#3"):
            return
        # 若该列所有可见行的值都相同，则不调整排序方式
        values = set()
        for iid in self.tree.get_children():
            idx = self.iid_to_index.get(iid)
            if idx is None or idx >= len(self.plan):
                continue
            item = self.plan[idx]
            if col == "#1":
                values.add(0 if idx not in self.disabled_indices else 1)
            elif col == "#2":
                values.add(item["old_name"].lower())
            else:
                values.add((item.get("manual_edit", False), item["new_name"].lower()))
            if len(values) > 1:
                break
        if len(values) <= 1:
            return
        direction = "desc" if self._sort_state.get(col) == "asc" else "asc"
        self._sort_state = {col: direction}
        self._apply_sort(col, direction)
        self._update_heading_arrows()

    def _apply_sort(self, col, direction):
        """按列排序：选择(已/未选择)、原文件名(A-Z/Z-A)、新文件名(手动/未手动修改)。"""
        indices = [idx for idx in range(len(self.plan)) if idx not in self.removed_indices]

        def key(idx):
            item = self.plan[idx]
            if col == "#1":
                return 0 if idx not in self.disabled_indices else 1
            if col == "#2":
                return item["old_name"].lower()
            if col == "#3":
                return (0 if item.get("manual_edit", False) else 1, item["new_name"].lower())
            return 0

        indices.sort(key=key, reverse=(direction == "desc"))
        self.tree.delete(*self.tree.get_children())
        self.iid_to_index = {}
        for idx in indices:
            new_iid = self.tree.insert("", "end")
            self.iid_to_index[new_iid] = idx
            self._update_row(new_iid, self.plan[idx])
        self._refresh_cell_labels()

    def _push_tree_history(self):
        self._tree_history.append((
            set(self.disabled_indices),
            set(self.removed_indices),
            self._selected_plan_indices(),
            self.tree.yview()[0],
        ))
        if len(self._tree_history) > 50:
            self._tree_history.pop(0)
        self._tree_redo.clear()

    def _selected_plan_indices(self):
        return [self.iid_to_index[iid] for iid in self.tree.selection() if iid in self.iid_to_index]

    def _select_plan_indices(self, indices):
        keep = [iid for iid, idx in self.iid_to_index.items() if idx in indices]
        if keep:
            self.tree.selection_set(keep)
            self.tree.focus(keep[0])

    def _rebuild_tree_rows(self):
        col = next(iter(self._sort_state), None)
        direction = self._sort_state.get(col) if col else None
        self._apply_sort(col if col else "#2", direction if col else "asc")
        self._update_heading_arrows()

    def _refresh_rename_button(self):
        ok_count = sum(
            1
            for iid in self.tree.get_children()
            if (idx := self.iid_to_index.get(iid)) is not None
            and idx < len(self.plan)
            and self._row_ready(self.plan[idx])
            and idx not in self.disabled_indices
        )
        self.rename_btn.set_state("normal" if ok_count else "disabled")

    def _on_tree_space(self, _event=None):
        """翻译框空格：切换选中行“选择”列的对勾。"""
        sel = self.tree.selection()
        if not sel:
            return "break"
        self._push_tree_history()
        for iid in list(sel):
            idx = self.iid_to_index.get(iid)
            if idx is None or idx >= len(self.plan):
                continue
            item = self.plan[idx]
            if not self._row_ready(item) or idx in self.removed_indices:
                continue
            if idx in self.disabled_indices:
                self.disabled_indices.discard(idx)
            else:
                self.disabled_indices.add(idx)
            self._update_row(iid, item, done=False)
        self._refresh_rename_button()
        return "break"

    def _on_tree_enter(self, _event=None):
        """翻译框回车：打开选中文件所在位置。"""
        sel = self.tree.selection()
        if not sel:
            return "break"
        iid = sel[0]
        idx = self.iid_to_index.get(iid)
        if idx is None or idx >= len(self.plan):
            return "break"
        item = self.plan[idx]
        path = item.get("old_path") or os.path.join(item.get("folder", ""), item.get("old_name", ""))
        if os.path.isfile(path):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        return "break"

    def _on_tree_delete(self, _event=None):
        self._remove_selected()
        return "break"

    def _remove_selected(self):
        """Del / 右键“移除队列”：把选中的行从右侧翻译队列移除。"""
        sel = list(self.tree.selection())
        if not sel:
            return
        children = self.tree.get_children()
        positions = []
        for iid in sel:
            try:
                positions.append(children.index(iid))
            except ValueError:
                pass
        base = max(positions) if positions else 0
        # 删除后自动选中“下方一项”；若删除的是最后一项则选中“上方一项”
        target_iid = None
        if base + 1 < len(children):
            target_iid = children[base + 1]
        elif base - 1 >= 0:
            target_iid = children[base - 1]
        self._push_tree_history()
        changed = False
        for iid in sel:
            idx = self.iid_to_index.get(iid)
            if idx is None or idx >= len(self.plan):
                continue
            if not self._row_ready(self.plan[idx]) or idx in self.removed_indices:
                continue
            self.removed_indices.add(idx)
            self.tree.delete(iid)
            changed = True
        if changed:
            self.iid_to_index = {i: x for i, x in self.iid_to_index.items() if self.tree.exists(i)}
            self._refresh_rename_button()
            if target_iid is not None and self.tree.exists(target_iid):
                self.tree.selection_set(target_iid)
                self.tree.focus(target_iid)

    def _on_tree_right_click(self, event):
        iid = self.tree.identify_row(event.y)
        if iid and iid not in self.tree.selection():
            self.tree.selection_set(iid)
        menu = tk.Menu(self.tree, tearoff=0)
        menu.add_command(label="移除队列", command=self._remove_selected)
        menu.add_command(label="打开文件所在位置", command=self._on_tree_enter)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _on_tree_undo(self, _event=None):
        """翻译框 Ctrl+Z：撤销上一次勾选/移除队列操作。"""
        if not self._tree_history:
            return "break"
        state = self._tree_history.pop()
        self._tree_redo.append((
            set(self.disabled_indices),
            set(self.removed_indices),
            self._selected_plan_indices(),
            self.tree.yview()[0],
        ))
        self.disabled_indices = set(state[0])
        self.removed_indices = set(state[1])
        self._rebuild_tree_rows()
        self._refresh_rename_button()
        self._select_plan_indices(state[2])
        try:
            self.tree.yview_moveto(float(state[3]))
        except (ValueError, tk.TclError):
            pass
        return "break"

    def _on_tree_redo(self, _event=None):
        """翻译框 Ctrl+Y / Ctrl+Shift+Z：重做被撤销的操作。"""
        if not self._tree_redo:
            return "break"
        state = self._tree_redo.pop()
        self._tree_history.append((
            set(self.disabled_indices),
            set(self.removed_indices),
            self._selected_plan_indices(),
            self.tree.yview()[0],
        ))
        self.disabled_indices = set(state[0])
        self.removed_indices = set(state[1])
        self._rebuild_tree_rows()
        self._refresh_rename_button()
        self._select_plan_indices(state[2])
        try:
            self.tree.yview_moveto(float(state[3]))
        except (ValueError, tk.TclError):
            pass
        return "break"

    def _update_heading_arrows(self):
        base = {"#1": "选择", "#2": "原文件名", "#3": "新文件名"}
        for col, text in base.items():
            direction = self._sort_state.get(col)
            arrow = {"asc": " ▲", "desc": " ▼"}.get(direction, "")
            self.tree.heading(col, text=text + arrow)

    # ================================================================ 翻译框：单元格着色
    def _row_ready(self, item):
        """该行是否可以勾选并执行重命名（翻译成功，或已手动修改新文件名）。"""
        return item["status"] == "ok" or bool(item.get("manual_edit"))

    def _new_display(self, item):
        """“新文件名”列当前显示的文字（与行状态保持一致）。"""
        if item.get("manual_edit"):
            return os.path.basename(item["new_path"])
        if item["status"] == "ok":
            return os.path.basename(item["new_path"])
        if item["status"] == "error":
            return plain_error(item["note"])
        return item["old_name"]

    def _cell_fg(self, item, column, selected=False):
        """单元格文字颜色：原文件名 绿=成功/红=失败；新文件名 黑=默认/绿=手动修改。

        选中行时根据选中背景色的明暗自动换成高对比度的同色系变体，
        避免绿色/红色文字叠在蓝色选中背景上看不清。
        """
        if column == "old":
            if item["status"] == "ok":
                base = TREE_FG_OK
            elif item["status"] == "error":
                base = TREE_FG_ERROR
            else:
                base = TREE_FG_NORMAL
        else:
            base = TREE_FG_MANUAL if item.get("manual_edit") else TREE_FG_NORMAL
        if not selected:
            return base
        # 选中行：根据选中背景明暗选变体
        try:
            sb = (getattr(self, "_sel_bg", "#4a6984") or "#4a6984").lstrip("#")
            r = int(sb[0:2], 16)
            g = int(sb[2:4], 16)
            b = int(sb[4:6], 16)
            luma = 0.299 * r + 0.587 * g + 0.114 * b
        except Exception:
            luma = 90
        if luma > 150:  # 浅色选中背景：用深色变体
            return {
                TREE_FG_OK: "#0d5c22",
                TREE_FG_ERROR: "#a01818",
                TREE_FG_NORMAL: "#1d2b44",
            }.get(base, "#1d2b44")
        # 深色选中背景（如 clam 主题 #4a6984）：用浅色变体
        return {
            TREE_FG_OK: "#a9e0b2",
            TREE_FG_ERROR: "#ffb4b4",
            TREE_FG_NORMAL: "#ffffff",
        }.get(base, "#ffffff")

    def _tree_event_xy(self, event):
        """把覆盖标签上的事件坐标转换成相对 Treeview 的坐标。"""
        try:
            return event.x + event.widget.winfo_x(), event.y + event.widget.winfo_y()
        except tk.TclError:
            return event.x, event.y

    def _forward_tree_click(self, event, _col):
        self.tree.focus_set()
        x, y = self._tree_event_xy(event)
        if self.tree.identify("region", x, y) == "heading":
            ev = type("TreeEvent", (), {"x": x, "y": y})()
            self._on_tree_heading_click(ev)
            return "break"
        iid = self.tree.identify_row(y)
        col = self.tree.identify_column(x)
        if not iid:
            return "break"
        idx = self.iid_to_index.get(iid)
        if idx is None or idx >= len(self.plan):
            return "break"
        if col == "#1":
            # 勾选列：交给原有逻辑（切换对勾，不改变选中状态）
            ev = type("TreeEvent", (), {"x": x, "y": y, "state": event.state})()
            self._on_tree_click(ev)
            return "break"
        # 原文件名/新文件名列：模拟原生 extended 模式的选择
        ctrl = (event.state & 0x0004) != 0
        shift = (event.state & 0x0001) != 0
        if shift:
            children = self.tree.get_children()
            focus = self.tree.focus()
            try:
                start = children.index(focus) if focus in children else 0
                end = children.index(iid)
            except ValueError:
                start, end = 0, 0
            lo, hi = sorted((start, end))
            self.tree.selection_set(children[lo : hi + 1])
            self._tree_drag_anchor = None
        elif ctrl:
            if iid in self.tree.selection():
                self.tree.selection_remove(iid)
            else:
                self.tree.selection_add(iid)
            self._tree_drag_anchor = None
        else:
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self._tree_drag_anchor = iid
        return "break"

    def _forward_tree_drag(self, event, _col):
        x, y = self._tree_event_xy(event)
        iid = self.tree.identify_row(y)
        if not iid:
            return "break"
        anchor = getattr(self, "_tree_drag_anchor", None)
        if anchor is None:
            anchor = iid
            self._tree_drag_anchor = anchor
        children = self.tree.get_children()
        try:
            lo, hi = sorted((children.index(anchor), children.index(iid)))
        except ValueError:
            return "break"
        self.tree.selection_set(children[lo : hi + 1])
        return "break"

    def _forward_tree_release(self, event, _col):
        self._tree_drag_anchor = None
        return "break"

    def _forward_tree_double(self, event, _col):
        x, y = self._tree_event_xy(event)
        ev = type("TreeEvent", (), {"x": x, "y": y})()
        self._on_tree_double_click(ev)
        return "break"

    def _forward_tree_right(self, event, _col):
        x, y = self._tree_event_xy(event)
        ev = type("TreeEvent", (), {"x": x, "y": y, "x_root": event.x_root, "y_root": event.y_root})()
        self._on_tree_right_click(ev)
        return "break"

    def _schedule_cell_refresh(self):
        """合并同一轮事件循环内的多次刷新请求。"""
        try:
            if getattr(self, "_cell_refresh_scheduled", False):
                return
            self._cell_refresh_scheduled = True
            self.root.after_idle(self._do_refresh_cell_labels)
        except tk.TclError:
            pass

    def _do_refresh_cell_labels(self):
        self._cell_refresh_scheduled = False
        try:
            self._refresh_cell_labels()
        except tk.TclError:
            pass

    def _refresh_cell_labels(self):
        """在“原文件名/新文件名”单元格上覆盖着色文字标签（Treeview 标签只能整行着色）。"""
        tree = self.tree
        try:
            if not tree.winfo_exists():
                return
            children = tree.get_children()
        except tk.TclError:
            return
        sel = set(tree.selection())
        needed = {}
        for iid in children:
            idx = self.iid_to_index.get(iid)
            if idx is None or idx >= len(self.plan):
                continue
            item = self.plan[idx]
            try:
                values = tree.item(iid, "values")
            except tk.TclError:
                continue
            for col_id, key in (("#2", "old"), ("#3", "new")):
                try:
                    bbox = tree.bbox(iid, col_id)
                except tk.TclError:
                    continue
                if not bbox:
                    continue
                text = values[1] if key == "old" else values[2]
                needed[(iid, col_id)] = (bbox, text, self._cell_fg(item, key, iid in sel), iid in sel)
        # 删除已不存在的单元格标签
        for key in list(self._cell_labels):
            if key not in needed:
                lbl = self._cell_labels.pop(key)
                try:
                    lbl.destroy()
                except tk.TclError:
                    pass
        # 创建/更新标签
        for key, (bbox, text, fg, selected) in needed.items():
            x, y, w, h = bbox
            lbl = self._cell_labels.get(key)
            if lbl is None:
                lbl = tk.Label(
                    tree,
                    text="",
                    anchor="w",
                    padx=4,
                    font=("Microsoft YaHei UI", 9),
                    bd=0,
                    highlightthickness=0,
                    takefocus=0,
                )
                col_id = key[1]
                lbl.bind("<Button-1>", lambda e, c=col_id: self._forward_tree_click(e, c))
                lbl.bind("<B1-Motion>", lambda e, c=col_id: self._forward_tree_drag(e, c))
                lbl.bind("<ButtonRelease-1>", lambda e, c=col_id: self._forward_tree_release(e, c))
                lbl.bind("<Double-1>", lambda e, c=col_id: self._forward_tree_double(e, c))
                lbl.bind("<Button-3>", lambda e, c=col_id: self._forward_tree_right(e, c))
                self._cell_labels[key] = lbl
            bg = self._sel_bg if selected else "white"
            try:
                lbl.configure(text=str(text), fg=fg, bg=bg)
                lbl.place(x=x, y=y, width=w, height=h)
            except tk.TclError:
                pass
        # 行内编辑框保持在最上层，避免被覆盖标签遮住
        try:
            for child in tree.winfo_children():
                if isinstance(child, tk.Entry):
                    child.lift()
        except tk.TclError:
            pass

    def _update_row(self, iid, item, done=False):
        if item["status"] == "ok":
            checked = "☑" if self.iid_to_index.get(iid, -1) not in self.disabled_indices else "☐"
            tag = "done" if done else "ok"
            values = (checked, item["old_name"], self._new_display(item))
        elif item["status"] == "error":
            values = ("—", item["old_name"], self._new_display(item))
            tag = "error"
        else:
            values = ("—", item["old_name"], self._new_display(item))
            tag = "skip"
        self.tree.item(iid, values=values, tags=(tag,))
        self._schedule_cell_refresh()

    def _insert_row(self, item):
        iid = self.tree.insert("", "end")
        self.iid_to_index[iid] = self._stream_index
        self._stream_index += 1
        item.setdefault("manual_edit", False)
        self._update_row(iid, item)
        return iid

    def _clear_list(self):
        if self.busy:
            return
        self.plan = []
        self.iid_to_index.clear()
        self._stream_index = 0
        self.disabled_indices.clear()
        self.removed_indices.clear()
        self._tree_history.clear()
        self._tree_redo.clear()
        for lbl in self._cell_labels.values():
            try:
                lbl.destroy()
            except tk.TclError:
                pass
        self._cell_labels.clear()
        self.tree.delete(*self.tree.get_children())
        self.progress["value"] = 0
        self.status_var.set("列表已清空。")
        self.rename_btn.config(state="disabled")

    def _log(self, msg):
        self._log_lines.append(f"[{log_time()}] {msg}\n")
        if self._log_window is not None:
            try:
                if self._log_window.winfo_exists():
                    self._log_window.append_text(self._log_lines[-1])
            except tk.TclError:
                self._log_window = None

    def _open_log(self):
        if self._log_window is not None:
            try:
                if self._log_window.winfo_exists():
                    self._log_window.lift()
                    self._log_window.focus_force()
                    return
            except tk.TclError:
                self._log_window = None
        self._log_window = LogWindow(self.root, self)

    # ================================================================ 工作线程
    def _set_busy(self, busy):
        self.busy = busy
        self._refresh_play_button()
        if not busy:
            ok_count = sum(1 for i in self.plan if self._row_ready(i))
            self.rename_btn.set_state("normal" if ok_count else "disabled")
            self.undo_btn.set_state("normal" if self.last_applied else "disabled")

    def _refresh_play_button(self):
        """根据任务/运行状态刷新播放器按钮。"""
        if not self._tasks:
            self.preview_btn.set_state("idle")
        elif self.busy:
            self.preview_btn.set_state("paused" if self.translate_paused else "running")
        else:
            self.preview_btn.set_state("ready")

    def _play_btn_click(self):
        if not self._tasks:
            return
        if self.busy:
            if self.translate_paused:
                self._resume_translate()
            else:
                self._pause_translate()
        else:
            self._start_translate()

    def _pause_translate(self):
        self.translate_paused = True
        self.pause_flag.set()
        self._refresh_play_button()
        self.status_var.set("已暂停（点击播放继续）")
        self._log("已暂停翻译。")

    def _resume_translate(self):
        self.translate_paused = False
        self.pause_flag.clear()
        self._refresh_play_button()
        self.status_var.set("继续翻译...")
        self._log("继续翻译。")

    def _start_translate(self):
        try:
            self._start_translate_impl()
        except Exception as e:
            import traceback

            traceback.print_exc()
            self._set_busy(False)
            self._log(f"重命名异常：{type(e).__name__}: {e}")
            messagebox.showerror(
                "重命名失败",
                f"出现异常：{type(e).__name__}: {e}\n\n具体信息已写入日志窗口。",
                parent=self.root,
            )

    def _start_translate_impl(self):
        if self.busy:
            return
        self.removed_indices.clear()
        self._tree_history.clear()
        self._tree_redo.clear()
        self.pause_flag.clear()
        self.translate_paused = False
        if self._tasks:
            # 有任务队列：翻译选中的任务；没选中则全部
            if self.task_list.checked_indices():
                selected_tasks = [self._tasks[i] for i in self.task_list.checked_indices()]
            else:
                selected_tasks = self._tasks
            parts = []
            for t in selected_tasks:
                t_files = [f for f in self._task_active_files(t) if os.path.isfile(f)]
                if t_files:
                    parts.extend(t_files)  # 任务有具体文件：只翻译这些
                elif not t.get("files") and t.get("folder"):
                    parts.append(t["folder"])  # 否则翻译整个文件夹
            targets = ";".join(parts)
            if not targets:
                messagebox.showwarning("提示", "选中的任务没有可处理的路径。", parent=self.root)
                return
        else:
            checked = self.files_list.checked_indices()
            if checked:
                file_parts = [
                    self._selected_files[i] for i in checked
                    if 0 <= i < len(self._selected_files) and os.path.isfile(self._selected_files[i])
                ]
            else:
                file_parts = [p for p in self._selected_files if os.path.isfile(p)]
            if file_parts:
                targets = ";".join(file_parts)  # 选了具体文件：只翻译这些文件
            else:
                targets = self.folder_var.get().strip()  # 没选文件：翻译文件夹内全部
        if not targets:
            messagebox.showwarning("提示", "请先选择文件夹或文件。", parent=self.root)
            return
        self._save_runtime_state()
        ok, err = cfg_mod.save_config(self.cfg)
        if not ok:
            self._log(f"配置保存失败: {err}")
        recursive = bool(self.recursive_var.get())
        extensions = self._get_extensions() or "*"
        langs = list(self.cfg.get("source_langs") or ["auto"])
        skip_langs = set(self.cfg.get("skip_langs") or [])
        need_filter = len(langs) > 1 and "auto" not in langs
        if "auto" in langs:
            source = "auto"
        elif len(langs) == 1:
            source = langs[0]
        else:
            source = "auto"
        target = self.cfg["target_lang"]
        engine_key = self.engine_display_to_key.get(self.engine_var.get(), "google")
        self.cfg["engine"] = engine_key
        if source == target and source != "auto":
            messagebox.showinfo("提示", "源语言和目标语言相同，无需翻译。", parent=self.root)
            return
        try:
            engine = get_engine(self.cfg, engine_key)
            self.engine = engine
            paths, invalid = discover_entries(targets, recursive, extensions)
        except (OSError, EngineError) as e:
            messagebox.showerror("错误", str(e), parent=self.root)
            return
        if invalid:
            messagebox.showwarning(
                "提示",
                "以下路径不存在，已忽略：\n" + "\n".join(invalid[:10]),
                parent=self.root,
            )
        if not paths:
            messagebox.showinfo("提示", "没有找到匹配的文件。", parent=self.root)
            return
        self._clear_list()
        self.status_var.set(f"开始翻译 {len(paths)} 个文件...")
        self._log(
            f"目标: {targets} | 翻译源: {engine.display} | 源语言: {self._source_summary(langs)} -> {target} | 共 {len(paths)} 个文件"
        )
        glossary = None
        if self.glossary_enabled_var.get():
            manual_entries = glossary_mod.load_entries()
            file_entries, file_errors = glossary_mod.load_selected_file_entries(self.cfg)
            entries = manual_entries + file_entries
            glossary = glossary_mod.Glossary(
                entries,
                case_sensitive=bool(self.cfg.get("glossary", {}).get("case_sensitive", False)),
            )
            if glossary.active_count:
                self._log(
                    f"自定义词库已启用：手动词条 {len(manual_entries)} 条 + 词库文件 {len(file_entries)} 条，共 {glossary.active_count} 条生效"
                )
                for err in file_errors[:5]:
                    self._log(f"词库文件: {err}")
            else:
                self._log("自定义词库已启用，但当前没有启用的词条")
        self.stop_flag.clear()
        self.queue = queue.Queue()
        self._set_busy(True)
        self.progress["maximum"] = max(1, len(paths))
        skip_target = bool(self.skip_var.get())  # 主线程读取，避免 worker 线程触碰 Tk

        filter_fn = None
        if need_filter or skip_langs:
            selected_set = set(langs)

            def filter_fn(item, translated):
                detected = getattr(engine, "last_detected", None) if isinstance(engine, GoogleEngine) else None
                if not detected:
                    detected = detect_script_language(item["stem"])
                # 跳过语言优先：检测到属于跳过语言 -> 跳过并给出原因
                if skip_langs and detected and detected in skip_langs:
                    return "源语言为跳过语言，跳过"
                if need_filter:
                    return detected is None or detected in selected_set
                return True

        def safe_translate(text, _s=None, _t=None):
            """独立线程执行翻译：点“停止”后立即放弃当前请求，不等它超时。"""
            box = []

            def run():
                try:
                    box.append(engine.translate(text, _s or source, _t or target))
                except Exception as e:
                    box.append(e)

            t = threading.Thread(target=run, daemon=True)
            t.start()
            while t.is_alive():
                if self.stop_flag.is_set():
                    engine.abort()
                    return ""
                t.join(0.2)
            result = box[0]
            if isinstance(result, Exception):
                raise result
            return result

        def worker():
            try:
                plan = build_plan(
                    paths,
                    lambda t: (
                        glossary.apply(safe_translate, t, source, target)
                        if glossary and glossary.active_count
                        else safe_translate(t)
                    ),
                    target,
                    skip_target,
                    progress_cb=lambda done, total, name, item: self.queue.put(("row", done, total, item)),
                    stop_flag=self.stop_flag,
                    post_filter=filter_fn,
                    pause_event=self.pause_flag,
                )
                self.queue.put(("done", plan))
            except Exception as e:  # 兜底，避免线程静默崩溃
                self.queue.put(("fatal", str(e)))

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()
        self.root.after(80, self._poll)

    def _stop(self):
        self.stop_flag.set()
        engine = getattr(self, "engine", None)
        if engine is not None and hasattr(engine, "abort"):
            # 后台中断连接，避免 session.close() 阻塞主线程
            threading.Thread(target=engine.abort, daemon=True).start()
        self.status_var.set("正在停止...")
        self._log("用户请求停止。")

    def _confirm_rename(self):
        if self.busy:
            return
        items = [
            self.plan[self.iid_to_index[iid]]
            for iid in self.tree.get_children()
            if self.iid_to_index[iid] not in self.disabled_indices
            and self._row_ready(self.plan[self.iid_to_index[iid]])
        ]
        if not items:
            messagebox.showinfo("提示", "没有勾选任何要重命名的文件。", parent=self.root)
            return
        if not messagebox.askyesno("确认", f"确定要重命名 {len(items)} 个文件吗？\n（重命名前可先勾选/取消个别文件）", parent=self.root):
            return
        self.status_var.set(f"正在重命名 {len(items)} 个文件...")
        self._log(f"开始重命名 {len(items)} 个文件")
        self.stop_flag.clear()
        self.queue = queue.Queue()
        self._set_busy(True)
        self.progress["maximum"] = max(1, len(items))
        self.progress["value"] = 0

        def worker():
            def log_cb(msg):
                self.queue.put(("log", msg))

            errors, applied = apply_plan(items, log_cb=log_cb)
            self.queue.put(("rename_done", errors, applied))

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()
        self.root.after(80, self._poll)

    def _confirm_undo(self, confirm=True):
        if self.busy or not self.last_applied:
            return
        n = len(self.last_applied)
        if confirm and not messagebox.askyesno("确认", f"撤销上次的 {n} 次重命名吗？", parent=self.root):
            return
        self.status_var.set(f"正在撤销 {n} 次重命名...")
        self._log(f"开始撤销 {n} 次重命名")
        self.queue = queue.Queue()
        self._set_busy(True)
        self.progress["maximum"] = max(1, n)
        self.progress["value"] = 0

        def worker():
            def log_cb(msg):
                self.queue.put(("log", msg))

            errors, reverted = undo_plan(self.last_applied, log_cb=log_cb)
            self.queue.put(("undo_done", errors, reverted))

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()
        self.root.after(80, self._poll)

    def _redo_rename(self):
        """Ctrl+Y / Ctrl+Shift+Z：重做上次撤销的重命名。"""
        if self.busy or not self.last_undone:
            return
        items = self.last_undone
        n = len(items)
        self.status_var.set(f"正在重做 {n} 次重命名...")
        self._log(f"开始重做 {n} 次重命名")
        self.queue = queue.Queue()
        self._set_busy(True)
        self.progress["maximum"] = max(1, n)
        self.progress["value"] = 0

        def worker():
            def log_cb(msg):
                self.queue.put(("log", msg))

            errors, applied = apply_plan(items, log_cb=log_cb)
            self.queue.put(("redo_done", errors, applied))

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()
        self.root.after(80, self._poll)

    def _on_shortcut_undo(self, _event=None):
        self._confirm_undo(confirm=False)
        return "break"

    def _on_shortcut_redo(self, _event=None):
        self._redo_rename()
        return "break"

    # ================================================================ 消息处理
    def _poll(self):
        try:
            while True:
                msg = self.queue.get_nowait()
                kind = msg[0]
                if kind == "row":
                    _done, _total, item = msg[1], msg[2], msg[3]
                    self._insert_row(item)
                    self.progress["value"] = _done
                    self.status_var.set(f"翻译中 {_done}/{_total}: {item['old_name']}")
                elif kind == "log":
                    self._log(msg[1])
                elif kind == "done":
                    self.plan = msg[1]
                    self._finish_translate()
                elif kind == "rename_done":
                    self._finish_rename(msg[1], msg[2])
                elif kind == "undo_done":
                    self._finish_undo(msg[1], msg[2])
                elif kind == "redo_done":
                    self.last_undone = []
                    self._finish_rename(msg[1], msg[2])
                elif kind == "fatal":
                    self._log(f"出错: {msg[1]}")
                    messagebox.showerror("出错", msg[1], parent=self.root)
                    self._set_busy(False)
        except queue.Empty:
            pass
        if self.worker is not None and self.worker.is_alive():
            self.root.after(80, self._poll)
        else:
            self.worker = None

    def _finish_translate(self):
        plan = self.plan
        self.pause_flag.clear()
        self.translate_paused = False
        ok = sum(1 for it in plan if it["status"] == "ok")
        skipped = sum(1 for it in plan if it["status"] == "skip")
        failed = sum(1 for it in plan if it["status"] == "error")
        self.status_var.set(f"预览完成：待重命名 {ok}，跳过 {skipped}，失败 {failed}。勾选后点击“保存修改”。")
        self._log(f"预览完成：待重命名 {ok}，跳过 {skipped}，失败 {failed}")
        for it in plan:
            if it["status"] == "error":
                self._log(f"失败 {it['old_name']}: {it['note']}")
        self._set_busy(False)

    def _finish_rename(self, errors, applied):
        self.last_applied = applied
        self.last_undone = []
        if applied:
            log_path = append_rename_log(os.path.dirname(applied[0][0]), applied)
            if log_path:
                self._log(f"重命名记录已写入: {log_path}")
        for iid in self.tree.get_children():
            idx = self.iid_to_index.get(iid)
            if idx is not None and idx < len(self.plan):
                item = self.plan[idx]
                if item["status"] == "ok" and idx not in self.disabled_indices:
                    self._update_row(iid, item, done=True)
        if errors:
            self._log(f"重命名完成，{len(applied)} 个成功，{len(errors)} 个失败。")
            messagebox.showwarning("完成", f"成功 {len(applied)} 个，失败 {len(errors)} 个：\n" + "\n".join(errors[:10]), parent=self.root)
        else:
            self._log(f"重命名完成，共 {len(applied)} 个。")
            messagebox.showinfo("完成", f"成功重命名 {len(applied)} 个文件。", parent=self.root)
        self.status_var.set(f"重命名完成：{len(applied)} 个。")
        self._set_busy(False)

    def _finish_undo(self, errors, reverted):
        if errors:
            self._log(f"撤销完成，{reverted} 个成功，{len(errors)} 个失败。")
            messagebox.showwarning("完成", f"撤销成功 {reverted} 个，失败 {len(errors)} 个：\n" + "\n".join(errors[:10]), parent=self.root)
        else:
            self._log(f"撤销完成，共 {reverted} 个。")
            messagebox.showinfo("完成", f"已撤销 {reverted} 个文件的重命名。", parent=self.root)
        if reverted:
            self.last_undone = list(self.last_applied)
        self.last_applied = []
        self.status_var.set(f"撤销完成：{reverted} 个。")
        self._set_busy(False)

    def _on_close(self):
        if self.busy:
            if not messagebox.askyesno("提示", "翻译/重命名仍在进行，确定退出吗？", parent=self.root):
                return
            self.stop_flag.set()
        self._save_runtime_state()
        cfg_mod.save_config(self.cfg)
        self.root.destroy()


# ================================================================ 设置窗口
class SettingsWindow(tk.Toplevel):
    """管理翻译源 / 设置窗口：修改后自动保存；可点击“设为默认”固定每次打开的页签。"""

    def __init__(self, parent, cfg, on_saved=None, start_tab=None, glossary_only=False, exclude_glossary=False):
        super().__init__(parent)
        setup_styles()
        self.configure(bg=APP_BG)
        self.withdraw()  # 先隐藏，居中后再显示，避免左上角闪烁
        self.cfg = cfg
        self.on_saved = on_saved
        self.glossary_only = glossary_only
        self._clipboard_fill = None
        self._clipboard_last = ""
        self._clipboard_watch_until = 0.0
        self.test_queue = queue.Queue()
        self.file_queue = queue.Queue()
        self._links = []
        self.result_vars = {
            "谷歌翻译": tk.StringVar(value=""),
            "DeepL": tk.StringVar(value=""),
            "Yandex": tk.StringVar(value=""),
            "百度翻译": tk.StringVar(value=""),
            "火山翻译": tk.StringVar(value=""),
            "小牛翻译": tk.StringVar(value=""),
            "腾讯云": tk.StringVar(value=""),
            "Bing 翻译": tk.StringVar(value=""),
            "Papago 翻译": tk.StringVar(value=""),
            "自定义翻译源": tk.StringVar(value=""),
            "自定义词库": tk.StringVar(value=""),
        }
        self.title("管理词库" if glossary_only else "管理翻译源 / 设置")
        if glossary_only:
            self.geometry("940x800")
            self.minsize(820, 700)
        else:
            self.geometry("780x720")
            self.minsize(700, 680)
        self.transient(parent)

        if glossary_only:
            # 独立词库管理窗口：只显示 自定义词库 内容
            container = ttk.Frame(self, padding=8)
            container.pack(fill="both", expand=True)
            self._build_glossary_content(container)
        else:
            notebook = StatusNotebook(self, on_select=self._on_tab_selected)
            notebook.set_group_titles({0: "常\n规", 1: "A\nI"})
            notebook.on_reorder = self._on_tab_reordered
            notebook.pack(fill="both", expand=True, padx=8, pady=8)
            self.notebook = notebook
            self._build_common_tab(notebook)
            self._build_google_tab(notebook)
            self._build_deepl_tab(notebook)
            self._build_yandex_tab(notebook)
            self._build_baidu_tab(notebook)
            self._build_volcengine_tab(notebook)
            self._build_niutrans_tab(notebook)
            self._build_tencent_tab(notebook)
            self._build_bing_tab(notebook)
            self._build_papago_tab(notebook)
            self._build_custom_tab(notebook)
            self._build_ai_group(notebook)
            if not exclude_glossary:
                self._build_glossary_tab(notebook)
            # 应用上次拖动保存的页签顺序
            saved_order = self.cfg.get("settings_tab_order") or {}
            for group, key in ((0, "group0"), (1, "group1")):
                saved = saved_order.get(key)
                if not saved:
                    continue
                members = notebook.group_members[group]
                new_members = []
                for text in saved:
                    for idx in members:
                        if notebook.texts[idx] == text and idx not in new_members:
                            new_members.append(idx)
                            break
                for idx in members:
                    if idx not in new_members:
                        new_members.append(idx)
                notebook.group_members[group] = new_members
            notebook._relayout_tabs()
            notebook.select(0)  # 先默认显示“通用”
            # 每次打开都选中“设为默认”的页签（未设置则保持“通用”）
            default_tab = self.cfg.get("default_settings_tab")
            if default_tab:
                for idx, tab in enumerate(notebook.tabs()):
                    if notebook.tab(tab, "text") == default_tab:
                        notebook.select(idx)
                        break
            notebook.set_default(default_tab)

            # 底部：“设为默认”按钮 + 当前默认提示
            bottom = ttk.Frame(self)
            bottom.pack(fill="x", padx=10, pady=(0, 8))
            RoundedButton(bottom, "设为默认", self._set_default, style="green").pack(side="left")
            self.default_label_var = tk.StringVar()
            ttk.Label(bottom, textvariable=self.default_label_var, foreground="#1e7e34").pack(
                side="left", padx=10
            )
            self._update_default_label()

        self.protocol("WM_DELETE_WINDOW", self._close_auto_save)
        center_window(self)
        self.deiconify()
        self.grab_set()
        self.wait_visibility()
        self.after(80, self._poll_test)
        self._refresh_ip_info()

    # ---------------------------------------------------------------- 通用
    def _build_common_tab(self, notebook):
        tab = ttk.Frame(notebook.body, padding=10)
        notebook.add(tab, text="通用")
        ttk.Label(tab, text="代理服务器(可留空)：").grid(row=0, column=0, sticky="w", pady=4)
        self.proxy_var = tk.StringVar(value=self.cfg.get("proxy", ""))
        proxy_row = ttk.Frame(tab)
        proxy_row.grid(row=0, column=1, sticky="ew", pady=4, padx=(6, 0))
        self.proxy_type_var = tk.StringVar(
            value={"auto": "自动检测", "http": "HTTP", "socks5h": "SOCKS5"}.get(self.cfg.get("proxy_type", "auto"), "自动检测")
        )
        ttk.Combobox(
            proxy_row,
            textvariable=self.proxy_type_var,
            values=("自动检测", "HTTP", "SOCKS5"),
            state="readonly",
            width=8,
        ).pack(side="left", padx=(0, 6))
        ttk.Entry(proxy_row, textvariable=self.proxy_var, width=30).pack(side="left", fill="x", expand=True)
        RoundedButton(proxy_row, "测试代理", self._test_proxy, style="gray").pack(side="left", padx=6)
        self.proxy_test_var = tk.StringVar(value="")
        ttk.Label(proxy_row, textvariable=self.proxy_test_var, foreground=PRIMARY).pack(side="left", padx=4)
        ttk.Label(tab, text="示例：127.0.0.1:10808（左侧选择协议；自动检测会优先尝试 SOCKS5）", foreground="#888").grid(
            row=1, column=1, sticky="w", padx=(6, 0), pady=(0, 4)
        )
        ttk.Label(tab, text="请求超时(秒)：").grid(row=2, column=0, sticky="w", pady=4)
        self.timeout_var = tk.StringVar(value=str(self.cfg.get("timeout", 20)))
        ttk.Spinbox(tab, from_=5, to=120, textvariable=self.timeout_var, width=10).grid(row=2, column=1, sticky="w", pady=4, padx=(6, 0))

        # ---- IP 信息 ----
        ttk.Label(tab, text="我的IP：").grid(row=3, column=0, sticky="w", pady=4)
        ip_row = ttk.Frame(tab)
        ip_row.grid(row=3, column=1, sticky="w", pady=4, padx=(6, 0))
        self.ip_value_var = tk.StringVar(value="查询中...")
        ttk.Label(ip_row, textvariable=self.ip_value_var, foreground=PRIMARY).pack(side="left")
        RoundedButton(ip_row, "刷新", self._refresh_ip_info, style="gray").pack(side="left", padx=6)

        ttk.Label(tab, text="IP类型：").grid(row=4, column=0, sticky="w", pady=4)
        self.ip_type_var = tk.StringVar(value="")
        ttk.Label(tab, textvariable=self.ip_type_var, foreground="#1d2b44").grid(
            row=4, column=1, sticky="w", pady=4, padx=(6, 0)
        )

        ttk.Label(tab, text="风控程度：").grid(row=5, column=0, sticky="w", pady=4)
        self.risk_var = tk.StringVar(value="")
        self.risk_label_widget = ttk.Label(tab, textvariable=self.risk_var)
        self.risk_label_widget.grid(row=5, column=1, sticky="w", pady=4, padx=(6, 0))

        tip = (
            "说明：\n"
            "• 谷歌翻译为免费接口，国内网络通常无法直连。如有代理（如 Clash 的 http://127.0.0.1:7890），填入上方即可。\n"
            "• DeepL 与 AI 接口一般可直连，AI 接口适合批量翻译，速度与效果更好。\n"
            "• 配置文件保存在程序同目录 config.json（只读目录时保存在用户目录）。"
        )
        ttk.Label(tab, text=tip, justify="left", foreground="#555").grid(row=6, column=0, columnspan=2, sticky="w", pady=(12, 0))
        tab.columnconfigure(1, weight=1)

    # ---------------------------------------------------------------- 谷歌
    def _build_google_tab(self, notebook):
        tab = ttk.Frame(notebook.body, padding=10)
        notebook.add(tab, text="谷歌翻译")
        text = (
            "谷歌翻译（免费）\n\n"
            "• 无需 API Key，直接使用。\n"
            "• 免费接口有频率限制，批量大文件时建议放慢或使用 AI 接口。\n"
            "• 国内网络若无法直连，请在“通用”标签页配置代理。"
        )
        ttk.Label(tab, text=text, justify="left").pack(anchor="w")
        self._test_button(tab, "google", self.result_vars["谷歌翻译"], "谷歌翻译", row=None)

    # ---------------------------------------------------------------- DeepL
    def _build_deepl_tab(self, notebook):
        tab = ttk.Frame(notebook.body, padding=10)
        notebook.add(tab, text="DeepL")
        ttk.Label(tab, text="API Key：").grid(row=0, column=0, sticky="w", pady=4)
        self.deepl_key_var = tk.StringVar(value=self.cfg.get("deepl", {}).get("api_key", ""))
        ttk.Entry(tab, textvariable=self.deepl_key_var, width=48, show="*").grid(row=0, column=1, sticky="ew", pady=4, padx=(6, 0))
        ttk.Label(tab, text="账号类型：").grid(row=1, column=0, sticky="w", pady=4)
        self.deepl_type_var = tk.StringVar(value="免费版" if self.cfg.get("deepl", {}).get("api_type", "free") == "free" else "专业版")
        ttk.Combobox(tab, textvariable=self.deepl_type_var, values=("免费版", "专业版"), state="readonly", width=10).grid(
            row=1, column=1, sticky="w", pady=4, padx=(6, 0)
        )
        ttk.Label(tab, text="获取 API Key：").grid(row=2, column=0, sticky="w", pady=4)
        self._link_label(tab, "https://www.deepl.com/zh/pro-api", row=2, col=1)
        ttk.Label(tab, text="注册后可免费获取 API Key，点击上方链接直达。", foreground="#555").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=2
        )
        row = self._auto_fetch_row(tab, "deepl", "api_key", "https://www.deepl.com/zh/pro-api", 4, var=self.deepl_key_var)
        self._test_button(tab, "deepl", self.result_vars["DeepL"], "DeepL", row=row)
        tab.columnconfigure(1, weight=1)

    # ---------------------------------------------------------------- Yandex
    def _build_yandex_tab(self, notebook):
        tab = ttk.Frame(notebook.body, padding=10)
        notebook.add(tab, text="Yandex")
        ttk.Label(tab, text="API Key：").grid(row=0, column=0, sticky="w", pady=4)
        self.yandex_key_var = tk.StringVar(value=self.cfg.get("yandex", {}).get("api_key", ""))
        ttk.Entry(tab, textvariable=self.yandex_key_var, width=52, show="*").grid(row=0, column=1, sticky="ew", pady=4, padx=(6, 0))
        ttk.Label(tab, text="获取 API Key：").grid(row=1, column=0, sticky="w", pady=4)
        self._link_label(tab, "https://yandex.com/dev/translate/", row=1, col=1)
        ttk.Label(tab, text="Yandex 翻译接口，需要 API Key（免费额度有限）。", foreground="#555").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=2
        )
        row = self._auto_fetch_row(tab, "yandex", "api_key", "https://yandex.com/dev/translate/", 3, var=self.yandex_key_var)
        self._test_button(tab, "yandex", self.result_vars["Yandex"], "Yandex", row=row)
        tab.columnconfigure(1, weight=1)

    # ---------------------------------------------------------------- 通用 Key 页签
    def _build_key_tab(self, notebook, tab_text, engine_key, cfg_key, fields, url, note):
        tab = ttk.Frame(notebook.body, padding=10)
        notebook.add(tab, text=tab_text)
        row = 0
        for attr, label, show in fields:
            ttk.Label(tab, text=label).grid(row=row, column=0, sticky="w", pady=4)
            var = tk.StringVar(value=self.cfg.get(cfg_key, {}).get(attr, ""))
            setattr(self, f"{engine_key}_{attr}_var", var)
            ttk.Entry(tab, textvariable=var, width=52, show=("*" if show else "")).grid(
                row=row, column=1, sticky="ew", pady=4, padx=(6, 0)
            )
            row += 1
        ttk.Label(tab, text="获取 API Key：").grid(row=row, column=0, sticky="w", pady=4)
        self._link_label(tab, url, row=row, col=1)
        row += 1
        ttk.Label(tab, text=note, foreground="#555").grid(row=row, column=0, columnspan=2, sticky="w", pady=2)
        row += 1
        row = self._auto_fetch_row(tab, engine_key, fields[-1][0], url, row)
        self._test_button(tab, engine_key, self.result_vars[tab_text], tab_text, row=row)
        tab.columnconfigure(1, weight=1)

    def _build_baidu_tab(self, notebook):
        self._build_key_tab(
            notebook, "百度翻译", "baidu", "baidu",
            [("appid", "APP ID：", False), ("secret", "密钥：", True)],
            "https://fanyi-api.baidu.com/",
            "百度翻译开放平台，免费申请 APP ID 与密钥，支持自动检测源语言。",
        )

    def _build_volcengine_tab(self, notebook):
        self._build_key_tab(
            notebook, "火山翻译", "volcengine", "volcengine",
            [("access_key", "Access Key ID：", False), ("secret_key", "Secret Access Key：", True)],
            "https://www.volcengine.com/product/machine-translation",
            "火山引擎机器翻译，需在控制台创建密钥对。",
        )

    def _build_niutrans_tab(self, notebook):
        self._build_key_tab(
            notebook, "小牛翻译", "niutrans", "niutrans",
            [("api_key", "API Key：", True)],
            "https://niutrans.com/trans_api",
            "小牛翻译开放平台，注册后获取 API Key。",
        )

    def _build_tencent_tab(self, notebook):
        self._build_key_tab(
            notebook, "腾讯云", "tencent", "tencent",
            [("secret_id", "SecretId：", False), ("secret_key", "SecretKey：", True)],
            "https://console.cloud.tencent.com/tmt",
            "腾讯云机器翻译 TMT，控制台创建密钥后使用。",
        )

    # ---------------------------------------------------------------- AI
    def _build_bing_tab(self, notebook):
        tab = ttk.Frame(notebook.body, padding=10)
        notebook.add(tab, text="Bing 翻译", group=0)
        ttk.Label(
            tab,
            text="Bing（微软）翻译为免费接口，无需 API Key；国内网络可能无法直连，请在“通用”页配置代理。",
            foreground="#555",
            justify="left",
            wraplength=560,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=4)
        self._test_button(tab, "bing", self.result_vars["Bing 翻译"], "Bing 翻译", row=2)
        tab.columnconfigure(1, weight=1)

    def _build_papago_tab(self, notebook):
        tab = ttk.Frame(notebook.body, padding=10)
        notebook.add(tab, text="Papago 翻译", group=0)
        papago_cfg = self.cfg.get("papago", {})
        ttk.Label(tab, text="Client ID：").grid(row=0, column=0, sticky="w", pady=4)
        self.papago_id_var = tk.StringVar(value=papago_cfg.get("client_id", ""))
        ttk.Entry(tab, textvariable=self.papago_id_var, width=52).grid(
            row=0, column=1, sticky="ew", pady=4, padx=(6, 0)
        )
        ttk.Label(tab, text="Client Secret：").grid(row=1, column=0, sticky="w", pady=4)
        self.papago_secret_var = tk.StringVar(value=papago_cfg.get("client_secret", ""))
        ttk.Entry(tab, textvariable=self.papago_secret_var, width=52, show="*").grid(
            row=1, column=1, sticky="ew", pady=4, padx=(6, 0)
        )
        link_url = "https://console.ncloud.com/naver-service/api"
        ttk.Label(tab, text="申请地址：").grid(row=2, column=0, sticky="w", pady=4)
        self._link_label(tab, link_url, row=2, col=1)
        self._test_button(tab, "papago", self.result_vars["Papago 翻译"], "Papago 翻译", row=4)
        tab.columnconfigure(1, weight=1)

    def _build_ai_group(self, notebook):
        """AI 模型组：每个预设渠道单独一个块（和普通翻译渠道相同布局）。"""
        cfg_mod.ensure_ai_providers(self.cfg)
        ai = self.cfg["ai"]
        self.ai_forms = {}
        self.ai_balance_vars = {}
        self.ai_model_boxes = {}
        for name, preset in cfg_mod.AI_PRESETS.items():
            tab = ttk.Frame(notebook.body, padding=10)
            notebook.add(tab, text=name, group=1)
            prov = ai["providers"].get(name, {})
            base_var = tk.StringVar(value=prov.get("base_url") or preset["base_url"])
            key_var = tk.StringVar(value=prov.get("api_key", ""))
            model_var = tk.StringVar(value=prov.get("model") or preset["model"])
            temp_var = tk.StringVar(value=str(prov.get("temperature", 0.3)))
            prompt_text = tk.Text(tab, height=4, width=52, wrap="word")
            prompt_text.insert("1.0", prov.get("system_prompt") or cfg_mod.DEFAULT_AI_PROMPT)
            self.ai_forms[name] = {
                "base": base_var,
                "key": key_var,
                "model": model_var,
                "temp": temp_var,
                "prompt": prompt_text,
            }
            self.result_vars.setdefault(name, tk.StringVar(value=""))

            url = preset.get("api_key_url") or ""
            r = 0
            if name == "本地 Ollama":
                # 本地 Ollama：无 API Key/余额概念，改为“下载 Ollama”入口 + 推荐模型两行
                line1 = ttk.Frame(tab)
                line1.grid(row=r, column=0, columnspan=2, sticky="w", pady=(6, 0), padx=(6, 0))
                dl_link = tk.Label(
                    line1,
                    text="下载Ollama：",
                    fg="#0645ad",
                    cursor="hand2",
                    font=("Microsoft YaHei UI", 9, "underline"),
                    bg=APP_BG,
                )
                dl_link.pack(side="left")
                dl_link.bind("<Button-1>", lambda _e: webbrowser.open("https://ollama.com/download"))
                for desc, model, size, model_url in cfg_mod.OLLAMA_RECOMMENDED[:4]:
                    ttk.Label(line1, text=f"{desc}：").pack(side="left")
                    link = tk.Label(
                        line1,
                        text=model,
                        fg="#0645ad",
                        cursor="hand2",
                        font=("Microsoft YaHei UI", 9, "underline"),
                        bg=APP_BG,
                    )
                    link.pack(side="left")
                    link.bind(
                        "<Button-1>",
                        lambda _e, m=model, u=model_url: self._pick_ollama_model(model_var, m, u),
                    )
                    ttk.Label(line1, text=f" ({size})  ").pack(side="left")
                r += 1
                line2 = ttk.Frame(tab)
                line2.grid(row=r, column=1, sticky="w", pady=(2, 0), padx=(6, 0))
                for desc, model, size, model_url in cfg_mod.OLLAMA_RECOMMENDED[4:]:
                    ttk.Label(line2, text=f"{desc}：").pack(side="left")
                    link = tk.Label(
                        line2,
                        text=model,
                        fg="#0645ad",
                        cursor="hand2",
                        font=("Microsoft YaHei UI", 9, "underline"),
                        bg=APP_BG,
                    )
                    link.pack(side="left")
                    link.bind(
                        "<Button-1>",
                        lambda _e, m=model, u=model_url: self._pick_ollama_model(model_var, m, u),
                    )
                    ttk.Label(line2, text=f" ({size})  ").pack(side="left")
                r += 1
            else:
                ttk.Label(tab, text="获取 API Key：").grid(row=r, column=0, sticky="w", pady=4)
                if url:
                    self._link_label(tab, url, row=r, col=1)
                else:
                    ttk.Label(tab, text="（自定义接口，直接填写下方地址即可）", foreground="#888").grid(
                        row=r, column=1, sticky="w", pady=4, padx=(6, 0)
                    )
                r += 1
                ttk.Label(tab, text="余额：").grid(row=r, column=0, sticky="w", pady=4)
                balance_row = ttk.Frame(tab)
                balance_row.grid(row=r, column=1, sticky="w", pady=4, padx=(6, 0))
                self.ai_balance_vars[name] = tk.StringVar(value="")
                RoundedButton(
                    balance_row,
                    "查询余额",
                    lambda n=name: self._query_ai_balance(n),
                    style="gray",
                ).pack(side="left")
                ttk.Label(balance_row, textvariable=self.ai_balance_vars[name], foreground=PRIMARY).pack(
                    side="left", padx=8
                )
                r += 1

            ttk.Label(tab, text="接口地址：").grid(row=r, column=0, sticky="w", pady=4)
            ttk.Entry(tab, textvariable=base_var, width=52).grid(
                row=r, column=1, sticky="ew", pady=4, padx=(6, 0)
            )
            r += 1
            if name != "本地 Ollama":
                ttk.Label(tab, text="API Key：").grid(row=r, column=0, sticky="w", pady=4)
                ttk.Entry(tab, textvariable=key_var, width=52, show="*").grid(
                    row=r, column=1, sticky="ew", pady=4, padx=(6, 0)
                )
            r += 1
            ttk.Label(tab, text="模型名称：").grid(row=r, column=0, sticky="w", pady=4)
            model_row = ttk.Frame(tab)
            model_row.grid(row=r, column=1, sticky="ew", pady=4, padx=(6, 0))
            model_box = ttk.Combobox(model_row, textvariable=model_var, width=46)
            self.ai_model_boxes[name] = model_box
            # 顺序：模型选择框 + “获取模型列表”按钮；用 grid 保证按钮不被压缩
            model_box.grid(row=0, column=0, sticky="ew", padx=(0, 6))
            RoundedButton(
                model_row,
                "获取模型列表",
                lambda n=name: self._fetch_ai_models(n),
                style="gray",
            ).grid(row=0, column=1, sticky="w")
            model_row.columnconfigure(0, weight=1)
            r += 1
            ttk.Label(tab, text="温度(0-1)：").grid(row=r, column=0, sticky="w", pady=4)
            ttk.Spinbox(tab, from_=0.0, to=1.0, increment=0.1, textvariable=temp_var, width=10).grid(
                row=r, column=1, sticky="w", pady=4, padx=(6, 0)
            )
            r += 1
            ttk.Label(tab, text="系统提示词：").grid(row=r, column=0, sticky="nw", pady=4)
            prompt_text.grid(row=r, column=1, sticky="ew", pady=4, padx=(6, 0))
            r += 1
            if name == "本地 Ollama":
                # 本地 Ollama 不需要“自动获取 API Key”
                row = r
            else:
                row = self._auto_fetch_row(
                    tab,
                    "ai",
                    "api_key",
                    url or "https://platform.deepseek.com",
                    r,
                    var=key_var,
                )
            self._test_button(tab, f"ai:{name}", self.result_vars[name], name, row=row)
            tab.columnconfigure(1, weight=1)

    def _fetch_ai_models(self, provider=None):
        self._apply_form_to_cfg()
        var = self.ai_balance_vars.get(provider)
        if var is not None:
            var.set("")

        def worker():
            try:
                models = list_ai_models(self.cfg, provider)
                self.test_queue.put(("models", provider, models))
            except EngineError as e:
                self.test_queue.put(("models_err", provider, str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _query_ai_balance(self, provider=None):
        self._apply_form_to_cfg()
        var = self.ai_balance_vars.get(provider)
        if var is not None:
            var.set("查询中...")

        def worker():
            try:
                text = query_ai_balance(self.cfg, provider)
                self.test_queue.put(("balance", provider, text))
            except EngineError as e:
                self.test_queue.put(("balance_err", provider, str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _pick_ollama_model(self, model_var, model, url):
        """本地 Ollama：点击推荐模型 -> 填入模型名称并打开下载地址。"""
        model_var.set(model)
        webbrowser.open(url)

    def _test_proxy(self):
        self._apply_form_to_cfg()
        self.proxy_test_var.set("测试中...")

        def worker():
            result = test_proxy_connectivity(self.cfg.get("proxy", ""), self.cfg.get("proxy_type", "auto"))
            self.test_queue.put(("proxy_result", result))

        threading.Thread(target=worker, daemon=True).start()

    def _auto_fetch_key(self, url, var):
        """打开官方获取页面，并监听剪贴板：复制 Key 后自动填入对应输入框。"""
        webbrowser.open(url)
        self._clipboard_fill = var
        self._clipboard_watch_until = time.time() + 120
        try:
            self._clipboard_last = self.clipboard_get().strip()
        except tk.TclError:
            self._clipboard_last = ""
        self._clipboard_watch()

    def _clipboard_watch(self):
        if self._clipboard_fill is None:
            return
        if time.time() > self._clipboard_watch_until:
            self._clipboard_fill = None
            return
        try:
            text = self.clipboard_get().strip()
        except tk.TclError:
            text = self._clipboard_last
        if text and text != self._clipboard_last and len(text) >= 8 and not any(
            ch.isspace() for ch in text
        ):
            self._clipboard_last = text
            var = self._clipboard_fill
            self._clipboard_fill = None
            var.set(text)
            messagebox.showinfo("已自动填入", "检测到剪贴板内容，已自动填入 API Key。", parent=self)
            return
        self.after(800, self._clipboard_watch)

    def _key_var(self, engine_key, attr):
        return getattr(self, f"{engine_key}_{attr}_var")

    def _auto_fetch_row(self, tab, engine_key, attr, url, row, var=None):
        """在页签里放一个“自动获取 API Key”按钮行。"""
        frame = ttk.Frame(tab)
        frame.grid(row=row, column=0, columnspan=2, sticky="w", pady=(6, 0))
        if var is None:
            var = self._key_var(engine_key, attr)
        RoundedButton(
            frame,
            "自动获取 API Key",
            lambda: self._auto_fetch_key(url, var),
            style="green",
        ).pack(side="left")
        ttk.Label(
            frame,
            text="点击打开官网获取页，复制 Key 后自动填入",
            foreground="#888",
        ).pack(side="left", padx=8)
        return row + 1

    def _refresh_ip_info(self):
        if getattr(self, "glossary_only", False):
            return
        self._apply_form_to_cfg()
        self.ip_value_var.set("查询中...")
        self.ip_type_var.set("")
        self.risk_var.set("")

        def worker():
            try:
                info = get_ip_info(self.cfg)
                self.test_queue.put(("ipinfo", info))
            except Exception as e:
                self.test_queue.put(("ipinfo_err", str(e)))

        threading.Thread(target=worker, daemon=True).start()

    # ---------------------------------------------------------------- 自定义源
    def _build_custom_tab(self, notebook):
        tab = ttk.Frame(notebook.body, padding=10)
        notebook.add(tab, text="自定义翻译源")
        left = ttk.Frame(tab)
        left.pack(side="left", fill="y", padx=(0, 10))
        self.custom_list = tk.Listbox(left, width=26, height=12)
        self.custom_list.pack(fill="y")
        self.custom_list.bind("<<ListboxSelect>>", self._load_custom)
        btns = ttk.Frame(left)
        btns.pack(fill="x", pady=4)
        RoundedButton(btns, "新建", self._new_custom, style="gray").pack(side="left", padx=2)
        RoundedButton(btns, "保存", self._save_custom, style="gray").pack(side="left", padx=2)
        RoundedButton(btns, "删除", self._delete_custom, style="gray").pack(side="left", padx=2)

        form = ttk.Frame(tab)
        form.pack(side="left", fill="both", expand=True)
        ttk.Label(form, text="名称：").grid(row=0, column=0, sticky="w", pady=3)
        self.c_name_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.c_name_var, width=30).grid(row=0, column=1, sticky="ew", pady=3, padx=(4, 0))
        ttk.Label(form, text="方法：").grid(row=1, column=0, sticky="w", pady=3)
        self.c_method_var = tk.StringVar(value="GET")
        ttk.Combobox(form, textvariable=self.c_method_var, values=("GET", "POST"), state="readonly", width=8).grid(
            row=1, column=1, sticky="w", pady=3, padx=(4, 0)
        )
        ttk.Label(form, text="请求URL：").grid(row=2, column=0, sticky="nw", pady=3)
        self.c_url_text = tk.Text(form, height=3, width=40, wrap="word")
        self.c_url_text.grid(row=2, column=1, sticky="ew", pady=3, padx=(4, 0))
        ttk.Label(form, text="请求头(JSON)：").grid(row=3, column=0, sticky="nw", pady=3)
        self.c_headers_text = tk.Text(form, height=2, width=40, wrap="word")
        self.c_headers_text.grid(row=3, column=1, sticky="ew", pady=3, padx=(4, 0))
        ttk.Label(form, text="请求体(JSON)：").grid(row=4, column=0, sticky="nw", pady=3)
        self.c_body_text = tk.Text(form, height=4, width=40, wrap="word")
        self.c_body_text.grid(row=4, column=1, sticky="ew", pady=3, padx=(4, 0))
        ttk.Label(form, text="响应路径：").grid(row=5, column=0, sticky="w", pady=3)
        self.c_path_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.c_path_var, width=30).grid(row=5, column=1, sticky="ew", pady=3, padx=(4, 0))
        tip = (
            "占位符：{text} 原文，{source} 源语言，{target} 目标语言\n"
            "响应路径示例：responseData.translatedText 或 data.translations[0].text"
        )
        ttk.Label(form, text=tip, foreground="#555", justify="left").grid(row=6, column=0, columnspan=2, sticky="w", pady=3)
        self._test_button(form, "custom", self.result_vars["自定义翻译源"], "自定义翻译源", row=7, columnspan=2)
        form.columnconfigure(1, weight=1)

        self._reload_custom_list()

    # ---------------------------------------------------------------- 词库
    def _build_glossary_tab(self, notebook):
        tab = ttk.Frame(notebook.body, padding=8)
        notebook.add(tab, text="自定义词库")
        self._build_glossary_content(tab)

    def _build_glossary_content(self, parent):
        self.g_entries = glossary_mod.load_entries()

        paned = ttk.Panedwindow(parent, orient="vertical")
        paned.pack(fill="both", expand=True)

        # ---- 上：手动词条 ----
        top = ttk.Frame(paned, padding=4)
        paned.add(top, weight=1)
        bar = ttk.Frame(top)
        bar.pack(fill="x")
        self.g_case_var = tk.BooleanVar(value=bool(self.cfg.get("glossary", {}).get("case_sensitive", False)))
        g_case_cb = make_checkbutton(bar, "区分大小写（子串/整词模式）", self.g_case_var)
        g_case_cb.config(command=self._auto_save)
        g_case_cb.pack(side="left")
        ttk.Label(bar, text="手动词条: " + glossary_mod.glossary_path(), foreground="#555").pack(side="left", padx=12)

        tree_frame = ttk.Frame(top)
        tree_frame.pack(fill="both", expand=True, pady=4)
        cols = ("on", "src", "tgt", "mode")
        self.g_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse", height=4)
        self.g_tree.heading("on", text="启用")
        self.g_tree.heading("src", text="原文")
        self.g_tree.heading("tgt", text="译文")
        self.g_tree.heading("mode", text="匹配方式")
        self.g_tree.column("on", width=46, anchor="center", stretch=False)
        self.g_tree.column("src", width=200, anchor="w")
        self.g_tree.column("tgt", width=200, anchor="w")
        self.g_tree.column("mode", width=90, anchor="center", stretch=False)
        vsb = ThumbScrollbar(tree_frame, command=self.g_tree.yview)
        self.g_tree.configure(yscrollcommand=vsb.set)
        self.g_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.g_tree.bind("<Double-1>", lambda _e: self._glossary_edit_dialog())

        btns = ttk.Frame(top)
        btns.pack(fill="x")
        for text, cmd in (
            ("添加", lambda: self._glossary_edit_dialog()),
            ("修改", lambda: self._glossary_edit_dialog(self._glossary_selected())),
            ("删除", self._glossary_delete),
            ("上移", lambda: self._glossary_move(-1)),
            ("下移", lambda: self._glossary_move(1)),
            ("清空", self._glossary_clear),
            ("导入CSV", self._glossary_import),
            ("导出CSV", self._glossary_export),
        ):
            RoundedButton(btns, text, cmd, style="gray").pack(side="left", padx=2, pady=2)

        tip = (
            "用法：先把词条原文替换成占位符再交给云端翻译，翻译完再还原成词库译文，保证词条不被云翻译乱翻。\n"
            "• 子串匹配：原文出现在文件名任何位置都生效；整词匹配：按英文单词边界匹配（不会误伤 concatenate 里的 cat）。\n"
            "• 正则表达式：原文填正则，译文可用 \\1 引用捕获组（例如原文 EP(\\d+) -> 译文 第\\1集）。\n"
            "• 译文与原文相同时用于“保留原名”，例如乐队名 Deep Purple -> Deep Purple。\n"
            "• 也可以直接用 Excel 编辑 词库\\默认词库.csv（UTF-8 编码，带表头：原文,译文,匹配方式,启用）。"
        )
        ttk.Label(top, text=tip, justify="left", foreground="#555").pack(anchor="w", pady=(4, 0))
        self._reload_glossary_tree()

        # ---- 下：词库文件 ----
        bottom = ttk.Frame(paned, padding=4)
        paned.add(bottom, weight=1)
        try:
            paned.paneconfigure(top, weight=1, minsize=240)
            paned.paneconfigure(bottom, weight=1, minsize=190)
        except tk.TclError:
            pass
        self._build_glossary_files_pane(bottom)

    def _build_glossary_files_pane(self, parent):
        # 先放底部按钮，保证窗口再小按钮也可见
        btns = ttk.Frame(parent)
        btns.pack(side="bottom", fill="x")
        for text, cmd in (
            ("勾选全库", lambda: self._gfile_set_all(True)),
            ("全部取消", lambda: self._gfile_set_all(False)),
            ("刷新", self._reload_glossary_files),
            ("打开词库文件夹", self._gfile_open_folder),
            ("知名词库", self._open_famous_glossaries),
        ):
            RoundedButton(btns, text, cmd, style="gray").pack(side="left", padx=2, pady=2)

        canvas_frame = ttk.Frame(parent)
        canvas_frame.pack(fill="both", expand=True, pady=4)
        self.gfile_canvas = tk.Canvas(canvas_frame, bg="white", highlightthickness=1, highlightbackground="#b9cbea")
        vsb = ThumbScrollbar(canvas_frame, command=self.gfile_canvas.yview)
        self.gfile_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.gfile_canvas.pack(side="left", fill="both", expand=True)
        self.gfile_canvas.bind("<Configure>", self._gfile_relayout)
        self.gfile_canvas.bind("<MouseWheel>", self._gfile_on_wheel)

        head = ttk.Frame(parent)
        head.pack(side="top", fill="x")
        ttk.Label(
            head,
            text="词库文件",
        ).pack(side="left")
        self.gfile_status_var = tk.StringVar(value="扫描中...")
        ttk.Label(head, textvariable=self.gfile_status_var, foreground="#555").pack(side="right")

        self.gfile_selected = set(self.cfg.get("glossary", {}).get("files") or [])
        self.gfile_counts = {}
        self.gfile_files = []
        self.gfile_pending = 0
        self.gfile_item_map = {}
        self.gfile_layout_items = []
        self.gfile_collapsed = set()
        self.gfile_folder_labels = {}
        self.gfile_folder_checks = {}
        self._reload_glossary_files()

    def _reload_glossary_files(self):
        self.gfile_canvas.delete("all")
        self.gfile_item_map = {}
        self.gfile_layout_items = []
        self.gfile_folder_checks = {}
        self.gfile_counts = {}
        self.gfile_files = glossary_mod.scan_glossary_files()
        self._gfile_walk(self._gfile_build_tree(), 0, "")
        self._gfile_start_count()
        self._gfile_relayout()

    def _gfile_build_tree(self):
        tree = {}
        for info in self.gfile_files:
            parts = info["rel"].split("/")
            node = tree
            for p in parts[:-1]:
                node = node.setdefault(p, {})
            node.setdefault("__files__", []).append(info)
        return tree

    def _gfile_collect_rels(self, node):
        rels = [info["rel"] for info in node.get("__files__", [])]
        for key, child in node.items():
            if key != "__files__":
                rels.extend(self._gfile_collect_rels(child))
        return rels

    def _gfile_walk(self, node, depth, prefix):
        for info in sorted(node.get("__files__", []), key=lambda i: i["rel"]):
            self._gfile_add_file(info, depth)
        for folder in sorted(k for k in node if k != "__files__"):
            child = node[folder]
            rel_prefix = f"{folder}" if not prefix else f"{prefix}/{folder}"
            self._gfile_add_folder(folder, depth, rel_prefix)
            self._gfile_walk(child, depth + 1, rel_prefix)

    def _gfile_add_folder(self, name, depth, rel_prefix):
        collapsed = rel_prefix in self.gfile_collapsed
        arrow = "▸" if collapsed else "▾"
        level = min(depth, len(TITLE_COLORS) - 1)
        label = tk.Label(
            self.gfile_canvas,
            text=f"{arrow} {name}",
            bg=TITLE_COLORS[level],
            fg="white",
            font=TITLE_FONTS[level],
            anchor="w",
            padx=8,
            pady=3,
            cursor="hand2",
        )
        label.bind("<Button-1>", lambda _e: self._gfile_toggle_folder(rel_prefix))
        label.bind("<MouseWheel>", self._gfile_on_wheel)
        win_id = self.gfile_canvas.create_window((0, 0), window=label, anchor="nw")
        # 文件夹行右侧的对勾：勾选 = 选中该文件夹下所有文件
        cb_var = tk.BooleanVar(value=False)
        cb = tk.Checkbutton(
            self.gfile_canvas,
            variable=cb_var,
            bg=TITLE_COLORS[level],
            activebackground=TITLE_COLORS[level],
            selectcolor="white",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=lambda: self._gfile_toggle_folder_check(rel_prefix),
        )
        cb.bind("<MouseWheel>", self._gfile_on_wheel)
        cb_win = self.gfile_canvas.create_window((0, 0), window=cb, anchor="nw")
        self.gfile_folder_checks[rel_prefix] = (cb_var, cb, cb_win, TITLE_COLORS[level])
        self.gfile_layout_items.append(("folder", label, win_id, depth, rel_prefix))
        self.gfile_folder_labels[rel_prefix] = (label, name, depth)

    def _gfile_collect_rels_for_prefix(self, rel_prefix):
        return [info["rel"] for info in self.gfile_files if info["rel"].startswith(rel_prefix + "/")]

    def _gfile_toggle_folder_check(self, rel_prefix):
        rels = self._gfile_collect_rels_for_prefix(rel_prefix)
        if not rels:
            return
        all_on = all(r in self.gfile_selected for r in rels)
        for r in rels:
            if all_on:
                self.gfile_selected.discard(r)
            else:
                self.gfile_selected.add(r)
        self._gfile_save_selection()
        self._gfile_paint_items()

    def _gfile_toggle_folder(self, rel_prefix):
        if rel_prefix in self.gfile_collapsed:
            self.gfile_collapsed.discard(rel_prefix)
        else:
            self.gfile_collapsed.add(rel_prefix)
        info = self.gfile_folder_labels.get(rel_prefix)
        if info:
            label, name, depth = info
            arrow = "▸" if rel_prefix in self.gfile_collapsed else "▾"
            label.config(text=f"{arrow} {name}")
        self._gfile_relayout()

    def _gfile_add_file(self, info, depth):
        rel = info["rel"]
        base = os.path.splitext(os.path.basename(rel))[0]
        var = tk.BooleanVar(value=rel in self.gfile_selected)
        cb = tk.Checkbutton(
            self.gfile_canvas,
            text=base,
            variable=var,
            bg="white",
            fg="#1d2b44",
            activebackground="white",
            activeforeground="#1d2b44",
            selectcolor="white",
            anchor="w",
            bd=0,
            highlightthickness=0,
            padx=2,
            font=("Microsoft YaHei UI", 9),
            cursor="hand2",
            command=self._make_gfile_toggle(rel, var),
        )
        cb.bind("<MouseWheel>", self._gfile_on_wheel)
        self.gfile_counts[rel] = ""
        self.gfile_item_map[rel] = {"var": var, "cb": cb, "base": base}
        win_id = self.gfile_canvas.create_window((0, 0), window=cb, anchor="nw")
        self.gfile_layout_items.append(("file", cb, win_id, depth, rel))

    def _gfile_relayout(self, _event=None):
        """流式布局：文件夹独占一行；文件每行至少 2 个，随宽度换行增多。"""
        w = max(self.gfile_canvas.winfo_width(), 2)
        margin = 6
        x = margin
        y = 4
        row_h = 33
        for item in self.gfile_layout_items:
            if item[0] == "file":
                row_h = item[1].winfo_reqheight() + 3
                break
        line_count = 0
        for kind, widget, win_id, depth, _rel in self.gfile_layout_items:
            hidden = bool(_rel) and any(_rel.startswith(p + "/") for p in self.gfile_collapsed)
            self.gfile_canvas.itemconfigure(win_id, state="hidden" if hidden else "normal")
            cb_info = self.gfile_folder_checks.get(_rel) if kind == "folder" else None
            if cb_info is not None:
                self.gfile_canvas.itemconfigure(cb_info[2], state="hidden" if hidden else "normal")
            if hidden:
                continue
            if kind == "folder":
                if line_count > 0:
                    y += row_h  # 上一行还有文件时，先换到新的一行
                x0 = margin if depth == 0 else margin + depth * 24
                # 右侧预留对勾位置
                self.gfile_canvas.coords(win_id, x0, y)
                self.gfile_canvas.itemconfigure(win_id, width=max(w - x0 - 30, 40))
                if cb_info is not None:
                    cb_h = cb_info[1].winfo_reqheight()
                    lh = widget.winfo_reqheight()
                    self.gfile_canvas.coords(cb_info[2], w - 26, y + (lh - cb_h) // 2)
                y += widget.winfo_reqheight()
                line_count = 0
            else:
                if line_count == 0:
                    x = margin + depth * 24
                item_w = widget.winfo_reqwidth()
                if line_count >= 2 and x + item_w > w - margin:
                    x = margin + depth * 24
                    y += row_h
                    line_count = 0
                self.gfile_canvas.coords(win_id, x, y)
                x += item_w + 10
                line_count += 1
        self.gfile_canvas.configure(scrollregion=(0, 0, w, y + row_h + 10))

    def _gfile_on_wheel(self, event):
        if self.gfile_canvas.yview()[0] == 0.0 and event.delta > 0:
            return
        self.gfile_canvas.yview_scroll(int(-event.delta / 120), "units")

    def _make_gfile_toggle(self, rel, var):
        def cmd():
            if var.get():
                self.gfile_selected.add(rel)
            else:
                self.gfile_selected.discard(rel)
            self._gfile_save_selection()
            self._gfile_update_summary()

        return cmd

    def _gfile_toggle_rels(self, rels):
        if not rels:
            return
        all_on = all(r in self.gfile_selected for r in rels)
        for r in rels:
            if all_on:
                self.gfile_selected.discard(r)
            else:
                self.gfile_selected.add(r)
        self._gfile_save_selection()
        self._gfile_paint_items()

    def _gfile_paint_items(self):
        for rel, info in self.gfile_item_map.items():
            info["var"].set(rel in self.gfile_selected)
        for rel_prefix, (var, _cb, _win, _bg) in self.gfile_folder_checks.items():
            rels = self._gfile_collect_rels_for_prefix(rel_prefix)
            var.set(bool(rels) and all(r in self.gfile_selected for r in rels))
        self._gfile_update_summary()

    def _gfile_start_count(self):
        files = list(self.gfile_files)
        self.gfile_pending = len(files)
        if not files:
            self.gfile_status_var.set("词库目录为空，把词库文件放入 词库/ 下对应格式的文件夹即可。")
            return

        def worker():
            for info in files:
                ents, err = glossary_mod.parse_file(info["path"])
                self.file_queue.put(("fcount", info["rel"], len(ents), err or ""))

        threading.Thread(target=worker, daemon=True).start()

    def _gfile_on_count(self, rel, count, err):
        if rel in self.gfile_counts:
            self.gfile_counts[rel] = count
            if err:
                self.gfile_status_var.set(f"{rel}: {err}")
        self.gfile_pending = max(0, self.gfile_pending - 1)
        if self.gfile_pending == 0:
            self._gfile_update_summary()

    def _gfile_update_summary(self):
        selected = sorted(rel for rel in self.gfile_selected if rel in self.gfile_counts)
        total_words = sum(self.gfile_counts.get(rel, 0) for rel in selected)
        self.gfile_status_var.set(f"已勾选 {len(selected)}/{len(self.gfile_files)} 个文件，共 {total_words} 词条")

    def _gfile_save_selection(self):
        self.cfg["glossary"]["files"] = sorted(self.gfile_selected)
        cfg_mod.save_config(self.cfg)

    def _gfile_set_all(self, on):
        for info in self.gfile_files:
            if on:
                self.gfile_selected.add(info["rel"])
            else:
                self.gfile_selected.discard(info["rel"])
        self._gfile_save_selection()
        self._gfile_paint_items()

    def _gfile_open_folder(self):
        try:
            glossary_mod.ensure_glossary_structure()
            subprocess.Popen(["explorer", os.path.normpath(glossary_mod.glossary_dir())])
        except OSError:
            pass

    def _open_famous_glossaries(self):
        """知名词库弹窗：列出常用词库，带下载链接与简介。"""
        dlg = tk.Toplevel(self)
        dlg.title("知名词库")
        dlg.configure(bg=APP_BG)
        dlg.transient(self)
        dlg.grab_set()
        center_window(dlg, 680, 620)

        header = ttk.Frame(dlg)
        header.pack(fill="x", padx=12, pady=(10, 4))
        ttk.Label(header, text="知名词库（点击名称打开链接，可下载后放入 词库/ 对应格式文件夹）：").pack(anchor="w")

        body = ttk.Frame(dlg)
        body.pack(fill="both", expand=True, padx=(12, 0), pady=4)
        canvas = tk.Canvas(body, bg="white", highlightthickness=1, highlightbackground="#b9cbea")
        scroll = ThumbScrollbar(body, command=canvas.yview)
        inner = tk.Frame(canvas, bg="white")
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win_id, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        def on_wheel(event):
            if canvas.yview()[0] == 0.0 and event.delta > 0:
                return
            canvas.yview_scroll(int(-event.delta / 120), "units")

        dlg.bind("<MouseWheel>", on_wheel)

        for entry in glossary_mod.FAMOUS_GLOSSARIES:
            name, url, desc = entry[0], entry[1], entry[2]
            local_path = glossary_mod.find_famous_local(entry)
            row = tk.Frame(inner, bg="white")
            row.pack(fill="x", padx=8, pady=4)
            link = tk.Label(
                row,
                text=name,
                fg="#1e7e34" if local_path else "#0645ad",
                cursor="hand2",
                font=("Microsoft YaHei UI", 10, "underline"),
                bg="white",
                anchor="w",
            )
            link.pack(anchor="w")
            _click = {"after": None}
            link.bind(
                "<Button-1>",
                lambda _e, _l=link, _u=url, _st=_click: self._famous_single_click(_l, _u, _st),
            )
            link.bind(
                "<Double-1>",
                lambda _e, _l=link, _p=local_path, _st=_click: self._famous_double_click(_l, _p, _st),
            )
            tk.Label(
                row,
                text=desc,
                bg="white",
                fg="#555",
                font=("Microsoft YaHei UI", 9),
                anchor="w",
                justify="left",
                wraplength=600,
            ).pack(anchor="w", pady=(2, 0))

        bottom = ttk.Frame(dlg)
        bottom.pack(fill="x", padx=12, pady=8)
        RoundedButton(bottom, "关闭", dlg.destroy, style="gray").pack(side="right")
        return dlg

    def _famous_single_click(self, label, url, state):
        """知名词库：单击延迟后打开下载链接（双击会取消本次打开）。"""
        if state["after"] is not None:
            try:
                label.after_cancel(state["after"])
            except tk.TclError:
                pass
        state["after"] = label.after(280, lambda: webbrowser.open(url))

    def _famous_double_click(self, label, local_path, state):
        """知名词库：双击取消下载链接，改打开本地词库所在文件夹。"""
        if state["after"] is not None:
            try:
                label.after_cancel(state["after"])
            except tk.TclError:
                pass
            state["after"] = None
        if local_path:
            subprocess.Popen(["explorer", os.path.normpath(local_path)])

    def _glossary_selected(self):
        sel = self.g_tree.selection()
        if not sel:
            return None
        return self.g_tree.index(sel[0])

    def _reload_glossary_tree(self):
        self.g_tree.delete(*self.g_tree.get_children())
        for e in self.g_entries:
            self.g_tree.insert(
                "",
                "end",
                values=(
                    "☑" if e.get("enabled", True) else "☐",
                    e.get("source", ""),
                    e.get("target", ""),
                    glossary_mod.MATCH_MODE_NAMES.get(e.get("mode", "substring"), e.get("mode", "")),
                ),
            )

    def _glossary_save_file(self):
        try:
            glossary_mod.save_entries(self.g_entries)
        except OSError as e:
            messagebox.showerror("错误", f"词库保存失败：{e}", parent=self)

    def _glossary_edit_dialog(self, index=None):
        if index is not None and (index < 0 or index >= len(self.g_entries)):
            return
        dlg = tk.Toplevel(self)
        dlg.title("编辑词条" if index is not None else "添加词条")
        dlg.transient(self)
        dlg.grab_set()
        # 居中显示在设置窗口上方
        dlg.geometry("420x250")
        dlg.update_idletasks()
        w = dlg.winfo_width()
        h = dlg.winfo_height()
        x = self.winfo_rootx() + max(0, (self.winfo_width() - w) // 2)
        y = self.winfo_rooty() + max(0, (self.winfo_height() - h) // 2)
        dlg.geometry(f"+{x}+{y}")
        pad = {"padx": 6, "pady": 4}
        current = self.g_entries[index] if index is not None else None

        src_var = tk.StringVar(value=(current or {}).get("source", ""))
        tgt_var = tk.StringVar(value=(current or {}).get("target", ""))
        mode_var = tk.StringVar(value=glossary_mod.MATCH_MODE_NAMES.get((current or {}).get("mode", "substring"), "子串匹配"))
        enabled_var = tk.BooleanVar(value=(current or {}).get("enabled", True))

        ttk.Label(dlg, text="原文：").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(dlg, textvariable=src_var, width=40).grid(row=0, column=1, **pad)
        ttk.Label(dlg, text="译文：").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(dlg, textvariable=tgt_var, width=40).grid(row=1, column=1, **pad)
        ttk.Label(dlg, text="匹配方式：").grid(row=2, column=0, sticky="w", **pad)
        ttk.Combobox(
            dlg,
            textvariable=mode_var,
            values=list(glossary_mod.MATCH_MODE_NAMES.values()),
            state="readonly",
            width=16,
        ).grid(row=2, column=1, sticky="w", **pad)
        dlg.configure(bg=APP_BG)
        make_checkbutton(dlg, "启用该词条", enabled_var).grid(row=3, column=0, columnspan=2, sticky="w", **pad)

        def ok():
            source = src_var.get().strip()
            if not source:
                messagebox.showwarning("提示", "原文不能为空。", parent=dlg)
                return
            entry = {
                "source": source,
                "target": tgt_var.get().strip(),
                "mode": glossary_mod.MODE_BY_NAME.get(mode_var.get(), "substring"),
                "enabled": bool(enabled_var.get()),
            }
            if index is not None:
                self.g_entries[index] = entry
            else:
                self.g_entries.append(entry)
            self._reload_glossary_tree()
            self._glossary_save_file()
            dlg.destroy()

        RoundedButton(dlg, "确定", ok, style="blue").grid(row=4, column=0, pady=8)
        RoundedButton(dlg, "取消", dlg.destroy, style="gray").grid(row=4, column=1, pady=8)

    def _glossary_delete(self):
        idx = self._glossary_selected()
        if idx is None:
            return
        name = self.g_entries[idx].get("source", "")
        if messagebox.askyesno("确认", f"删除词条“{name}”？", parent=self):
            del self.g_entries[idx]
            self._reload_glossary_tree()
            self._glossary_save_file()

    def _glossary_move(self, delta):
        idx = self._glossary_selected()
        if idx is None:
            return
        target = idx + delta
        if target < 0 or target >= len(self.g_entries):
            return
        self.g_entries[idx], self.g_entries[target] = self.g_entries[target], self.g_entries[idx]
        self._reload_glossary_tree()
        self._glossary_save_file()
        self.g_tree.selection_set(self.g_tree.get_children()[target])

    def _glossary_clear(self):
        if not self.g_entries:
            return
        if messagebox.askyesno("确认", "清空全部词条？", parent=self):
            self.g_entries = []
            self._reload_glossary_tree()
            self._glossary_save_file()

    def _glossary_import(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")])
        if not path:
            return
        imported = []
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.reader(f))
            if rows and any("原文" in (cell or "") for cell in rows[0]):
                imported = glossary_mod.load_entries(path)
            else:
                # 无表头的两列 CSV：原文,译文
                for row in rows:
                    if len(row) >= 2 and row[0].strip():
                        imported.append(
                            {
                                "source": row[0].strip(),
                                "target": row[1].strip(),
                                "mode": "substring",
                                "enabled": True,
                            }
                        )
        except OSError as e:
            messagebox.showerror("错误", f"读取失败：{e}", parent=self)
            return
        if not imported:
            messagebox.showinfo("提示", "文件里没有可导入的词条。", parent=self)
            return
        self.g_entries.extend(imported)
        self._reload_glossary_tree()
        self._glossary_save_file()
        messagebox.showinfo("完成", f"已导入 {len(imported)} 条词条。", parent=self)

    def _glossary_export(self):
        if not self.g_entries:
            messagebox.showinfo("提示", "词库为空，无需导出。", parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv")],
            initialfile="默认词库.csv",
        )
        if not path:
            return
        try:
            glossary_mod.save_entries(self.g_entries, path)
            messagebox.showinfo("完成", f"已导出到：\n{path}", parent=self)
        except OSError as e:
            messagebox.showerror("错误", f"导出失败：{e}", parent=self)

    def _reload_custom_list(self):
        self.custom_list.delete(0, "end")
        for spec in self.cfg.get("custom_sources", []):
            self.custom_list.insert("end", spec.get("name", "未命名"))

    def _load_custom(self, _event=None):
        sel = self.custom_list.curselection()
        if not sel:
            return
        specs = self.cfg.get("custom_sources", [])
        if sel[0] >= len(specs):
            return
        spec = specs[sel[0]]
        self.c_name_var.set(spec.get("name", ""))
        self.c_method_var.set(spec.get("method", "GET"))
        self._set_text(self.c_url_text, spec.get("url", ""))
        self._set_text(self.c_headers_text, spec.get("headers", "{}"))
        self._set_text(self.c_body_text, spec.get("body", ""))
        self.c_path_var.set(spec.get("response_path", ""))

    @staticmethod
    def _set_text(widget, text):
        widget.delete("1.0", "end")
        widget.insert("1.0", text)

    def _new_custom(self):
        self.custom_list.selection_clear(0, "end")
        self.c_name_var.set("")
        self.c_method_var.set("GET")
        self._set_text(self.c_url_text, "https://example.com/api/translate?q={text}")
        self._set_text(self.c_headers_text, "{}")
        self._set_text(self.c_body_text, "")
        self.c_path_var.set("translatedText")

    def _custom_form_spec(self):
        return {
            "name": self.c_name_var.get().strip(),
            "url": self.c_url_text.get("1.0", "end").strip(),
            "method": self.c_method_var.get().strip() or "GET",
            "headers": self.c_headers_text.get("1.0", "end").strip() or "{}",
            "body": self.c_body_text.get("1.0", "end").strip(),
            "response_path": self.c_path_var.get().strip(),
        }

    def _save_custom(self):
        spec = self._custom_form_spec()
        if not spec["name"] or not spec["url"]:
            messagebox.showwarning("提示", "名称和请求 URL 不能为空。", parent=self)
            return False
        specs = self.cfg.setdefault("custom_sources", [])
        sel = self.custom_list.curselection()
        if sel and sel[0] < len(specs):
            specs[sel[0]] = spec
        else:
            for i, old in enumerate(specs):
                if old.get("name") == spec["name"]:
                    specs[i] = spec
                    break
            else:
                specs.append(spec)
        self._reload_custom_list()
        self._log_custom("已保存自定义翻译源。")
        cfg_mod.save_config(self.cfg)
        if self.on_saved:
            self.on_saved()
        return True

    def _delete_custom(self):
        sel = self.custom_list.curselection()
        if not sel:
            return
        specs = self.cfg.get("custom_sources", [])
        name = specs[sel[0]].get("name", "")
        if messagebox.askyesno("确认", f"删除自定义翻译源“{name}”？", parent=self):
            del specs[sel[0]]
            self._reload_custom_list()
            self._new_custom()
            cfg_mod.save_config(self.cfg)
            if self.on_saved:
                self.on_saved()

    # ---------------------------------------------------------------- 测试
    def _link_label(self, parent, url, row=None, col=1, sticky="w"):
        """可点击的链接标签（蓝色下划线，点击用浏览器打开）。"""
        lbl = tk.Label(
            parent,
            text=url,
            fg="#0645ad",
            cursor="hand2",
            font=("Microsoft YaHei UI", 9, "underline"),
        )
        if row is not None:
            lbl.grid(row=row, column=col, sticky=sticky, padx=(6, 0), pady=2)
        else:
            lbl.pack(anchor="w", pady=2)
        lbl.bind("<Button-1>", lambda _e: webbrowser.open(url))
        self._links.append(lbl)
        return lbl

    def _test_button(self, parent, engine_key, result_var, tab_key, row=None, columnspan=2):
        frame = ttk.Frame(parent)
        if row is not None:
            frame.grid(row=row, column=0, columnspan=columnspan, sticky="w", pady=(10, 0))
        else:
            frame.pack(anchor="w", pady=(12, 0))
        RoundedButton(frame, "测试翻译", lambda: self._run_test(engine_key, result_var, tab_key), style="blue").pack(side="left")
        ttk.Label(frame, textvariable=result_var, foreground="#0a7d32", wraplength=520).pack(side="left", padx=8)

    def _run_test(self, engine_key, result_var, tab_key):
        self._apply_form_to_cfg()
        if engine_key == "custom":
            spec = self._custom_form_spec()
            if not spec["name"] or not spec["url"]:
                result_var.set("失败: 请先填写自定义源的名称和请求 URL")
                self.notebook.set_status(tab_key, "fail")
                return
            engine = CustomHttpEngine(self.cfg, spec)
        else:
            try:
                engine = get_engine(self.cfg, engine_key)
            except EngineError as e:
                result_var.set(f"失败: {e}")
                self.notebook.set_status(tab_key, "fail")
                return
        result_var.set("测试中...")

        def worker():
            try:
                result = engine.translate("Hello, how are you? Test file name 2024", "auto", "zh-CN")
                self.test_queue.put(("ok", tab_key, result))
            except EngineError as e:
                self.test_queue.put(("err", tab_key, str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_test(self):
        try:
            while True:
                msg = self.test_queue.get_nowait()
                kind = msg[0]
                if kind in ("ok", "err"):
                    _k, tab_key, payload = msg
                    result_var = self.result_vars.get(tab_key)
                    if result_var is not None:
                        result_var.set(("成功: " if kind == "ok" else "失败: ") + payload)
                    self.notebook.set_status(tab_key, "ok" if kind == "ok" else "fail")
                elif kind == "models":
                    _k, provider, models = msg
                    box = self.ai_model_boxes.get(provider)
                    current = box.get() if box is not None else ""
                    values = list(models)
                    if current and current not in values:
                        values = [current] + values
                    if box is not None:
                        box["values"] = values
                    var = self.ai_balance_vars.get(provider)
                    if var is not None:
                        var.set(f"共 {len(models)} 个模型可选")
                elif kind == "models_err":
                    _k, provider, err = msg
                    var = self.ai_balance_vars.get(provider)
                    if var is not None:
                        var.set("")
                    messagebox.showerror("获取模型列表失败", err, parent=self)
                elif kind == "balance":
                    _k, provider, text = msg
                    var = self.ai_balance_vars.get(provider)
                    if var is not None:
                        var.set("余额：" + text)
                elif kind == "balance_err":
                    _k, provider, err = msg
                    var = self.ai_balance_vars.get(provider)
                    if var is not None:
                        var.set("")
                    messagebox.showerror("查询余额失败", err, parent=self)
                elif kind == "proxy_result":
                    self.proxy_test_var.set(msg[1])
                elif kind == "ipinfo":
                    info = msg[1]
                    self.ip_value_var.set(f"{info['flag']} {info['location']}（IP: {info['ip']}）")
                    self.ip_type_var.set(info["ip_type"])
                    self.risk_var.set(f"{info['score']} 分 · {info['risk_label']}")
                    self.risk_label_widget.config(foreground=info["risk_color"])
                elif kind == "ipinfo_err":
                    self.ip_value_var.set("查询失败：" + msg[1])
        except queue.Empty:
            pass
        try:
            while True:
                _kind, rel, count, err = self.file_queue.get_nowait()
                self._gfile_on_count(rel, count, err)
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(80, self._poll_test)

    def _log_custom(self, msg):
        self.result_vars["自定义翻译源"].set(msg)

    def _apply_form_to_cfg(self):
        self.cfg["proxy"] = self.proxy_var.get().strip()
        self.cfg["proxy_type"] = {"自动检测": "auto", "HTTP": "http", "SOCKS5": "socks5h"}.get(
            self.proxy_type_var.get(), "auto"
        )
        try:
            self.cfg["timeout"] = int(self.timeout_var.get())
        except ValueError:
            pass
        self.cfg["deepl"] = {
            "api_key": self.deepl_key_var.get().strip(),
            "api_type": "free" if self.deepl_type_var.get() == "免费版" else "pro",
        }
        self.cfg["yandex"] = {"api_key": self.yandex_key_var.get().strip()}
        self.cfg["baidu"] = {
            "appid": self.baidu_appid_var.get().strip(),
            "secret": self.baidu_secret_var.get().strip(),
        }
        self.cfg["volcengine"] = {
            "access_key": self.volcengine_access_key_var.get().strip(),
            "secret_key": self.volcengine_secret_key_var.get().strip(),
        }
        self.cfg["niutrans"] = {"api_key": self.niutrans_api_key_var.get().strip()}
        self.cfg["tencent"] = {
            "secret_id": self.tencent_secret_id_var.get().strip(),
            "secret_key": self.tencent_secret_key_var.get().strip(),
        }
        self.cfg["papago"] = {
            "client_id": self.papago_id_var.get().strip(),
            "client_secret": self.papago_secret_var.get().strip(),
        }
        # AI 模型：按预设渠道分块保存
        cfg_mod.ensure_ai_providers(self.cfg)
        ai = self.cfg["ai"]
        for name, form in getattr(self, "ai_forms", {}).items():
            prov = ai["providers"].setdefault(name, {})
            prov["base_url"] = form["base"].get().strip().rstrip("/")
            prov["api_key"] = form["key"].get().strip()
            prov["model"] = form["model"].get().strip()
            try:
                prov["temperature"] = float(form["temp"].get())
            except ValueError:
                pass
            prov["system_prompt"] = form["prompt"].get("1.0", "end").strip()

    def _on_tab_selected(self, text, _idx):
        """切换页签时自动保存当前修改。"""
        self._auto_save()

    def _update_default_label(self):
        default = self.cfg.get("default_settings_tab")
        self.default_label_var.set(
            f"当前默认：{default}" if default else "未设置默认（每次打开显示“通用”）"
        )

    def _on_tab_reordered(self, group, order_texts):
        """长按拖动排序后保存页签顺序。"""
        key = "group0" if group == 0 else "group1"
        self.cfg.setdefault("settings_tab_order", {})[key] = list(order_texts)
        cfg_mod.save_config(self.cfg)

    def _set_default(self):
        """把当前选中的渠道设为默认：打开设置定位到该页签，软件启动时默认翻译源也用它。"""
        if getattr(self, "glossary_only", False):
            return
        text = self.notebook.texts[self.notebook.current]
        self.cfg["default_settings_tab"] = text
        engine_key = self._tab_to_engine_key(text)
        if engine_key:
            self.cfg["engine"] = engine_key
        cfg_mod.save_config(self.cfg)
        self.notebook.set_default(text)
        self._update_default_label()

    def _tab_to_engine_key(self, text):
        """页签文字 -> 翻译源 key（通用/自定义翻译源 无法映射到具体引擎，返回 None）。"""
        mapping = {
            "谷歌翻译": "google",
            "DeepL": "deepl",
            "Yandex": "yandex",
            "百度翻译": "baidu",
            "火山翻译": "volcengine",
            "小牛翻译": "niutrans",
            "腾讯云": "tencent",
            "Bing 翻译": "bing",
            "Papago 翻译": "papago",
        }
        if text in mapping:
            return mapping[text]
        if text in cfg_mod.AI_PRESETS:
            return f"ai:{text}"
        return None

    def _auto_save(self):
        """把当前表单内容静默写入配置（无保存提示）。"""
        try:
            if not getattr(self, "glossary_only", False):
                self._apply_form_to_cfg()
                # 自定义翻译源表单有内容时自动保存
                if self.c_name_var.get().strip() or self.c_url_text.get("1.0", "end").strip():
                    self._save_custom()
            if hasattr(self, "g_case_var"):
                self.cfg["glossary"]["case_sensitive"] = bool(self.g_case_var.get())
            ok, _path = cfg_mod.save_config(self.cfg)
            if ok and self.on_saved:
                self.on_saved()
        except Exception:
            pass

    def _close_auto_save(self):
        """关闭窗口：先自动保存再销毁。"""
        self._auto_save()
        self.destroy()
