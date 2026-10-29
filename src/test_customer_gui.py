# -*- coding: utf-8 -*-
"""客户管理系统（图形界面版）自动化测试。

放在程序所在目录，用真实 customers.db 的副本做测试，不会改动原始数据。
所有数量都是运行时从真实数据算出来的，你平时增删客户不会让测试失效。

运行方式：在本目录执行  python test_customer_gui.py
"""
import importlib.util
import os
import shutil
import sqlite3
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))     # 本脚本所在目录 = 程序目录
SRC = os.path.join(HERE, "客户管理系统（图形界面）.py")
REAL_DB = os.path.join(HERE, "customers.db")


def pick_tmp_dir():
    """选一个可写的目录来存放测试用的数据库副本。

    优先用程序目录下的 "_测试临时目录"；如果该目录不可写（受限环境），
    依次退到上一级目录、系统临时目录。
    """
    candidates = [
        os.path.join(HERE, "_测试临时目录"),
        os.path.join(os.path.dirname(HERE), "_测试临时目录"),
        os.path.join(tempfile.gettempdir(), "_测试临时目录"),
    ]
    for cand in candidates:
        try:
            os.makedirs(cand, exist_ok=True)
            probe = os.path.join(cand, ".write_probe")
            with open(probe, "w", encoding="utf-8") as f:
                f.write("x")
            os.remove(probe)
            return cand
        except OSError:
            continue
    raise SystemExit("找不到可写的临时目录，测试无法运行。")


passed, failed = [], []


def check(name, condition, detail=""):
    if condition:
        passed.append(name)
        print(f"  [OK]   {name}")
    else:
        failed.append(name)
        print(f"  [FAIL] {name}  {detail}")


def win_exists(widget):
    try:
        return bool(widget.winfo_exists())
    except Exception:  # noqa: BLE001
        return False


def tags_of(tree, iid):
    try:
        return tuple(tree.item(iid, "tags"))
    except Exception:  # noqa: BLE001
        return ()


# ---------- 载入被测模块 ----------
spec = importlib.util.spec_from_file_location("cust_gui", SRC)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(f"模块已载入：{SRC}")

# 注意：不要用 tempfile.mkdtemp（0700 权限在受限环境下会创建失败）
tmp = pick_tmp_dir()
shutil.rmtree(tmp, ignore_errors=True)   # 清掉上一次的残留
os.makedirs(tmp, exist_ok=True)
print(f"临时目录：{tmp}\n")

db_path = os.path.join(tmp, "customers.db")
shutil.copy(REAL_DB, db_path)   # 用真实数据副本

# ================== 1. 数据层 ==================
print("=== 1. 数据层（含老数据兼容） ===")
db = mod.CustomerDB(db_path)
conn = sqlite3.connect(db_path)
cols = [r[1] for r in conn.execute("PRAGMA table_info(customers)")]
conn.close()
check("老库自动补上 remark（备注）列", "remark" in cols, f"实际列：{cols}")

rows = db.fetch()
n0 = len(rows)                       # 真实数据现有条数（不写死，随你的数据自动变）
check("现有客户数据全部完好读取", n0 >= 1, f"实际 {n0} 条")
check("每条记录的姓名/手机号/邮箱/来源都完整",
      all(r[1] and r[2] and r[3] and r[4] for r in rows))
check("备注列可正常读取（老数据为空）", all(isinstance(r[5], str) for r in rows))

source_counts = {}
for r in rows:
    source_counts[r[4]] = source_counts.get(r[4], 0) + 1
top_source = max(source_counts, key=source_counts.get)
print(f"  （当前真实数据：{n0} 条，来源分布 {source_counts}）")

# ================== 2. 校验规则（与老版本一致） ==================
print("\n=== 2. 校验规则 ===")
check("手机号 13812345678 合法", mod.is_valid_phone("13812345678"))
check("手机号 10 位不合法", not mod.is_valid_phone("1381234567"))
check("手机号 12812345678（第二位 2）不合法", not mod.is_valid_phone("12812345678"))
check("手机号含字母不合法", not mod.is_valid_phone("1381234567a"))
check("邮箱 zhangsan@example.com 合法", mod.is_valid_email("zhangsan@example.com"))
check("邮箱 abc 不合法", not mod.is_valid_email("abc"))
check("邮箱留空视为合法（没有邮箱）", mod.is_valid_email(""))
check("邮箱填“无”视为合法", mod.is_valid_email("无"))
check("空邮箱统一存成“无”", mod.normalize_email("") == "无")

