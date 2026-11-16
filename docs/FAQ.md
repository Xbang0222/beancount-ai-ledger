# 常见问题

- 适用对象：用户。
- 相关文档：[使用指南](GUIDE.md)、[命令与配置](REFERENCE.md)。

## 1 工具与环境

| 问题 | 回答 |
|---|---|
| 支持哪些 AI 工具 | 能读取仓库文件并执行命令的 AI 编程助手均可。Claude Code 与 Gemini CLI 通过 `CLAUDE.md`、`GEMINI.md` 载入规则；Codex、Cursor、GitHub Copilot 等直接读取 `AGENTS.md`。其他工具的用法见[使用指南第 9 节](GUIDE.md#9-其他-ai-工具) |
| 是否支持 Windows | 支持。命令中的 `python3` 换为 `python` 或 `py`。PowerShell 不支持 heredoc，手动入账时先将分录保存为 UTF-8 文件，再执行 `add <账本> --file <文件>` |
| Claude Code 网页版、Codex 云端等云环境 | 每次会话均为新环境，AI 按 `AGENTS.md` 先执行 `bootstrap.py` 安装依赖，随后照常记账 |
| 不使用 Git 时账本存放在哪里 | 存放在豆包这类 AI 的云电脑中，每日向用户自己的云盘备份一份，做法见[不使用 Git：通过豆包记账](NO-GIT.md) |
| 是否可以不使用 AI | 可以。全部功能均为命令行脚本，命令见[命令与配置](REFERENCE.md) |
| 是否可以查看图表 | 可使用 [Fava](https://github.com/beancount/fava)：执行 `pip install fava && fava personal.beancount`，然后访问 http://localhost:5000 |

## 2 数据与校验

| 问题 | 回答 |
|---|---|
| 多台设备同时记账是否冲突 | AI 每次开始前先执行 `git pull --ff-only`。同一台机器上 `add` 带文件锁，并发写入不会相互覆盖 |
| 推送后是否有云端检查 | 没有，校验在本地完成：命令写盘后校验整本账；提交前由钩子执行 `check`、`fmt --check` 并检查提交信息。因此每台设备、每个克隆均须启用一次钩子（`git config core.hooksPath scripts/hooks`），`doctor` 检查是否已启用。自建 CI 时，在流水线中执行 `check`、`fmt --check`，再以 `commit-msg --range A..B` 检查推送的提交 |

## 3 升级

模板更新后，只同步脚本、测试与说明文档，不改动账本数据：

```bash
git remote add upstream https://github.com/Xbang0222/beancount-ai-ledger.git   # 只需一次
git fetch upstream
git checkout upstream/main -- scripts tests docs AGENTS.md requirements.txt requirements-dev.txt pyproject.toml
python3 -m pytest tests/ -q && python3 scripts/ledger.py check
git commit -m "chore: 同步上游脚本"
```

- 规则文件（`rules/`，旧版为根目录的 `CATEGORIES.md` 等）、`STATE.md`、`ledger.toml` 与各账本目录属于用户数据，不得覆盖。
- 修改过 `AGENTS.md` 的，先对照[更新日志](../CHANGELOG.md)确认差异；需要保留自己的修改时，从上述命令中去掉 `AGENTS.md` 后手动合并。新版 `AGENTS.md` 依赖 `docs/` 下的文档，两者须一并更新。
- 交由 AI 处理时，说明「帮我升级记账项目」即可，AI 按 `docs/AI-TASKS.md`「升级工具」执行。
