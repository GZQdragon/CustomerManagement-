# 客户管理系统（Customer Management）

一个基于 Python 的客户信息管理小工具：既能用图形界面表单录入，也保留了早期的控制台版本。
支持客户信息的新增 / 修改 / 删除、关键字搜索与来源筛选、按来源统计人数，以及导出 Excel 可直接打开的 CSV。

> 仓库只收录**源码与文档**。可执行文件（`.exe`）、客户数据库（`customers.db`）和界面截图属于本地运行产物，
> 已写入 `.gitignore`，不入库 —— 客户端数据不应上传到公开仓库。

## 功能特性

- **表单式录入**：姓名、手机号、邮箱、来源、备注一次填完，点「保存」或按回车即可
- **搜索与筛选**：按姓名 / 手机号 / 邮箱 / 备注模糊搜索，可叠加来源筛选；搜索框灰字提示不会被当成关键字
- **表单校验**：手机号需为 11 位中国大陆号；邮箱可留空（自动记为「无」）；出错时输入框标红并直接说明原因
- **列表交互**：点表头排序（▲ / ▼）、鼠标划过高亮、双击某行载入表单修改、新增或修改后该行短暂高亮
- **按来源统计**：锚定在按钮上的弹层，显示每个来源的人数与占比横条
- **导出 CSV**：用 `utf-8-sig` 编码写入，Excel 打开中文不乱码
- **旧数据兼容**：老库自动补上 `remark`（备注）列，与早期控制台版共用同一个 `customers.db`
- **高分屏适配**：按系统 DPI 缩放，窗口尺寸自动收敛到屏幕范围内

## 目录结构

```
.
├── README.md
├── .gitignore
├── src/
│   ├── 客户管理系统（图形界面）.py     图形界面版主程序（tkinter + SQLite）
│   ├── Customer Management (SQLite).py  控制台版，免安装数据库
│   ├── Customer Management.py          控制台版，需要本机 MySQL
│   └── test_customer_gui.py            图形界面版自动化测试
└── docs/
    └── 使用说明.txt                    面向使用者的完整操作说明
```

## 三个版本怎么选

| 程序 | 界面 | 数据存储 | 适用场景 |
| --- | --- | --- | --- |
| `客户管理系统（图形界面）.py` | 图形界面（tkinter） | `customers.db`（SQLite） | **推荐**，日常录入维护 |
| `Customer Management (SQLite).py` | 控制台菜单 | `customers.db`（SQLite） | 无图形环境、或习惯命令行 |
| `Customer Management.py` | 控制台菜单 | 本机 MySQL（`customer_db.customers`） | 已有 MySQL、想做集中存储 |

图形界面版与控制台 SQLite 版**共用同一个 `customers.db`**，两份程序的数据完全互通。

## 快速开始

环境要求：Python 3.x。

图形界面版只依赖标准库（`tkinter`、`sqlite3`），不需要安装任何第三方包：

```bash
cd src
python "客户管理系统（图形界面）.py"
```

首次运行会在程序所在目录自动创建 `customers.db`。调试时可以用 `--db` 指定另一个数据库文件：

```bash
python "客户管理系统（图形界面）.py" --db D:/data/test.db
```

MySQL 控制台版需要额外安装依赖，并通过**环境变量**提供数据库密码（密码不写在代码里）：

```bash
pip install mysql-connector-python

# 先在当前终端设置密码（关掉终端就失效）
set MYSQL_PASSWORD=你的密码             # Windows CMD
$env:MYSQL_PASSWORD="你的密码"          # Windows PowerShell
export MYSQL_PASSWORD=你的密码          # macOS / Linux

python "Customer Management.py"
```

连接信息可用环境变量覆盖，默认值为 `MYSQL_HOST=localhost`、`MYSQL_USER=root`、`MYSQL_DATABASE=customer_db`。
首次运行会自动创建数据库 `customer_db` 与表 `customers`（`utf8mb4`）。

## 运行自检

`src/test_customer_gui.py` 用**真实数据库的副本**跑 59 项检查（数据层、校验规则、增删改查、搜索、统计、排序、导出、弹层等），不会改动原始数据：

```bash
cd src
python test_customer_gui.py
```

注意：该脚本从**它所在目录**读取 `客户管理系统（图形界面）.py` 和 `customers.db`，所以两者需要放在同一目录。
仓库里不包含 `customers.db`，本地运行时先让主程序生成一份（或从你自己的数据目录拷一份副本）再跑测试。
无图形环境时，脚本会自动跳过界面部分，只跑数据层检查。

## 数据与备份

所有客户数据都在程序旁边的 `customers.db` 这一个文件里。备份 = 关闭程序后复制该文件。
换电脑时把 `customers.db` 和新程序放在同一文件夹，数据就回来了。

## 文档

完整的使用说明（界面操作、常见问题、数据备份）见 [`docs/使用说明.txt`](docs/使用说明.txt)。

## 注意

- `src/Customer Management.py` 的数据库密码从环境变量 `MYSQL_PASSWORD` 读取，**不要把密码写回代码**或提交到仓库。
- 可执行文件建议后续通过 GitHub Releases 分发，而不是提交到仓库。
