# -*- coding: utf-8 -*-
"""
============================================
          控制台客户管理系统（SQLite 版）
============================================
【本版特点】
  · 免安装数据库：数据保存在本程序同目录的 customers.db 文件里
  · 客户电脑不需要安装 MySQL，双击 exe 就能用
  · 适合单台电脑单人使用
  · 添加客户支持两种方式：逐项输入 或 一次性输入
     一次性输入格式：姓名,手机号,邮箱,来源
     （中英文逗号都可以，例如：张三,13812345678,zhangsan@example.com,朋友推荐）
  · 没有邮箱的客户，邮箱一栏填"无"即可

【环境要求】
  · Python 3.x（自带 sqlite3 模块，无需安装任何第三方库）

【数据库说明】
  程序会自动创建：
  · 数据文件 customers.db（和程序在同一个文件夹）
  · 数据表 customers，字段：
      id     自增主键
      name   客户姓名
      phone  手机号
      email  邮箱
      source 客户来源

【运行方式】
  在终端执行：python "Customer Management (SQLite).py"
  然后按菜单提示操作即可。

【数据备份】
  直接把 customers.db 文件复制一份保存即可（程序没运行时才能复制）。
============================================
"""

import csv          # 用于导出 CSV 文件
import re           # 用于正则表达式校验格式
import sqlite3      # Python 自带的轻量数据库（免安装）

# ================== 数据库配置（初学者改这里） ==================
# 数据库文件名：客户数据都存在这个文件里，和程序放同一个文件夹
DB_FILE = "customers.db"

# ================== 数据库工具函数 ==================

def get_connection():
    """打开数据库文件；失败时打印提示并返回 None"""
    try:
        # sqlite3 的用法和 mysql 很像：execute / commit / fetchone / fetchall 都一样
        conn = sqlite3.connect(DB_FILE)
        return conn
    except sqlite3.Error as e:
        print(f"数据库打开失败：{e}")
        print(f"   请确认程序所在文件夹可以正常读写（{DB_FILE}）。")
        return None


