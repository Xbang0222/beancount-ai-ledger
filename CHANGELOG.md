# 更新日志

这里记录每个版本中值得注意的改动。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## [0.2.0] - 2026-10-04

### 新增

- `find` / `amend` / `void` 命令：按关键词找到分录的编号，再整笔更正或作废。改账和入账走同一套"写盘、校验整本账、失败还原"，不再需要手动编辑序时簿。
- `add` 的新守卫：拒绝内容相同的重复分录（`--allow-duplicate` 放行）、缺对方或摘要的分录、格式不对的 `time`，以及 `open` 这类科目表指令。
- 提交前自动检查 `scripts/hooks/pre-commit`：账本校验、往来对账、排版检查，改了脚本再跑 ruff 和测试。`doctor` 会提醒启用。
- `backup` 命令：把整个账套打成一个压缩包，输出各账本的交易笔数和最后一笔。账本有错误时不生成压缩包。
- 不用 Git 也能用：`AGENTS.md` 新增「不用 Git 时」一节，账本以压缩包形式存在用户的云盘里，适合豆包这类自带云电脑和云盘的 AI。给用户看的做法和开场白写在 `docs/NO-GIT.md`。

### 变更

- `add` / `amend` 按日期和时间把分录插到序时簿里对应的位置，补记较早的账不再打乱顺序。
- `fmt` 重排时，紧贴分录上方的注释跟着分录走。
- 写盘沿用文件原有的换行符。
- 开发依赖加入 ruff，配置在 `pyproject.toml`；CI 增加代码规范检查。
- 汇率改为现查现用，不再写进账本：算总资产前查当天汇率，用 `networth --rate` 传入；`CATEGORIES.md` 第 5 节给出了云端环境也能访问的取数命令。基金、股票净值仍然用 `price` 记账。
- 有多本账时，回答"我有多少钱"按合并口径列示，不列账本之间的往来。
- `doctor` 发现账套目录不是 Git 仓库时，同时给出建私有仓库和改用云盘两条路。
- README 只保留简介和文档入口，详细内容拆到 `docs/`：`QUICKSTART.md`（用 Git 开始）、`NO-GIT.md`（不用 Git）、`REFERENCE.md`（命令与配置）、`FAQ.md`（常见问题）。英文 README 不再重复命令和配置，改为指向这些文档。

## [0.1.0] - 2026-09-27

首个公开版本。

### 新增

- `scripts/ledger.py` 命令：`doctor`、`check`、`add`、`recent`、`summary`、`report`、`balances`、`tag`、`networth`、`reconcile`、`fmt`、`books`、`new-book`。
- `add` 的入账保护：一次只录一笔，自动注入录入时间，拒绝未来的日期和时间，校验失败整笔回滚；支持余额断言，支持用 `--file` 从文件读取分录。
- 多账本：在 `ledger.toml` 声明账本和往来镜像；`reconcile` 核对往来，`networth` 合并时抵销往来并折算外币。
- `new-book` 提供 personal、business、minimal 三种科目表模板；`--link` 生成往来科目，`--no-consolidate` 用于与他人共有的账本。
- `scripts/bootstrap.py` 把依赖装进仓库的 `.venv`；缺依赖时 `ledger.py` 自动改用 `.venv`。
- 给 AI 用的 `AGENTS.md`、`CLAUDE.md`、`GEMINI.md` 和 `.claude/settings.json`。
- 中英文 README、使用指南、分录范例和示例账本。
- CI：Ubuntu（Python 3.9、3.13）和 Windows（Python 3.12）；用模板建的账本仓库只跑账本校验。

[Unreleased]: https://github.com/Xbang0222/beancount-ai-ledger/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Xbang0222/beancount-ai-ledger/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Xbang0222/beancount-ai-ledger/releases/tag/v0.1.0