# ================== 3. 增 / 改 / 删 / 搜索 ==================
print("\n=== 3. 增删改查 ===")
new_id = db.add("测试客户", "13900000000", "无", "网络", "备注测试")
check("新增客户成功", db.count_all() == n0 + 1, f"实际 {db.count_all()} 条")
check("能按姓名搜索", len(db.fetch("测试")) == 1)
check("能按手机号搜索", len(db.fetch("13900000000")) == 1)
check("能按备注搜索", len(db.fetch("备注测试")) == 1)
check(f"能按来源筛选（{top_source}）",
      len(db.fetch("", top_source)) == source_counts[top_source],
      f"期望 {source_counts[top_source]}，实际 {len(db.fetch('', top_source))}")

sample = rows[0]
check(f"姓名+来源组合筛选（{sample[1]} / {sample[4]}）",
      len(db.fetch(sample[1], sample[4])) >= 1)
check("搜不到时返回空", len(db.fetch("这个人肯定不存在xyz")) == 0)

db.update(new_id, "测试客户改", "13900000001", "t@e.com", "广告", "改过的备注")
row = db.get(new_id)
check("修改客户成功",
      row[1] == "测试客户改" and row[2] == "13900000001"
      and row[3] == "t@e.com" and row[4] == "广告" and row[5] == "改过的备注",
      f"实际：{row}")

stats = db.count_by_source()
check("统计总数正确", sum(c for _, c in stats) == n0 + 1, f"实际：{stats}")

db.delete(new_id)
check("删除客户成功", db.count_all() == n0 and db.get(new_id) is None)

# ================== 4. 图形界面逻辑 ==================
print("\n=== 4. 图形界面 ===")
try:
    import tkinter
    root_probe = tkinter.Tk()
    root_probe.destroy()
    gui_ok = True
except Exception as e:  # noqa: BLE001
    gui_ok = False
    print(f"  !! 当前环境无法创建窗口，跳过界面测试：{e}")

