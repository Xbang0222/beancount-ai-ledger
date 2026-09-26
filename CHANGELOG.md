# 更新日志

这里记录每个版本中值得注意的改动。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

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

[Unreleased]: https://github.com/Xbang0222/beancount-ai-ledger/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Xbang0222/beancount-ai-ledger/releases/tag/v0.1.0
