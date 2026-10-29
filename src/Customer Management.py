# -*- coding: utf-8 -*-
"""
============================================
          控制台客户管理系统
============================================
【环境要求】
  · Python 3.x
  · 依赖库：mysql-connector-python
    安装命令：pip install mysql-connector-python
  · 本机 MySQL 服务已启动

【数据库说明】
  程序会自动创建：
  · 数据库 customer_db
  · 数据表 customers，字段：
      id     自增主键
      name   客户姓名
      phone  手机号
      email  邮箱
      source 客户来源

【运行方式】
  在终端执行：python "Customer Mangement.py"
  然后按菜单提示操作即可。

【使用前必改】
  把下方 DB_CONFIG 里的 password 改成你自己 MySQL 的密码。
============================================
"""

import csv          # 用于导出 CSV 文件
import re           # 用于正则表达式校验格式
import mysql.connector
from mysql.connector import Error

# ================== 数据库连接配置（初学者改这里） ==================
DB_CONFIG = {
    "host": "localhost",   # MySQL 服务器地址
    "user": "root",        # MySQL 用户名
    "password": "123456",     # MySQL root 密码（已重置为 123456）
    "database": "customer_db",  # 数据库名
}

# ================== 数据库工具函数 ==================

def get_connection():
    """建立数据库连接；失败时打印提示并返回 None"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        print(f"数据库连接失败：{e}")
        print("   请检查 MySQL 服务是否启动、密码是否正确。")
        return None


def init_database():
    """
    初始化数据库：如果 customer_db 库或 customers 表不存在，自动创建。
    这样第一次运行程序时，不需要手动去 MySQL 里建库建表。
    """
    try:
        # 先不带 database 连接服务器，再创建库和表
        conn = mysql.connector.connect(
            host=DB_CONFIG["host"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
        )
        cursor = conn.cursor(buffered=True)  # buffered: 一次读入全部结果，避免未消费结果集导致后续语句异常
        cursor.execute(
            "CREATE DATABASE IF NOT EXISTS customer_db "
            "DEFAULT CHARACTER SET utf8mb4"
        )
        conn.commit()
        conn.database = "customer_db"  # 切换到 customer_db 库
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id     INT AUTO_INCREMENT PRIMARY KEY,
                name   VARCHAR(50)  NOT NULL,
                phone  VARCHAR(20)  NOT NULL,
                email  VARCHAR(100) NOT NULL,
                source VARCHAR(50)  NOT NULL
            ) DEFAULT CHARSET=utf8mb4
            """
        )
        conn.commit()
        cursor.close()
        conn.close()
        print("数据库初始化完成（库和表已就绪）")
    except Error as e:
        print(f"初始化数据库失败：{e}")


# ================== 格式校验函数 ==================

def is_valid_email(email):
    """
    校验邮箱格式是否合法。
    简单规则：用户名@域名.后缀，如 zhangsan@example.com
    """
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

    # 邮箱校验：不合法就一直提示重新输入
    while True:
        email = input("请输入邮箱：").strip()
        if is_valid_email(email):
            break
        print("邮箱格式不正确（如 zhangsan@example.com），请重新输入")

    source = input("请输入客户来源（如：广告/朋友推荐/网络/其他）：").strip() or "其他"

    conn = get_connection()
    if conn is None:
        return
    try:
        cursor = conn.cursor(buffered=True)  # buffered: 一次读入全部结果，避免未消费结果集导致后续语句异常
        # 使用 %s 占位符传参，防止 SQL 注入，也避免引号转义问题
        sql = "INSERT INTO customers (name, phone, email, source) VALUES (%s, %s, %s, %s)"
        cursor.execute(sql, (name, phone, email, source))
        conn.commit()
        print(f"客户“{name}”添加成功，ID = {cursor.lastrowid}")
        cursor.close()
        conn.close()
    except Error as e:
        print(f"添加失败：{e}")


def view_customers():
    """功能 2：查看所有客户"""
    print("\n———— 客户列表 ————")
    conn = get_connection()
    if conn is None:
        return
    try:
        cursor = conn.cursor(buffered=True)  # buffered: 一次读入全部结果，避免未消费结果集导致后续语句异常
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
    except Error as e:
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
        cursor = conn.cursor(buffered=True)  # buffered: 一次读入全部结果，避免未消费结果集导致后续语句异常
        cursor.execute(
            "SELECT id, name, phone, email, source FROM customers WHERE id = %s",
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
                new_value = input(f"新邮箱（原：{row[3]}）：").strip()
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

        sql = f"UPDATE customers SET {field} = %s WHERE id = %s"
        cursor.execute(sql, (new_value, cid))
        conn.commit()
        print("修改成功！")
        cursor.close()
        conn.close()
    except Error as e:
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
        cursor = conn.cursor(buffered=True)  # buffered: 一次读入全部结果，避免未消费结果集导致后续语句异常
        cursor.execute("SELECT name FROM customers WHERE id = %s", (cid,))
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

        cursor.execute("DELETE FROM customers WHERE id = %s", (cid,))
        conn.commit()
        print("删除成功！")
        cursor.close()
        conn.close()
    except Error as e:
        print(f"删除失败：{e}")


def count_by_source():
    """功能 5：按客户来源统计数量"""
    print("\n———— 按来源统计 ————")
    conn = get_connection()
    if conn is None:
        return
    try:
        cursor = conn.cursor(buffered=True)  # buffered: 一次读入全部结果，避免未消费结果集导致后续语句异常
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
    except Error as e:
        print(f"统计失败：{e}")


def export_csv(filename="customers.csv"):
    """功能 6：导出客户列表到 CSV 文件"""
    print(f"\n———— 导出到 {filename} ————")
    conn = get_connection()
    if conn is None:
        return
    try:
        cursor = conn.cursor(buffered=True)  # buffered: 一次读入全部结果，避免未消费结果集导致后续语句异常
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
    except Error as e:
        print(f"导出失败：{e}")


# ================== 主菜单 ==================

MENU = """
=========================================
            客户管理系统
=========================================
  1. 添加客户
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
            add_customer()
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