def init_database():
    """
    初始化数据库：如果 customers.db 或 customers 表不存在，自动创建。
    这样第一次运行程序时，不需要手动建库建表。
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
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
        conn.commit()
        cursor.close()
        conn.close()
        print("数据库初始化完成（customers.db 已就绪）")
    except sqlite3.Error as e:
        print(f"初始化数据库失败：{e}")


# ================== 格式校验函数 ==================

def is_valid_email(email):
    """
    校验邮箱格式是否合法。
    简单规则：用户名@域名.后缀，如 zhangsan@example.com
    特殊规则：没有邮箱的客户，输入"无"两个字也视为合法。
    """
    if email == "无":
        return True
    pattern = r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$"
    return re.match(pattern, email) is not None


def is_valid_phone(phone):
    """
    校验手机号格式是否合法（中国大陆 11 位手机号）。
    规则：1 开头，第二位是 3-9，后面 9 位数字，如 13812345678。
    如果要用其他国家的手机号，修改这个正则即可。
    """
    pattern = r"^1[3-9]\d{9}$"
    return re.match(pattern, phone) is not None


# ================== 功能函数 ==================

def add_customer():
    """功能 1：添加客户（带邮箱和手机号格式校验）"""
    print("\n———— 添加客户 ————")
    name = input("请输入客户姓名：").strip()
    if not name:
        print("姓名不能为空！")
        return

    # 手机号校验：不合法就一直提示重新输入
    while True:
        phone = input("请输入手机号：").strip()
        if is_valid_phone(phone):
            break
        print("手机号格式不正确（应为 11 位，如 13812345678），请重新输入")

    # 邮箱校验：不合法就一直提示重新输入（没有邮箱请输"无"）
    while True:
        email = input("请输入邮箱（没有邮箱请输入 无）：").strip()
        if is_valid_email(email):
            break
        print("邮箱格式不正确（如 zhangsan@example.com，没有邮箱请输入 无），请重新输入")

    source = input("请输入客户来源（如：广告/朋友推荐/网络/其他）：").strip() or "其他"

    conn = get_connection()
    if conn is None:
        return
    try:
        cursor = conn.cursor()
        # 使用 ? 占位符传参，防止 SQL 注入，也避免引号转义问题（sqlite 用 ?，mysql 用 %s）
        sql = "INSERT INTO customers (name, phone, email, source) VALUES (?, ?, ?, ?)"
        cursor.execute(sql, (name, phone, email, source))
        conn.commit()
        print(f"客户“{name}”添加成功，ID = {cursor.lastrowid}")
        cursor.close()
        conn.close()
    except sqlite3.Error as e:
        print(f"添加失败：{e}")


def add_customer_once():
    """功能 1b：一次性输入客户信息，格式：姓名,手机号,邮箱,来源"""
    print("\n———— 一次性添加客户 ————")
    print("请按这个格式一次性输入（中英文逗号都可以）：")
    print("  姓名,手机号,邮箱,来源")
    print("例如：张三,13812345678,zhangsan@example.com,朋友推荐")
    print("（没有邮箱请填：无；来源不填默认 其他；输入 0 可放弃）")
    while True:
        line = input("请输入：").strip()
        if line == "0":
            print("已放弃本次添加。")
            return
        # 把中文逗号统一换成英文逗号，再拆分成 4 段
        parts = [p.strip() for p in line.replace("，", ",").split(",")]
        if len(parts) != 4:
            print(f"格式不对：应该是 4 项（姓名,手机号,邮箱,来源），你输入了 {len(parts)} 项，请重新输入")
            continue
        name, phone, email, source = parts
        # 逐项校验，明确提示是哪一项有问题
        if not name:
            print("第 1 项：姓名不能为空！")
            continue
        if not is_valid_phone(phone):
            print("第 2 项：手机号格式不正确（应为 11 位，如 13812345678）")
            continue
        if not is_valid_email(email):
            print("第 3 项：邮箱格式不正确（如 zhangsan@example.com，没有邮箱请填 无）")
            continue
        source = source or "其他"
        # 校验全部通过，写入数据库
        conn = get_connection()
        if conn is None:
            return
        try:
            cursor = conn.cursor()
            sql = "INSERT INTO customers (name, phone, email, source) VALUES (?, ?, ?, ?)"
            cursor.execute(sql, (name, phone, email, source))
            conn.commit()
            print(f"客户“{name}”添加成功，ID = {cursor.lastrowid}")
            cursor.close()
            conn.close()
        except sqlite3.Error as e:
            print(f"添加失败：{e}")
        return


def add_customer_menu():
    """功能 1：添加客户的子菜单（逐项输入 / 一次性输入）"""
    print("\n———— 添加客户 ————")
    print("  a. 逐项输入（按提示一项一项填）")
    print("  b. 一次性输入（格式：姓名,手机号,邮箱,来源）")
    print("  0. 返回主菜单")
    choice = input("请选择输入方式（a/b/0）：").strip().lower()
    if choice == "a":
        add_customer()
    elif choice == "b":
        add_customer_once()
    else:
        print("已返回主菜单。")


def view_customers():
    """功能 2：查看所有客户"""
    print("\n———— 客户列表 ————")
    conn = get_connection()
    if conn is None:
        return
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, phone, email, source FROM customers ORDER BY id")
        rows = cursor.fetchall()
        if not rows:
            print("目前没有客户记录。")
            cursor.close()
            conn.close()
            return
        print(f"{'ID':<5}{'姓名':<10}{'手机号':<14}{'邮箱':<26}{'来源':<8}")
        print("-" * 68)
        for r in rows:
            print(f"{r[0]:<5}{r[1]:<10}{r[2]:<14}{r[3]:<26}{r[4]:<8}")
        print(f"\n共 {len(rows)} 条记录")
        cursor.close()
        conn.close()
    except sqlite3.Error as e:
        print(f"查询失败：{e}")


def update_customer():
    """功能 3：修改客户（先按 ID 定位，再选择要修改的字段）"""
    print("\n———— 修改客户 ————")
    cid = input("请输入要修改的客户 ID：").strip()
    if not cid.isdigit():
        print("ID 必须是数字！")
        return

    conn = get_connection()
    if conn is None:
        return
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, phone, email, source FROM customers WHERE id = ?",
            (cid,),
        )
        row = cursor.fetchone()
        if row is None:
            print(f"找不到 ID 为 {cid} 的客户。")
            cursor.close()
            conn.close()
            return

        print(f"当前信息：姓名={row[1]}，手机号={row[2]}，邮箱={row[3]}，来源={row[4]}")
        print("\n请选择要修改的字段：")
        print("1. 姓名  2. 手机号  3. 邮箱  4. 来源  0. 取消")
        choice = input("请输入序号：").strip()

        # 根据选择决定要改的字段名和新值（field 来自固定选项，不存在注入风险）
        if choice == "1":
            field = "name"
            new_value = input(f"新姓名（原：{row[1]}）：").strip()
            if not new_value:
                print("姓名不能为空！")
                cursor.close()
                conn.close()
                return
        elif choice == "2":
            field = "phone"
            while True:
                new_value = input(f"新手机号（原：{row[2]}）：").strip()
                if is_valid_phone(new_value):
                    break
                print("手机号格式不正确，请重新输入")
        elif choice == "3":
            field = "email"
            while True:
                new_value = input(f"新邮箱（原：{row[3]}，没有邮箱请输入 无）：").strip()
                if is_valid_email(new_value):
                    break
                print("邮箱格式不正确，请重新输入")
        elif choice == "4":
            field = "source"
            new_value = input(f"新来源（原：{row[4]}）：").strip() or "其他"
        else:
            print("已取消修改。")
            cursor.close()
            conn.close()
            return

        sql = f"UPDATE customers SET {field} = ? WHERE id = ?"
        cursor.execute(sql, (new_value, cid))
        conn.commit()
        print("修改成功！")
        cursor.close()
        conn.close()
    except sqlite3.Error as e:
        print(f"修改失败：{e}")


def delete_customer():
    """功能 4：删除客户（按 ID 定位，删除前二次确认）"""
    print("\n———— 删除客户 ————")
    cid = input("请输入要删除的客户 ID：").strip()
    if not cid.isdigit():
        print("ID 必须是数字！")
        return

    conn = get_connection()
    if conn is None:
        return
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM customers WHERE id = ?", (cid,))
        row = cursor.fetchone()
        if row is None:
            print(f"找不到 ID 为 {cid} 的客户。")
            cursor.close()
            conn.close()
            return

        confirm = input(f"确定删除客户“{row[0]}”（ID={cid}）吗？(y/n)：").strip().lower()
        if confirm != "y":
            print("已取消删除。")
            cursor.close()
            conn.close()
            return

        cursor.execute("DELETE FROM customers WHERE id = ?", (cid,))
        conn.commit()
        print("删除成功！")
        cursor.close()
        conn.close()
    except sqlite3.Error as e:
        print(f"删除失败：{e}")


def count_by_source():
    """功能 5：按客户来源统计数量"""
    print("\n———— 按来源统计 ————")
    conn = get_connection()
    if conn is None:
        return
    try:
        cursor = conn.cursor()
        # GROUP BY 按来源分组，COUNT(*) 统计每组人数，按人数从多到少排列
        cursor.execute(
            "SELECT source, COUNT(*) FROM customers "
            "GROUP BY source ORDER BY COUNT(*) DESC"
        )
        rows = cursor.fetchall()
        if not rows:
            print("暂无客户数据。")
            cursor.close()
            conn.close()
            return
        total = 0
        for source, cnt in rows:
            print(f"  {source:<10}：{cnt} 人")
            total += cnt
        print(f"  ────────────────\n  合计：{total} 人")
        cursor.close()
        conn.close()
    except sqlite3.Error as e:
        print(f"统计失败：{e}")


def export_csv(filename="customers.csv"):
    """功能 6：导出客户列表到 CSV 文件"""
    print(f"\n———— 导出到 {filename} ————")
    conn = get_connection()
    if conn is None:
        return
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, phone, email, source FROM customers ORDER BY id")
        rows = cursor.fetchall()
        if not rows:
            print("没有数据可导出。")
            cursor.close()
            conn.close()
            return
        # 用 utf-8-sig 编码写入，Excel 直接打开中文不会乱码
        with open(filename, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "姓名", "手机号", "邮箱", "来源"])  # 表头
            writer.writerows(rows)                                     # 数据行
        print(f"已导出 {len(rows)} 条客户记录到 {filename}")
        cursor.close()
        conn.close()
    except sqlite3.Error as e:
        print(f"导出失败：{e}")


# ================== 主菜单 ==================

MENU = """
=========================================
            客户管理系统
=========================================
  1. 添加客户（逐项/一次性）
  2. 查看所有客户
  3. 修改客户
  4. 删除客户
  5. 按来源统计客户数量
  6. 导出客户列表到 customers.csv
  7. 退出
=========================================
"""


def main():
    """程序入口：初始化数据库后进入菜单循环"""
    init_database()
    while True:
        print(MENU)
        choice = input("请选择功能（1-7）：").strip()
        if choice == "1":
            add_customer_menu()
        elif choice == "2":
            view_customers()
        elif choice == "3":
            update_customer()
        elif choice == "4":
            delete_customer()
        elif choice == "5":
            count_by_source()
        elif choice == "6":
            export_csv()
        elif choice == "7":
            print("感谢使用，再见！")
            break
        else:
            print("输入无效，请输入 1-7 的数字。")


if __name__ == "__main__":
    main()
