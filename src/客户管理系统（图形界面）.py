# -*- coding: utf-8 -*-
"""
============================================
        客户管理系统（图形界面版）
============================================
【这个版本解决了什么】
  老版本是"黑窗口"命令行：每填一项都要按一次回车。
  这个版本改成表单式界面 —— 像登录/注册页面那样，
  姓名、手机号、邮箱、来源、备注一次填完，点一次"保存"（或直接按回车）即可。

【界面说明】
  · 顶部：标题 + 常驻的客户总数（筛选时会变成"筛选出 M / 共 N"）
  · 上半部分：客户信息表单（一次性填完 → 点保存 / 按回车）
      填写有误时，出错的输入框变红，并在表单右上角直接说明哪里不对
  · 中间：搜索框（按姓名、手机号、邮箱、备注模糊搜索）+ 来源筛选
  · 下半部分：客户列表（鼠标划过有反馈，双击某一行 = 载入表单修改）
  · 底部：修改选中 / 删除选中 / 按来源统计 / 导出 CSV
  · 新增或修改成功后，对应那一行会短暂高亮，方便确认"存哪去了"

【数据保存位置】
  customers.db —— 就在本程序（或 exe）旁边，和老版本完全通用，
  旧数据会自动兼容（本版本会自动给数据表补上"备注"一列）。

【环境要求】
  · Python 3.x（自带 tkinter 和 sqlite3，无需安装任何第三方库）

【运行方式】
  python "客户管理系统（图形界面）.py"
  （调试用：python "客户管理系统（图形界面）.py" --db 其他路径.db）
============================================
"""

from __future__ import annotations

import csv
import os
import re
import sqlite3
import sys
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

# ================== 基本配置 ==================

APP_TITLE = "客户管理系统"
ALL_SOURCES = "全部"
DEFAULT_SOURCES = ["朋友推荐", "广告", "网络", "其他"]
NO_EMAIL = "无"          # 没有邮箱时数据库里存这个字，保持和老版本一致
SEARCH_HINT = "姓名 / 手机号 / 邮箱 / 备注"      # 搜索框灰字提示

# 界面设计基准尺寸（在 100% 缩放下的理想窗口大小），高分屏会按比例放大
DESIGN_W, DESIGN_H = 1040, 680
MIN_W, MIN_H = 800, 620      # 最小尺寸要保证列表至少还能看到 4~5 行

# 配色：底色与卡片分层，蓝色只用在"主要动作"上，颜色都有明确用途
BG = "#F5F7FB"            # 窗口底色
CARD = "#FFFFFF"          # 卡片
BORDER = "#E3E8EF"        # 卡片描边
BORDER_SOFT = "#EEF1F6"   # 分隔线
TEXT = "#1F2937"          # 正文
TEXT_SUB = "#6B7280"      # 次要文字
TEXT_MUTED = "#9AA3AF"    # 占位提示文字
PRIMARY = "#2563EB"       # 主色（保存按钮、焦点）
PRIMARY_HOVER = "#1D4ED8"
PRIMARY_SOFT = "#EFF6FF"  # 主色浅底（计数标记、次级按钮）
DANGER = "#DC2626"
SUCCESS = "#059669"
FIELD_BORDER = "#CBD5E1"
FIELD_ERR = "#EF4444"     # 出错时的输入框描边
ROW_ALT = "#FAFBFD"       # 斑马纹
ROW_HOVER = "#F1F5F9"     # 鼠标划过
ROW_FLASH = "#DBEAFE"     # 新增/修改成功后的短暂高亮
HEAD_BG = "#F8FAFC"       # 表头


def app_dir() -> str:
    """
    程序所在目录。
    · 直接运行 .py 时 = 脚本所在目录
    · 打包成 exe 后 = exe 所在目录
      （打包后不能再用相对路径，否则数据会写进临时解压目录，一关就没）
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def enable_dpi_awareness() -> None:
    """
    告诉 Windows"本程序自己处理高 DPI"。
    必须在创建窗口（tk.Tk()）之前调用，否则窗口尺寸和实际 DPI 对不上，
    在高分屏上会出现窗口被撑到屏幕外面、字太小或太大等问题。
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)   # Win8.1 及以上
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()        # 更老的系统
    except Exception:
        pass


def system_dpi() -> int:
    """当前系统 DPI（96 = 100% 缩放，192 = 200% 缩放）。"""
    dpi = 96
    if sys.platform == "win32":
        try:
            import ctypes

            dpi = int(ctypes.windll.user32.GetDpiForSystem())
        except Exception:
            dpi = 96
    return dpi if 72 <= dpi <= 480 else 96


enable_dpi_awareness()   # 注意：必须在下面创建 Tk 窗口之前执行


def resolve_db_path() -> str:
    """数据库文件路径；支持 --db 参数临时指定（方便测试）。"""
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == "--db" and i + 1 < len(argv):
            return os.path.abspath(argv[i + 1])
    return os.path.join(app_dir(), "customers.db")


# ================== 格式校验（规则和老版本一致） ==================

def is_valid_phone(phone: str) -> bool:
    """中国大陆手机号：1 开头，第二位 3-9，共 11 位。"""
    return re.match(r"^1[3-9]\d{9}$", phone) is not None


