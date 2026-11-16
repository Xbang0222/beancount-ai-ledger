# 开发规范

适用于 `scripts/` 与 `tests/` 的修改，以及新克隆仓库的环境初始化。只记账、不修改脚本时无需阅读本文件。

## 1 环境初始化

每个新克隆执行一次；此后 `python3 scripts/ledger.py` 自动使用 `.venv`。

```bash
python3 scripts/bootstrap.py                                # 创建 .venv、安装依赖、校验账本
.venv/bin/python -m pip install -r requirements-dev.txt     # 开发依赖：pytest、ruff
git config core.hooksPath scripts/hooks                     # 启用提交钩子
python3 scripts/ledger.py doctor                            # 检查环境、账本与 Git 状态
```

## 2 检查

修改脚本或测试后，提交前执行：

```bash
.venv/bin/python -m ruff check scripts tests
.venv/bin/python -m pytest
```

校验分两层：

| 层 | 内容 |
|---|---|
| 命令内 | `add` / `pair` / `amend` / `void` / `fmt` 写盘后校验整本账，未通过即还原 |
| 提交前 | `scripts/hooks/pre-commit` 执行 `check` 与 `fmt --check`；改动脚本或测试时另执行 ruff 与 pytest；`commit-msg` 检查提交信息 |

推送后没有云端检查。每台设备、每个克隆都须启用钩子，`doctor` 会检查是否启用；未启用时入账命令会在末尾提示。

## 3 模块职责

实现位于 `scripts/ledgerlib/`，`scripts/ledger.py` 仅作入口转发。命令清单以 `python3 scripts/ledger.py --help` 为准。已有命令的用法不得随意变更，用户与规则文档均依赖这些命令。

| 模块 | 职责 |
|---|---|
| `config` | 读取 `ledger.toml`：账本清单、往来镜像、周期事项、时区、本位币、写法规则 |
| `entry` | 分录文本的检查与预处理，不访问磁盘 |
| `naming` | 对方与摘要的写法检查，`rules` 对照表；规则定义在 `[naming]`，未配置则不检查 |
| `journal` | 序时簿分块、行号与分录编号 |
| `store` | 加锁、写盘、整本校验、失败还原 |
| `add` / `pair` / `edit` / `fmt` | 入账、两本账同时入账、更正与作废、排版 |
| `brief` / `recurring` | 入账前的现场信息；周期事项漏记提醒，规则定义在 `[[recurring]]`，只提醒不代记 |
| `lookup` / `rulebook` | 按关键词检索规则文档与科目说明；规则文档路径的唯一来源，兼容 `rules/` 布局与根目录旧布局 |
| `books` / `query` / `reconcile` / `networth` / `display` | 加载账本与报错翻译、查询、对账、合并资产、输出对齐 |
| `dividend` / `fxrate` / `quote` | 按月利润分配、汇率与金银价格、基金股票等价格查询 |
| `doctor` / `env` / `backup` / `newbook` | 环境自检、依赖与 `.venv`、打包备份、新建账本 |
| `commitmsg` | 提交信息检查，由 `commit-msg` 钩子调用 |

## 4 约束

1. 代码中不得写死账本名或科目。新增账本、往来镜像、周期事项一律修改 `ledger.toml`。
2. 所有修改序时簿的命令必须经由 `store.commit` 或 `store.commit_many`。唯一例外是 `fmt`：它执行更严格的前后余额比对并自行写盘，但同样须持有 `store.book_lock`。
3. 各模块只承担一项职责。新逻辑放入对应模块，不得跨模块调用以下划线开头的内部函数。
4. 写法规则只在 `ledger.toml` 的 `[naming]` 维护；脚本引用规则文档的路径只经由 `rulebook`。
5. 新增或修改逻辑须配套 `tests/` 用例。测试使用 `conftest.py` 的 `ledger`（两本账）、`solo`（仅个人账）、`empty_root`（空目录）fixture 在临时目录构建账套，不得访问真实账本。
6. 需要在真实数据上验证时，先将账套复制到其他目录，再使用 `--root <副本目录>`。
7. 修改查询类命令后，以改动前的 `balances`、`report` 输出比对，确认口径没有变化。

## 5 文档与发布

- 规则文档位于 `rules/`，属于用户数据，升级时不覆盖；`scripts`、`tests`、`docs`、`AGENTS.md` 由升级流程整体替换，其中不得写入用户自定的规则。
- 面向用户的变更记入 `CHANGELOG.md` 的 `[Unreleased]`；版本号在 `scripts/ledgerlib/__init__.py`。