if gui_ok:
    # 屏蔽弹窗，避免测试卡住
    answers = {"yes": True}
    exported = {"path": os.path.join(tmp, "out.csv")}
    mod.messagebox.askyesno = lambda *a, **k: answers["yes"]
    mod.messagebox.showinfo = lambda *a, **k: None
    mod.messagebox.showwarning = lambda *a, **k: None
    mod.messagebox.showerror = lambda *a, **k: None
    mod.filedialog.asksaveasfilename = lambda **k: exported["path"]

    app = mod.CustomerApp(db)
    app.withdraw()
    app.update()

    check(f"启动后列出全部 {n0} 位客户",
          len(app.tree.get_children()) == n0,
          f"实际 {len(app.tree.get_children())} 行")
    check(f"顶部计数显示“共 {n0} 位客户”",
          f"共 {n0} 位客户" in app.count_var.get(), app.count_var.get())

    # --- 搜索框的灰字提示与「清空筛选」的按需出现 ---
    check("搜索框显示灰字提示", app.var_search.get() == mod.SEARCH_HINT,
          app.var_search.get())
    check("灰字提示不会被当成搜索关键字", app._search_keyword() == "")
    check("没有筛选时不显示「清空筛选」",
          app.btn_clear_filter.winfo_manager() == "",
          app.btn_clear_filter.winfo_manager())
    check("有数据时不显示空列表引导",
          app.empty_label.winfo_manager() == "")

    # --- 一次性填写 → 保存 ---
    app.var_name.set("图形界面测试")
    app.var_phone.set("13711112222")
    app.var_email.set("")
    app.var_source.set("广告")
    app.var_remark.set("来自测试")
    app.on_save()
    check("表单一次性填写后保存成功", app.db.count_all() == n0 + 1,
          f"实际 {app.db.count_all()} 条")
    check("保存后表单自动清空", app.var_name.get() == "" and app.var_remark.get() == "")
    check("保存后来源回到默认“其他”", app.var_source.get() == "其他")
    check("表单旁有保存成功提示", "已保存" in app.form_msg_var.get(),
          app.form_msg_var.get())
    check("状态栏也说明了刚发生什么", "已保存" in app.status_var.get(),
          app.status_var.get())
    check("列表自动刷新", len(app.tree.get_children()) == n0 + 1,
          f"实际 {len(app.tree.get_children())} 行")

    saved = db.fetch("图形界面测试")[0]
    saved_id = saved[0]
    check("空邮箱存成“无”", saved[3] == "无", f"实际：{saved[3]}")
    check("备注已写入数据库", saved[5] == "来自测试")
    check("新增的那一行短暂高亮（方便找到它）",
          "flash" in tags_of(app.tree, str(saved_id)),
          f"实际标签 {tags_of(app.tree, str(saved_id))}")
    check("顶部计数同步更新",
          f"共 {n0 + 1} 位客户" in app.count_var.get(), app.count_var.get())

    # --- 校验失败不应写入 ---
    before = app.db.count_all()
    app.var_name.set("手机号错的客户")
    app.var_phone.set("123")
    app.on_save()
    check("手机号不合法时拒绝保存", app.db.count_all() == before)
    check("出错的输入框被标红",
          app.entry_phone.cget("highlightbackground") == mod.FIELD_ERR)
    check("表单旁直接说明哪里错了", "手机号" in app.form_msg_var.get(),
          app.form_msg_var.get())
    app.clear_form()
    check("清空后错误标记消失",
          app.entry_phone.cget("highlightbackground") == mod.FIELD_BORDER)
    check("清空后提示也消失", app.form_msg_var.get() == "")

    app.var_name.set("")
    app.var_phone.set("13711113333")
    app.on_save()
    check("姓名为空时拒绝保存", app.db.count_all() == before)
    check("表单旁提示姓名必填", "姓名" in app.form_msg_var.get())
    app.clear_form()

    app.var_name.set("邮箱错的客户")n    app.var_phone.set("13711113333")
    app.var_email.set("abc")
    app.on_save()
    check("邮箱不合法时拒绝保存", app.db.count_all() == before)
    check("表单旁提示邮箱格式", "邮箱" in app.form_msg_var.get())
    app.clear_form()

    # --- 搜索 / 筛选 / 空状态 ---
    app.var_search.set("图形界面")
    app.refresh()
    check("搜索框实时过滤", len(app.tree.get_children()) == 1,
          f"实际 {len(app.tree.get_children())} 行")
    check("筛选时出现「清空筛选」按钮",
          app.btn_clear_filter.winfo_manager() == "pack")
    check("顶部计数变成“筛选出 M / 共 N”",
          "筛选出 1" in app.count_var.get(), app.count_var.get())

    app.var_search.set("绝对搜不到的关键词xyz")
    app.refresh()
    check("搜不到时列表为空", len(app.tree.get_children()) == 0)
    check("搜不到时给出引导文字", app.empty_label.winfo_manager() == "place")

    app.clear_filter()
    check("清空筛选后恢复全部", len(app.tree.get_children()) == n0 + 1,
          f"实际 {len(app.tree.get_children())} 行")
    check("清空后按钮收起、引导消失",
          app.btn_clear_filter.winfo_manager() == ""
          and app.empty_label.winfo_manager() == "")
    check("清空后搜索框内容为空（不会把灰字当关键字）",
          app._search_keyword() == "")
    app._placeholder_show()      # 等价于"焦点离开搜索框"
    check("焦点离开后重新显示灰字提示",
          app.var_search.get() == mod.SEARCH_HINT and app._search_keyword() == "")

    app.var_filter_source.set(top_source)
    app.refresh()
    expect_top = len([r for r in db.fetch() if r[4] == top_source])
    check(f"按来源筛选有效（{top_source}）",
          len(app.tree.get_children()) == expect_top,
          f"期望 {expect_top}，实际 {len(app.tree.get_children())}")
    app.clear_filter()

    # --- 列表的行反馈 ---
    first_iid = app.tree.get_children()[0]
    app._set_hover(first_iid)
    check("鼠标划过某行会高亮", "hover" in tags_of(app.tree, first_iid))
    app._set_hover(None)
    check("移开鼠标后高亮还原", "hover" not in tags_of(app.tree, first_iid))

    # --- 修改模式 ---
    app.load_into_form(saved_id)
    check("按钮/双击进入修改模式", app.editing_id == saved_id)
    check("按钮文字变为“保存修改”", app.btn_save.cget("text") == "保存修改")
    check("表单载入了原数据",
          app.var_name.get() == "图形界面测试" and app.var_remark.get() == "来自测试")
    check("表单旁提示正在修改", "正在修改" in app.form_msg_var.get())
    app.var_remark.set("改过的备注")
    app.on_save()
    check("修改保存成功", app.db.get(saved_id)[5] == "改过的备注")
    check("修改后退出修改模式", app.editing_id is None)
    check("修改后按钮文字复原", app.btn_save.cget("text") == "保存")
    check("修改成功后原行也会高亮",
          "flash" in tags_of(app.tree, str(saved_id)))

    app.load_into_form(saved_id)
    app.cancel_edit()
    check("取消修改后表单清空", app.var_name.get() == "" and app.editing_id is None)

    # --- 排序 ---
    app.sort_by("name")
    names = [app.tree.item(i)["values"][1] for i in app.tree.get_children()]
    check("按姓名排序（升序）", names == sorted(names), f"实际：{names}")
    check("升序时表头有 ▲ 标记", "▲" in app.tree.heading("name", "text"),
          app.tree.heading("name", "text"))
    app.sort_by("name")
    names2 = [app.tree.item(i)["values"][1] for i in app.tree.get_children()]
    check("再点一次变降序", names2 == sorted(names, reverse=True), f"实际：{names2}")
    check("降序时表头有 ▼ 标记", "▼" in app.tree.heading("name", "text"),
          app.tree.heading("name", "text"))

    # --- 导出 ---
    app.export_csv()
    check("导出 CSV 文件已生成", os.path.exists(exported["path"]))
    with open(exported["path"], encoding="utf-8-sig") as f:
        content = f.read()
    check("导出内容含备注列", "备注" in content and "ID" in content)
    check("导出内容含中文数据", "图形界面测试" in content and "改过的备注" in content)

    # --- 保存时被筛选挡住 → 自动清除筛选 ---
    app.var_search.set("绝对搜不到的关键词xyz")
    app.refresh()
    check("筛选到空时列表为空", len(app.tree.get_children()) == 0)
    app.load_into_form(saved_id)
    app.var_remark.set("筛选状态下保存的备注")
    app.on_save()
    visible_names = [app.tree.item(i)["values"][1] for i in app.tree.get_children()]
    check("保存后自动清除筛选，能立刻看到这条记录",
          "图形界面测试" in visible_names, f"实际列表：{visible_names}")
    check("自动清除筛选时状态栏有说明",
          "已自动清除筛选" in app.status_var.get(), app.status_var.get())
    check("备注修改已生效", app.db.get(saved_id)[5] == "筛选状态下保存的备注")

    # --- 删除 ---
    app.tree.selection_set(str(saved_id))
    app.delete_selected()
    check("删除选中客户成功", app.db.get(saved_id) is None)
    check("删除后列表刷新", len(app.tree.get_children()) == n0,
          f"实际 {len(app.tree.get_children())} 行")
    check("删除后状态栏提示", "已删除" in app.status_var.get(), app.status_var.get())
    check("删除后顶部计数同步", f"共 {n0} 位客户" in app.count_var.get(),
          app.count_var.get())

    answers["yes"] = False
    app.tree.selection_set(app.tree.get_children()[0])
    count_before = app.db.count_all()
    app.delete_selected()
    check("删除时选“否”不会删数据", app.db.count_all() == count_before)

    # --- 统计弹层（锚定 + 遮罩 + 进出场） ---
    win = app.show_stats()
    app.update()
    check("统计弹层能打开", win is not None and win_exists(win))
    check("统计弹层打开时背景被压暗", app._scrim is not None)
    app._close_stats(win)
    check("关闭时遮罩立刻移除", app._scrim is None)
    for _ in range(12):
        app.update()
        time.sleep(0.03)
    check("统计弹层已关闭", not win_exists(win))

    app.destroy()

# ================== 结果 ==================
print("\n" + "=" * 46)
print(f"通过 {len(passed)} 项，失败 {len(failed)} 项")
if failed:
    for f in failed:
        print(f"  失败：{f}")
# 顺带确认测试没有改动真实数据
_real = sqlite3.connect(REAL_DB)
_real_n = list(_real.execute("SELECT COUNT(*) FROM customers"))[0][0]
_real.close()
print(f"真实 customers.db 记录数仍为 {_real_n} 条（应等于测试开始时的 {n0} 条）")
if _real_n != n0:
    print("  !! 警告：真实数据条数发生变化，请检查！")
    failed.append("真实数据被意外改动")

shutil.rmtree(tmp, ignore_errors=True)
sys.exit(1 if failed else 0)
