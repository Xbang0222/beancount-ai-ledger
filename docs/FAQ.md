# 常见问题

**支持哪些 AI 工具？**
能读取仓库文件、能执行命令的 AI 编程助手都可以。Claude Code 和 Gemini CLI 通过 `CLAUDE.md`、`GEMINI.md` 载入规则，Codex、Cursor、GitHub Copilot 等直接读取 `AGENTS.md`。其他工具的用法见[使用指南第九节](GUIDE.md#九在其他-ai-工具里用)。

**Windows 能用吗？**
能。命令里的 `python3` 换成 `python` 或 `py`。PowerShell 没有 heredoc，手动入账时先把分录存成 UTF-8 文件，再用 `add <账本> --file <文件>`。

**在 Claude Code 网页版、Codex 云端这类云环境里呢？**
每次会话都是新环境，AI 会按 `AGENTS.md` 先运行 `bootstrap.py` 安装依赖，然后照常记账。

**不会用 Git 能用吗？账本存在哪？**
能。账本放在豆包这类 AI 的云电脑里，每天往你自己的云盘备份一份，做法见[不用 Git：只用豆包记账](NO-GIT.md)。

**多台设备同时记账会冲突吗？**
AI 每次开始前会先 `git pull --ff-only`。同一台机器上 `add` 带文件锁，并发写入不会互相覆盖。

**能看图表吗？**
可以用 [Fava](https://github.com/beancount/fava)：`pip install fava && fava personal.beancount`，然后打开 http://localhost:5000 。

**不用 AI 可以吗？**
可以，所有功能都是命令行脚本。

**推送后有云端检查吗？**
没有。把关在本地：命令写盘后整本校验，提交前由钩子跑 `check`、`fmt --check` 并核对提交信息，所以每台设备、每个克隆都要启用一次钩子（`git config core.hooksPath scripts/hooks`），`doctor` 会查有没有启用。想自己接 CI 的，在流水线里跑 `check`、`fmt --check`，再用 `commit-msg --range A..B` 检查推上来的提交即可。

**模板更新后怎么升级？**
只同步脚本和测试，账本数据不动：

```bash
git remote add upstream https://github.com/Xbang0222/beancount-ai-ledger.git   # 只需一次
git fetch upstream
git checkout upstream/main -- scripts tests requirements.txt requirements-dev.txt pyproject.toml
python3 -m pytest tests/ -q && python3 scripts/ledger.py check
git commit -m "chore: 同步上游脚本"
```

`AGENTS.md` 和你自己的规则文件（`rules/`，旧版为 `CATEGORIES.md`）里可能有你改过的内容：规则文件不要覆盖，`AGENTS.md` 请对照[更新日志](../CHANGELOG.md)手动合并；要换成新版 `AGENTS.md` 的，把 `docs` 一起取下来（新版把不常用的章节放在 `docs/AI-SETUP.md`、`docs/AI-TASKS.md`）。让 AI 来做的话，说一句"帮我升级记账项目"。