def is_valid_email(email: str) -> bool:
    """邮箱格式；没有邮箱时留空或填"无"都算合法。"""
    if email in ("", NO_EMAIL):
        return True
    return re.match(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$", email) is not None


def normalize_email(email: str) -> str:
    """空邮箱统一存成"无"，和老数据保持一致。"""
    return email if email else NO_EMAIL


# ================== 数据层 ==================

class CustomerDB:
    """所有数据库操作都收在这里，界面层不直接碰 SQL。"""

    def __init__(self, path: str):
        self.path = path
        self.init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = None
        return conn

    def init_db(self) -> None:
        """建表；如果是从老版本升级过来的库，自动补上 remark（备注）列。"""
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS customers (
                    id     INTEGER PRIMARY KEY AUTOINCREMENT,
                    name   TEXT NOT NULL,
                    phone  TEXT NOT NULL,
                    email  TEXT NOT NULL,
                    source TEXT NOT NULL
                )
                """
            )
            columns = [row[1] for row in conn.execute("PRAGMA table_info(customers)")]
            if "remark" not in columns:
                conn.execute(
                    "ALTER TABLE customers ADD COLUMN remark TEXT NOT NULL DEFAULT ''"
                )
            conn.commit()
        finally:
            conn.close()

    # ---------- 增 ----------
    def add(self, name, phone, email, source, remark) -> int:
        conn = self._connect()
        try:
            cur = conn.execute(
                "INSERT INTO customers (name, phone, email, source, remark) "
                "VALUES (?, ?, ?, ?, ?)",
                (name, phone, email, source, remark),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    # ---------- 改 ----------
    def update(self, cid, name, phone, email, source, remark) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE customers SET name = ?, phone = ?, email = ?, "
                "source = ?, remark = ? WHERE id = ?",
                (name, phone, email, source, remark, cid),
            )
            conn.commit()
        finally:
            conn.close()

    # ---------- 删 ----------
    def delete(self, cid) -> None:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM customers WHERE id = ?", (cid,))
            conn.commit()
        finally:
            conn.close()

    # ---------- 查（带搜索和来源筛选） ----------
    def fetch(self, keyword: str = "", source: str = ALL_SOURCES):
        conn = self._connect()
        try:
            sql = "SELECT id, name, phone, email, source, remark FROM customers"
            where, params = [], []
            if keyword:
                like = f"%{keyword}%"
                where.append(
                    "(name LIKE ? OR phone LIKE ? OR email LIKE ? "
                    "OR source LIKE ? OR remark LIKE ?)"
                )
                params += [like] * 5
            if source and source != ALL_SOURCES:
                where.append("source = ?")
                params.append(source)
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY id"
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def get(self, cid):
        conn = self._connect()
        try:
            return conn.execute(
                "SELECT id, name, phone, email, source, remark FROM customers "
                "WHERE id = ?",
                (cid,),
            ).fetchone()
        finally:
            conn.close()

    def count_all(self) -> int:
        conn = self._connect()
        try:
            return int(conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0])
        finally:
            conn.close()

    def count_by_source(self):
        conn = self._connect()
        try:
            return conn.execute(
                "SELECT source, COUNT(*) FROM customers "
                "GROUP BY source ORDER BY COUNT(*) DESC, source"
            ).fetchall()
        finally:
            conn.close()

    def all_sources(self):
        """数据库里出现过的所有来源（含用户自定义的），用于筛选下拉框。"""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT DISTINCT source FROM customers WHERE source <> '' ORDER BY source"
            ).fetchall()
            return [r[0] for r in rows]
        finally:
            conn.close()


# ================== 界面 ==================

class CustomerApp(tk.Tk):
    def __init__(self, db: CustomerDB):
        super().__init__()
        self.db = db
        self.editing_id = None      # None = 新增模式；否则为正在修改的客户 ID
        self.rows = []              # 当前列表数据
        self.sort_col = None
        self.sort_desc = False
        self._base_tags = {}        # 每行的斑马纹标签，鼠标划过/高亮后要还原
        self._hover_iid = None
        self._flash_iid = None
        self._form_msg_job = None
        self._scrim = None
        self._scrim_bind = None

        self.title(APP_TITLE)
        self.configure(bg=BG)

        self._setup_dpi_and_fonts()
        self._setup_style()
        self._build_ui()
        self._center_window()
        self.refresh()
        self.after(150, self.entry_name.focus_set)

    # ---------- 初始化辅助 ----------

    def _setup_dpi_and_fonts(self) -> None:
        """按屏幕 DPI 决定整体缩放：高分屏放大，小屏幕自动收敛，保证界面放得下。"""
        raw = system_dpi() / 96.0

        # 屏幕装不下这么大的界面就自动缩小（例如 1280x800 的屏幕不该用 2 倍缩放）
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        fits = min(screen_w / DESIGN_W, screen_h / DESIGN_H)
        self.scale = max(0.85, min(raw, fits))
        try:
            # Tk 的字体按"点"计算，这里让字号跟着缩放一起走
            self.tk.call("tk", "scaling", self.scale * 96.0 / 72.0)
        except tk.TclError:
            self.scale = 1.0

        families = set(tkfont.families(self))
        self.font_family = "TkDefaultFont"
        for name in ("Microsoft YaHei UI", "Microsoft YaHei", "微软雅黑",
                     "SimHei", "SimSun"):
            if name in families:
                self.font_family = name
                break

        # 字号只用四档，靠"字重 + 大小"建立层次，避免满屏都是不同的字号
        f = self.font_family
        self.F_TITLE = (f, 16, "bold")     # 页面标题
        self.F_CARD = (f, 12, "bold")      # 卡片标题
        self.F_BODY = (f, 11)              # 正文 / 输入框 / 按钮
        self.F_CAPTION = (f, 10)           # 辅助说明

    def s(self, px: int) -> int:
        """把设计稿像素换算成当前缩放下的像素。"""
        return max(1, int(round(px * self.scale)))

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")   # clam 主题最好配色，界面更干净
        except tk.TclError:
            pass

        style.configure(
            "Treeview",
            background=CARD,
            fieldbackground=CARD,
            foreground=TEXT,
            rowheight=self.s(30),
            font=self.F_CAPTION,
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background=HEAD_BG,
            foreground=TEXT_SUB,
            font=(self.font_family, 10, "bold"),
            relief="flat",
            padding=(self.s(6), self.s(7)),
        )
        style.map("Treeview.Heading", background=[("active", "#EEF2F7")])
        style.map(
            "Treeview",
            background=[("selected", "#DBEAFE")],
            foreground=[("selected", TEXT)],
        )
        style.configure(
            "TCombobox",
            fieldbackground=CARD,
            background=CARD,
            foreground=TEXT,
            arrowcolor=TEXT_SUB,
            bordercolor=FIELD_BORDER,
            padding=self.s(4),
        )
        self.option_add("*TCombobox*Listbox.font", self.F_BODY)
        self.option_add("*TCombobox*Listbox.background", CARD)
        self.option_add("*TCombobox*Listbox.selectBackground", PRIMARY)
        self.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")
        style.configure("Vertical.TScrollbar", background="#E2E8F0",
                        troughcolor=BG, bordercolor=BG, arrowcolor=TEXT_SUB)

    def _center_window(self) -> None:
        w = min(self.s(DESIGN_W), int(self.winfo_screenwidth() * 0.96))
        h = min(self.s(DESIGN_H), int(self.winfo_screenheight() * 0.92))
        x = max(0, (self.winfo_screenwidth() - w) // 2)
        y = max(0, (self.winfo_screenheight() - h) // 3)
        self.minsize(min(self.s(MIN_W), w), min(self.s(MIN_H), h))
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _make_card(self, parent) -> tk.Frame:
        """白底卡片 + 1px 描边，用来把不同区域分开。"""
        return tk.Frame(parent, bg=CARD, highlightthickness=1,
                        highlightbackground=BORDER, highlightcolor=BORDER)

    def _make_entry(self, parent, var, width=20) -> tk.Entry:
        return tk.Entry(
            parent,
            textvariable=var,
            font=self.F_BODY,
            width=width,
            relief="flat",
            bd=0,
            bg=CARD,
            fg=TEXT,
            insertbackground=PRIMARY,
            highlightthickness=1,
            highlightbackground=FIELD_BORDER,
            highlightcolor=PRIMARY,
        )

    def _make_button(self, parent, text, command, kind="normal", width=None):
        """自己画按钮，方便控制配色与反馈（ttk 按钮在 Windows 上不好改配色）。"""
        colors = {
            "primary": (PRIMARY, "#FFFFFF", PRIMARY_HOVER, PRIMARY),
            "normal": ("#FFFFFF", TEXT, "#F1F5F9", BORDER),
            "danger": ("#FFFFFF", DANGER, "#FEF2F2", BORDER),
            "ghost": (PRIMARY_SOFT, PRIMARY, "#DBEAFE", PRIMARY_SOFT),
        }
        bg, fg, hover, ring = colors.get(kind, colors["normal"])
        primary = kind == "primary"
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            font=self.F_BODY,
            bg=bg,
            fg=fg,
            activebackground=hover,
            activeforeground=fg,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=self.s(20 if primary else 14),
            pady=self.s(8 if primary else 7),
            takefocus=True,
            highlightthickness=1,
            highlightbackground=ring,
            highlightcolor=PRIMARY,     # 键盘 Tab 选中时有可见的焦点框
        )
        if width:
            btn.configure(width=width)
        # 鼠标悬停换底色：即时反馈，不加过渡动画（悬停一天要发生几十次）
        btn.bind("<Enter>", lambda e: btn.configure(bg=hover))
        btn.bind("<Leave>", lambda e: btn.configure(bg=bg))
        return btn

    def _separator(self, parent):
        """操作栏里的细竖线，用来分组。"""
        return tk.Frame(parent, bg=BORDER, width=self.s(1), height=self.s(18))

    # ---------- 搭建界面 ----------

    def _build_ui(self) -> None:
        pad = self.s(16)

        # —— 顶部：标题 + 常驻计数 ——
        # 计数放这里（而不是状态栏），因为它需要一直看得见；
        # 状态栏只留给"刚发生了什么"的临时反馈，两者不再互相覆盖。
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=pad, pady=(self.s(14), self.s(10)))
        left = tk.Frame(header, bg=BG)
        left.pack(side="left")
        tk.Label(left, text=APP_TITLE, font=self.F_TITLE, bg=BG, fg=TEXT).pack(anchor="w")
        tk.Label(left, text="填完按回车即可保存", font=self.F_CAPTION,
                 bg=BG, fg=TEXT_SUB).pack(anchor="w", pady=(self.s(2), 0))

        self.count_var = tk.StringVar(value="共 0 位客户")
        self.count_chip = tk.Label(header, textvariable=self.count_var,
                                   font=(self.font_family, 10, "bold"),
                                   bg=PRIMARY_SOFT, fg=PRIMARY,
                                   padx=self.s(12), pady=self.s(6))
        self.count_chip.pack(side="right")

        # —— 表单卡片 ——
        card = self._make_card(self)
        card.pack(fill="x", padx=pad)
        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill="x", padx=self.s(18), pady=self.s(13))

        # 表单标题在左，校验/成功提示在右 —— 提示紧挨着出问题的地方，不用往窗口底部找
        self.form_title_var = tk.StringVar(value="新增客户")
        tk.Label(inner, textvariable=self.form_title_var, font=self.F_CARD,
                 bg=CARD, fg=TEXT).grid(row=0, column=0, columnspan=2, sticky="w")
        self.form_msg_var = tk.StringVar(value="")
        self.form_msg = tk.Label(inner, textvariable=self.form_msg_var,
                                 font=self.F_CAPTION, bg=CARD, fg=DANGER,
                                 anchor="e", justify="right")
        self.form_msg.grid(row=0, column=2, columnspan=2, sticky="e")

        self.var_name = tk.StringVar()
        self.var_phone = tk.StringVar()
        self.var_email = tk.StringVar()
        self.var_source = tk.StringVar(value="其他")
        self.var_remark = tk.StringVar()

        inner.grid_columnconfigure(1, weight=1)
        inner.grid_columnconfigure(3, weight=1)

        self.entry_name = self._field(inner, 1, 0, "姓名 *", self.var_name)
        self.entry_phone = self._field(inner, 1, 2, "手机号 *", self.var_phone)
        self.entry_email = self._field(inner, 2, 0, "邮箱", self.var_email)
        self.entry_remark = self._field(inner, 3, 0, "备注", self.var_remark, span=3)

        # 来源下拉框（可自己输入新的来源）
        self._field_label(inner, 2, 2, "来源")
        self.cmb_source = ttk.Combobox(
            inner, textvariable=self.var_source, values=DEFAULT_SOURCES,
            font=self.F_BODY, state="normal",
        )
        self.cmb_source.grid(row=2, column=3, sticky="ew", pady=self.s(5))

        # 表单按钮：主按钮（保存）最重，其余依次减弱
        btns = tk.Frame(inner, bg=CARD)
        btns.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(self.s(12), 0))
        self.btn_save = self._make_button(btns, "保存", self.on_save, kind="primary")
        self.btn_save.pack(side="left")
        self.btn_clear = self._make_button(btns, "清空重填", self.clear_form)
        self.btn_clear.pack(side="left", padx=self.s(8))
        self.btn_cancel_edit = self._make_button(btns, "取消修改", self.cancel_edit,
                                                 kind="ghost")
        self.btn_hint = tk.Label(btns, text="回车 = 保存　Esc = 清空",
                                 font=self.F_CAPTION, bg=CARD, fg=TEXT_MUTED)
        self.btn_hint.pack(side="right")

        # —— 搜索栏 ——
        search_bar = tk.Frame(self, bg=BG)
        search_bar.pack(fill="x", padx=pad, pady=(self.s(14), self.s(8)))
        tk.Label(search_bar, text="搜索", font=self.F_BODY, bg=BG,
                 fg=TEXT).pack(side="left")
        self.var_search = tk.StringVar()
        self.entry_search = tk.Entry(
            search_bar, textvariable=self.var_search, font=self.F_BODY,
            relief="flat", bd=0, bg=CARD, fg=TEXT_MUTED, insertbackground=PRIMARY,
            highlightthickness=1, highlightbackground=FIELD_BORDER,
            highlightcolor=PRIMARY,
        )
        self.entry_search.pack(side="left", fill="x", expand=True,
                               padx=self.s(8), ipady=self.s(6))
        self.entry_search.bind("<KeyRelease>", lambda e: self.refresh())
        self._attach_placeholder(self.entry_search, self.var_search, SEARCH_HINT)

        tk.Label(search_bar, text="来源", font=self.F_BODY, bg=BG,
                 fg=TEXT).pack(side="left")
        self.var_filter_source = tk.StringVar(value=ALL_SOURCES)
        self.cmb_filter = ttk.Combobox(
            search_bar, textvariable=self.var_filter_source,
            values=[ALL_SOURCES], font=self.F_BODY, state="readonly", width=10,
        )
        self.cmb_filter.pack(side="left", padx=self.s(8))
        self.cmb_filter.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        # "清空筛选"只在真的有筛选时才出现，平时不占视觉噪音
        self.btn_clear_filter = self._make_button(search_bar, "清空筛选",
                                                  self.clear_filter, kind="ghost")

        # —— 客户列表 ——
        # 注意：表格是唯一会"抢占剩余空间"的控件，所以它必须最后 pack，
        # 否则窗口不够高时，底部按钮和状态栏会被挤出可视区域。
        table_card = self._make_card(self)
        table_wrap = tk.Frame(table_card, bg=CARD)
        table_wrap.pack(fill="both", expand=True, padx=1, pady=1)

        columns = ("id", "name", "phone", "email", "source", "remark")
        self.tree = ttk.Treeview(table_wrap, columns=columns, show="headings",
                                 selectmode="browse", height=8)
        self._headings = {
            # 列宽合计要能塞进最小窗口宽度，否则最后几列会被切掉看不见
            "id": ("ID", 50, "center"),
            "name": ("姓名", 110, "w"),
            "phone": ("手机号", 130, "w"),
            "email": ("邮箱", 190, "w"),
            "source": ("来源", 90, "center"),
            "remark": ("备注", 170, "w"),
        }
        for col, (text, width, anchor) in self._headings.items():
            self.tree.heading(col, text=text, command=lambda c=col: self.sort_by(c))
            self.tree.column(col, width=self.s(width), anchor=anchor,
                             stretch=(col == "remark"))
        self.tree.tag_configure("odd", background=ROW_ALT)
        self.tree.tag_configure("hover", background=ROW_HOVER)
        self.tree.tag_configure("flash", background=ROW_FLASH)
        vsb = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self.on_row_double_click)
        self.tree.bind("<Delete>", lambda e: self.delete_selected())
        self.tree.bind("<Motion>", self._on_tree_motion)
        self.tree.bind("<Leave>", lambda e: self._set_hover(None))

        # 空列表时的引导文字（叠在表格中间，有数据就隐藏）
        self.empty_label = tk.Label(table_wrap, text="", font=self.F_BODY,
                                    bg=CARD, fg=TEXT_SUB, justify="center")

        # —— 底部操作栏 ——
        actions = tk.Frame(self, bg=BG)
        self._make_button(actions, "修改选中", self.edit_selected, kind="ghost").pack(
            side="left")
        self._make_button(actions, "删除选中", self.delete_selected, kind="danger").pack(
            side="left", padx=self.s(8))
        self._separator(actions).pack(side="left", padx=self.s(6), pady=self.s(4))
        self._make_button(actions, "刷新", self.refresh).pack(side="left", padx=self.s(6))
        self.btn_export = self._make_button(actions, "导出 Excel(CSV)", self.export_csv)
        self.btn_export.pack(side="right")
        self.btn_stats = self._make_button(actions, "按来源统计", self.show_stats)
        self.btn_stats.pack(side="right", padx=self.s(8))

        # —— 状态栏（只显示"刚发生了什么"） ——
        self.status_var = tk.StringVar(value="提示：在列表中双击某一行可直接修改")
        self.status = tk.Label(self, textvariable=self.status_var, font=self.F_CAPTION,
                               bg="#EEF2F7", fg=TEXT_SUB, anchor="w",
                               padx=self.s(14), pady=self.s(7))
        status_line = tk.Frame(self, bg=BORDER, height=1)

        # 打包顺序说明（很重要，决定了窗口变小时谁先被挤掉）：
        #   1) 状态栏贴最底部   2) 操作栏在状态栏上方   3) 表格吃掉剩下的全部空间
        self.status.pack(side="bottom", fill="x")
        status_line.pack(side="bottom", fill="x")
        actions.pack(side="bottom", fill="x", padx=pad, pady=(self.s(4), self.s(10)))
        table_card.pack(fill="both", expand=True, padx=pad, pady=(0, self.s(2)))

        # —— 快捷键 ——
        for widget in (self.entry_name, self.entry_phone, self.entry_email,
                       self.entry_remark, self.cmb_source):
            widget.bind("<Return>", lambda e: self.on_save())
            widget.bind("<Escape>", lambda e: self.clear_form())
        self.bind("<Control-f>", self._focus_search)
        self.bind("<F5>", lambda e: self.refresh())

    def _focus_search(self, _event=None):
        self.entry_search.focus_set()
        self.entry_search.select_range(0, "end")
        return "break"

    # ---------- 表单字段 ----------

    def _field_label(self, parent, row, col, text) -> tk.Label:
        label = tk.Label(parent, text=text, font=self.F_BODY, bg=CARD, fg=TEXT)
        label.grid(row=row, column=col, sticky="e",
                   padx=(0 if col == 0 else self.s(20), self.s(8)), pady=self.s(5))
        return label

    def _field(self, parent, row, col, label, var, span=1) -> tk.Entry:
        """生成"标签 + 输入框"一列，返回输入框。"""
        self._field_label(parent, row, col, label)
        entry = self._make_entry(parent, var)
        entry.grid(row=row, column=col + 1, columnspan=span, sticky="ew",
                   pady=self.s(5), ipady=self.s(4))
        entry.bind("<KeyRelease>", lambda e, en=entry: self._clear_entry_error(en))
        return entry

    def _attach_placeholder(self, entry, var, text):
        """给输入框加灰色提示文字：一聚焦就消失，空着离开又出现。"""
        def show():
            if not var.get():
                var.set(text)
                entry.configure(fg=TEXT_MUTED)

        def hide(_event=None):
            if var.get() == text:
                var.set("")
                entry.configure(fg=TEXT)

        self._placeholder_show = show   # 清空筛选后需要重新显示提示
        entry.bind("<FocusIn>", hide, add="+")
        entry.bind("<FocusOut>", lambda e: show(), add="+")
        show()

    def _search_keyword(self) -> str:
        """搜索关键字；灰字提示不算关键字。"""
        value = self.var_search.get().strip()
        return "" if value == SEARCH_HINT else value

    # ---------- 状态与提示 ----------

    def set_status(self, text, kind="info"):
        """窗口底部的临时反馈（列表层面的操作结果）。"""
        color = {"info": TEXT_SUB, "ok": SUCCESS, "error": DANGER}.get(kind, TEXT_SUB)
        self.status_var.set(text)
        self.status.configure(fg=color)

    def show_form_msg(self, text, kind="error", auto_hide_ms=None):
        """表单右上角的提示（表单层面的校验结果与保存结果）。"""
        color = {"info": TEXT_SUB, "ok": SUCCESS, "error": DANGER}.get(kind, DANGER)
        self.form_msg_var.set(text)
        self.form_msg.configure(fg=color)
        if self._form_msg_job is not None:
            try:
                self.after_cancel(self._form_msg_job)
            except (tk.TclError, ValueError):
                pass
            self._form_msg_job = None
        if auto_hide_ms:
            self._form_msg_job = self.after(auto_hide_ms, self.clear_form_msg)

    def clear_form_msg(self):
        self._form_msg_job = None
        self.form_msg_var.set("")

    def _mark_entry_error(self, entry, message):
        entry.configure(highlightbackground=FIELD_ERR, highlightcolor=FIELD_ERR)
        entry.focus_set()
        self.show_form_msg(message, "error")
        self.bell()

    def _clear_entry_error(self, entry):
        if entry.cget("highlightbackground") == FIELD_ERR:
            entry.configure(highlightbackground=FIELD_BORDER, highlightcolor=PRIMARY)
            self.clear_form_msg()

    def _clear_all_errors(self):
        for entry in (self.entry_name, self.entry_phone, self.entry_email,
                      self.entry_remark):
            entry.configure(highlightbackground=FIELD_BORDER, highlightcolor=PRIMARY)

    # ---------- 表单逻辑 ----------

    def _collect_form(self):
        """读取并校验表单；全部通过返回字典，否则返回 None（同时高亮出错的那一项）。"""
        self._clear_all_errors()
        name = self.var_name.get().strip()
        phone = self.var_phone.get().strip()
        email = self.var_email.get().strip()
        source = self.var_source.get().strip() or "其他"
        remark = self.var_remark.get().strip()

        if not name:
            self._mark_entry_error(self.entry_name, "请填写客户姓名（必填）")
            return None
        if not is_valid_phone(phone):
            self._mark_entry_error(
                self.entry_phone, "手机号应为 11 位数字，如 13812345678")
            return None
        if not is_valid_email(email):
            self._mark_entry_error(
                self.entry_email, "邮箱格式不对，如 zhangsan@example.com；没有就留空")
            return None
        return {
            "name": name, "phone": phone, "email": normalize_email(email),
            "source": source, "remark": remark,
        }

    def on_save(self):
        """点“保存”/按回车：新增模式=插入新客户，修改模式=更新原客户。"""
        data = self._collect_form()
        if data is None:
            return
        editing = self.editing_id
        try:
            if editing is None:
                new_id = self.db.add(data["name"], data["phone"], data["email"],
                                     data["source"], data["remark"])
                message = f"已保存：{data['name']}（ID={new_id}）"
                hint = f"已保存「{data['name']}」，可以接着填下一位"
            else:
                new_id = editing
                self.db.update(editing, data["name"], data["phone"], data["email"],
                               data["source"], data["remark"])
                message = f"已修改：{data['name']}（ID={editing}）"
                hint = f"已修改「{data['name']}」"
        except sqlite3.Error as e:
            messagebox.showerror(APP_TITLE, f"保存失败：{e}", parent=self)
            return

        if editing is not None:
            self.cancel_edit(quiet=True)   # 退出修改模式，回到新增模式
        self.clear_form(keep_status=True)

        # 保存后如果这一行被当前的搜索/筛选挡住，就自动清掉筛选，
        # 否则用户会觉得"我刚存的东西不见了"
        hidden_by_filter = not self._matches_filter(new_id)
        if hidden_by_filter:
            self._reset_filters()
            hint += "（已自动清除筛选，方便你看到它）"

        self.refresh(flash_id=new_id)
        self.show_form_msg(message, "ok", auto_hide_ms=4000)
        self.set_status(hint, "ok")
        self.entry_name.focus_set()

    def _matches_filter(self, cid) -> bool:
        """这条记录在当前搜索/筛选条件下是否可见。"""
        return any(int(r[0]) == int(cid) for r in self.rows)

    def _reset_filters(self):
        self._set_search_text("")
        self.var_filter_source.set(ALL_SOURCES)

    def clear_form(self, keep_status=False):
        self.var_name.set("")
        self.var_phone.set("")
        self.var_email.set("")
        self.var_source.set("其他")
        self.var_remark.set("")
        self._clear_all_errors()
        self.clear_form_msg()
        if not keep_status:
            self.set_status("提示：在列表中双击某一行可直接修改")
        self.entry_name.focus_set()

    def cancel_edit(self, quiet=False):
        self.editing_id = None
        self.form_title_var.set("新增客户")
        self.btn_save.configure(text="保存")
        self.btn_cancel_edit.pack_forget()
        self.tree.selection_remove(self.tree.selection())
        self.clear_form(keep_status=quiet)

    def load_into_form(self, cid):
        row = self.db.get(cid)
        if not row:
            self.set_status(f"找不到 ID={cid} 的记录", "error")
            self.refresh()
            return
        _, name, phone, email, source, remark = row
        self.editing_id = cid
        self.var_name.set(name)
        self.var_phone.set(phone)
        self.var_email.set("" if email == NO_EMAIL else email)
        self.var_source.set(source)
        self.var_remark.set(remark or "")
        self.form_title_var.set(f"修改客户（ID={cid}）")
        self.btn_save.configure(text="保存修改")
        self.btn_cancel_edit.pack(side="left", padx=self.s(8))
        self._clear_all_errors()
        self.show_form_msg(f"正在修改「{name}」，改好后点“保存修改”", "info")
        self.set_status(f"正在修改 ID={cid} 的记录")
        self.entry_name.focus_set()

    # ---------- 列表逻辑 ----------

    def refresh(self, flash_id=None):
        keyword = self._search_keyword()
        source = self.var_filter_source.get().strip() or ALL_SOURCES
        try:
            rows = self.db.fetch(keyword, source)
            total = self.db.count_all()
        except sqlite3.Error as e:
            self.set_status(f"读取数据库失败：{e}", "error")
            return

        self.rows = list(rows)
        if self.sort_col is not None:
            self._apply_sort()

        # 记住当前选中的 ID，刷新后尽量还原
        selected = self.selected_id()

        self.tree.delete(*self.tree.get_children())
        self._base_tags.clear()
        self._hover_iid = None
        for i, r in enumerate(self.rows):
            cid, name, phone, email, src, remark = r
            tags = ("odd",) if i % 2 else ()
            self._base_tags[str(cid)] = tags
            self.tree.insert(
                "", "end", iid=str(cid),
                values=(cid, name, phone, email, src, remark or ""),
                tags=tags,
            )
        if selected is not None and self.tree.exists(str(selected)):
            self.tree.selection_set(str(selected))
            self.tree.see(str(selected))

        # 顶部计数：没筛选时显示总数，筛选时同时显示"筛出多少"
        filtering = bool(keyword) or source != ALL_SOURCES
        if filtering:
            self.count_var.set(f"筛选出 {len(self.rows)} / 共 {total} 位")
        else:
            self.count_var.set(f"共 {total} 位客户")
        self._update_headings()

        # "清空筛选"只在需要时出现
        if filtering:
            self.btn_clear_filter.pack(side="left")
        else:
            self.btn_clear_filter.pack_forget()

        # 空列表的引导文字
        if self.rows:
            self.empty_label.place_forget()
        else:
            if filtering:
                self.empty_label.configure(
                    text="没有符合条件的客户\n换个关键词，或点「清空筛选」看看全部")
            else:
                self.empty_label.configure(
                    text="还没有客户记录\n在上面填写姓名和手机号，点「保存」就会出现在这里")
            self.empty_label.place(relx=0.5, rely=0.5, anchor="center")
            self.empty_label.lift()

        # 状态栏只报"筛选结果"这类临时信息，不跟计数抢位置
        if filtering:
            self.set_status(f"筛选出 {len(self.rows)} 位客户（共 {total} 位）")

        if flash_id is not None:
            self._flash_row(flash_id)

    def _update_headings(self):
        """表头显示当前排序方向，点过哪一列一眼能看出来。"""
        for col, (text, _width, _anchor) in self._headings.items():
            mark = ""
            if self.sort_col == col:
                mark = " ▼" if self.sort_desc else " ▲"
            self.tree.heading(col, text=text + mark)

    def sort_by(self, col):
        """点击表头排序；再点一次切换升序/降序。"""
        if self.sort_col == col:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_col, self.sort_desc = col, False
        self.refresh()

    def _apply_sort(self):
        index = {"id": 0, "name": 1, "phone": 2, "email": 3,
                 "source": 4, "remark": 5}[self.sort_col]
        if index == 0:
            self.rows.sort(key=lambda r: int(r[0]), reverse=self.sort_desc)
        else:
            self.rows.sort(key=lambda r: str(r[index] or ""),
                           reverse=self.sort_desc)

    def _on_tree_motion(self, event):
        """鼠标划过某一行时给一点底色反馈，方便横向读一整行的数据。"""
        iid = self.tree.identify_row(event.y)
        self._set_hover(iid or None)

    def _set_hover(self, iid):
        if iid == self._hover_iid:
            return
        previous, self._hover_iid = self._hover_iid, iid
        if previous and self.tree.exists(previous) and previous != self._flash_iid:
            self.tree.item(previous, tags=self._base_tags.get(previous, ()))
        if iid and self.tree.exists(iid) and iid != self._flash_iid:
            self.tree.item(iid, tags=("hover",))

    def _flash_row(self, cid):
        """新增/修改成功后让那一行短暂亮一下，回答"我存的东西去哪了"。"""
        iid = str(cid)
        if not self.tree.exists(iid):
            return
        self.tree.see(iid)
        self._flash_iid = iid
        steps = [ROW_FLASH, "#E3EEFD", "#EDF4FE", None]

        def step(index):
            try:
                if not self.winfo_exists():
                    return
            except tk.TclError:
                return
            if not self.tree.exists(iid):
                self._flash_iid = None
                return
            if index >= len(steps) - 1 or steps[index] is None:
                self.tree.item(iid, tags=self._base_tags.get(iid, ()))
                self._flash_iid = None
                return
            self.tree.tag_configure("flash", background=steps[index])
            self.tree.item(iid, tags=("flash",))
            self.after(160, lambda: step(index + 1))

        step(0)

    def selected_id(self):
        selection = self.tree.selection()
        if not selection:
            return None
        try:
            return int(selection[0])
        except ValueError:
            return None

    def on_row_double_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region not in ("cell", "tree"):
            return
        row_id = self.tree.identify_row(event.y)
        if row_id:
            self.tree.selection_set(row_id)
            self.load_into_form(int(row_id))

    def edit_selected(self):
        cid = self.selected_id()
        if cid is None:
            self.set_status("请先在列表里点选一位客户（或双击那一行）", "error")
            return
        self.load_into_form(cid)

    def delete_selected(self):
        cid = self.selected_id()
        if cid is None:
            self.set_status("请先在列表里点选要删除的客户", "error")
            return
        row = self.db.get(cid)
        if not row:
            self.refresh()
            return
        name = row[1]
        # 删除是不可恢复的破坏性操作，保留一次确认
        if not messagebox.askyesno(
            APP_TITLE, f"确定要删除客户“{name}”（ID={cid}）吗？\n删除后无法恢复。",
            parent=self,
        ):
            self.set_status("已取消删除")
            return
        try:
            self.db.delete(cid)
        except sqlite3.Error as e:
            messagebox.showerror(APP_TITLE, f"删除失败：{e}", parent=self)
            return
        if self.editing_id == cid:
            self.cancel_edit(quiet=True)
        if self._flash_iid == str(cid):
            self._flash_iid = None
        self._base_tags.pop(str(cid), None)
        self.refresh()
        self.set_status(f"已删除：{name}（ID={cid}）", "ok")

    def _set_search_text(self, text):
        self.var_search.set(text)
        self.entry_search.configure(fg=TEXT_MUTED if text == SEARCH_HINT else TEXT)

    def clear_filter(self):
        self._set_search_text("")
        self.var_filter_source.set(ALL_SOURCES)
        self.refresh()
        self.entry_search.focus_set()

    # ---------- 按来源统计（锚定在触发按钮上的弹层） ----------

    def show_stats(self):
        try:
            rows = self.db.count_by_source()
        except sqlite3.Error as e:
            messagebox.showerror(APP_TITLE, f"统计失败：{e}", parent=self)
            return
        total = sum(c for _, c in rows)

        win = tk.Toplevel(self)
        win.title("按来源统计")
        win.configure(bg=BG)
        win.transient(self)
        win.resizable(False, False)
        win.protocol("WM_DELETE_WINDOW", lambda: self._close_stats(win))

        head = tk.Frame(win, bg=BG)
        head.pack(fill="x", padx=self.s(16), pady=(self.s(14), self.s(8)))
        tk.Label(head, text="按来源统计", font=self.F_CARD, bg=BG,
                 fg=TEXT).pack(side="left")
        tk.Label(head, text=f"共 {total} 位", font=self.F_CAPTION, bg=BG,
                 fg=TEXT_SUB).pack(side="right")

        wrap = tk.Frame(win, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        wrap.pack(fill="both", expand=True, padx=self.s(16))
        tree = ttk.Treeview(wrap, columns=("source", "count", "percent"),
                            show="headings", height=max(2, min(len(rows), 8)))
        for col, (text, width, anchor) in {
            "source": ("来源", 140, "w"),
            "count": ("人数", 70, "center"),
            "percent": ("占比", 200, "w"),      # 要放得下"进度条 + 百分比"，窄了会截断
        }.items():
            tree.heading(col, text=text)
            tree.column(col, width=self.s(width), anchor=anchor)
        for src, cnt in rows:
            share = cnt / total if total else 0
            tree.insert("", "end", values=(src, cnt, self._bar(share)))
        tree.pack(fill="both", expand=True, padx=1, pady=1)

        if not rows:
            tk.Label(win, text="目前还没有客户记录", font=self.F_BODY, bg=BG,
                     fg=TEXT_SUB).pack(padx=self.s(16), pady=self.s(10))

        self._make_button(win, "关闭", lambda: self._close_stats(win)).pack(
            pady=(self.s(12), self.s(14)))
        win.bind("<Escape>", lambda e: self._close_stats(win))

        # 锚定到触发它的那个按钮：从哪点出来，就从哪冒出来
        win.update_idletasks()
        dw, dh = win.winfo_width(), win.winfo_height()
        anchor = self.btn_stats if self.btn_stats.winfo_ismapped() else self
        ax = anchor.winfo_rootx() + anchor.winfo_width() - dw
        ay = anchor.winfo_rooty() - dh - self.s(10)
        ax = max(self.s(8), min(ax, self.winfo_screenwidth() - dw - self.s(8)))
        ay = max(self.s(8), min(ay, self.winfo_screenheight() - dh - self.s(8)))
        win.geometry(f"+{ax}+{ay}")

        self._make_scrim(win)          # 背景压暗，把注意力收到弹层上
        win.lift()                     # 弹层压在遮罩之上
        try:
            win.grab_set()             # 模态：弹层开着时不会误操作主窗口
        except tk.TclError:
            pass
        self._fade_in(win, ax, ay)
        return win

    def _make_scrim(self, win):
        """主窗口上盖一层浅黑，弹层关闭时移除（失败就跳过，不影响功能）。"""
        try:
            scrim = tk.Toplevel(self)
            scrim.overrideredirect(True)
            scrim.configure(bg="#0B1220")
            scrim.transient(self)
            scrim.attributes("-alpha", 0.18)
            x = self.winfo_rootx()
            y = self.winfo_rooty()
            scrim.geometry(f"{self.winfo_width()}x{self.winfo_height()}+{x}+{y}")
            try:
                scrim.attributes("-disabled", True)   # 遮罩只负责变暗，不接收点击
            except tk.TclError:
                pass
            scrim.lift()                              # 浮在主窗口之上（弹层再压在它上面）
            self._scrim = scrim
            self._scrim_bind = self.bind(
                "<Configure>", lambda e: self._sync_scrim(), add="+")
        except tk.TclError:
            self._scrim = None

    def _sync_scrim(self):
        if self._scrim is None:
            return
        try:
            self._scrim.geometry(
                f"{self.winfo_width()}x{self.winfo_height()}"
                f"+{self.winfo_rootx()}+{self.winfo_rooty()}")
        except tk.TclError:
            self._scrim = None

    def _drop_scrim(self):
        if self._scrim_bind is not None:
            try:
                self.unbind("<Configure>", self._scrim_bind)
            except tk.TclError:
                pass
            self._scrim_bind = None
        if self._scrim is not None:
            try:
                self._scrim.destroy()
            except tk.TclError:
                pass
            self._scrim = None

    def _fade_in(self, win, ax, ay):
        """进场 140ms：淡入 + 从下方 8px 轻轻升起（弹层从触发按钮方向冒出来）。"""
        steps = [(0.0, 8), (0.45, 4), (0.8, 1), (1.0, 0)]

        def step(i):
            try:
                if not win.winfo_exists():
                    return
                alpha, offset = steps[i]
                win.attributes("-alpha", alpha)
                win.geometry(f"+{ax}+{ay + self.s(offset)}")
                if i < len(steps) - 1:
                    self.after(40, lambda: step(i + 1))
                else:
                    win.lift()
            except tk.TclError:
                pass

        step(0)

    def _close_stats(self, win):
        """离场 80ms：比进场快，操作完就干脆消失。"""
        try:
            if not win.winfo_exists():
                return
        except tk.TclError:
            return
        self._drop_scrim()
        steps = [0.7, 0.35, 0.0]

        def step(i):
            try:
                if not win.winfo_exists():
                    return
                win.attributes("-alpha", steps[i])
                if i < len(steps) - 1:
                    self.after(30, lambda: step(i + 1))
                else:
                    win.destroy()
            except tk.TclError:
                pass

        step(0)

    def _bar(self, share):
        filled = int(round(share * 10))
        return "█" * filled + "─" * (10 - filled) + f"  {share * 100:.0f}%"

    # ---------- 导出 ----------

    def export_csv(self):
        try:
            rows = self.db.fetch()   # 导出全部，不受搜索影响
        except sqlite3.Error as e:
            messagebox.showerror(APP_TITLE, f"导出失败：{e}", parent=self)
            return
        if not rows:
            messagebox.showinfo(APP_TITLE, "目前没有客户数据可以导出。", parent=self)
            return

        path = filedialog.asksaveasfilename(
            parent=self,
            title="导出客户列表",
            initialdir=app_dir(),
            initialfile="customers.csv",
            defaultextension=".csv",
            filetypes=[("Excel 可直接打开的 CSV 文件", "*.csv"), ("所有文件", "*.*")],
        )
        if not path:
            self.set_status("已取消导出")
            return
        try:
            # utf-8-sig：Excel 打开中文不乱码
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "姓名", "手机号", "邮箱", "来源", "备注"])
                writer.writerows(rows)
        except OSError as e:
            messagebox.showerror(APP_TITLE, f"写入文件失败：{e}", parent=self)
            return
        self.set_status(f"已导出 {len(rows)} 条记录到 {path}", "ok")
        if messagebox.askyesno(
            APP_TITLE,
            f"已成功导出 {len(rows)} 条客户记录：\n{path}\n\n现在打开这个文件吗？",
            parent=self,
        ):
            try:
                os.startfile(path)  # noqa: S606  （Windows 专用）
            except OSError as e:
                messagebox.showerror(APP_TITLE, f"打开文件失败：{e}", parent=self)


# ================== 程序入口 ==================

def main() -> int:
    """程序入口：出错时留下日志文件，方便排查（尤其是打包成 exe 后看不到报错）。"""
    try:
        return _run()
    except Exception as exc:  # noqa: BLE001  最后一道保险，不让程序"闪退"得莫名其妙
        path = write_crash_log(exc)
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                APP_TITLE,
                f"程序遇到错误：\n{exc}\n\n"
                f"详细信息已记录到：\n{path}\n"
                "请把这份日志发给维护人员。",
            )
            root.destroy()
        except Exception:
            pass
        return 1


def write_crash_log(exc: BaseException) -> str:
    """把崩溃详情写到程序旁边的"错误日志.txt"。"""
    import traceback

    path = os.path.join(app_dir(), "错误日志.txt")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("客户管理系统（图形界面版）运行出错\n")
            f.write(f"时间：{datetime.now():%Y-%m-%d %H:%M:%S}\n")
            f.write(f"Python：{sys.version}\n")
            f.write(f"是否打包运行：{getattr(sys, 'frozen', False)}\n\n")
            f.write("".join(traceback.format_exception(
                type(exc), exc, exc.__traceback__)))
            f.write("\n请把这份文件发给维护人员。\n")
    except OSError:
        pass
    return path


def _run() -> int:
    db_path = resolve_db_path()
    try:
        db = CustomerDB(db_path)
    except sqlite3.Error as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            APP_TITLE,
            f"数据库打开失败：{e}\n\n"
            f"文件位置：{db_path}\n"
            "请确认这个文件夹可以正常读写（不要放在系统盘的受保护目录里）。",
        )
        root.destroy()
        return 1

    app = CustomerApp(db)
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
