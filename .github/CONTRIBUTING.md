# 贡献指南

- 适用对象：向本项目提交问题或代码的贡献者。
- 相关文档：开发环境、模块职责与开发约束见 [`docs/DEVELOPMENT.md`](../docs/DEVELOPMENT.md)；提交信息规范见 [`docs/COMMITS.md`](../docs/COMMITS.md)。

## 1 报告问题

- 通过 [Issue 表单](https://github.com/Xbang0222/beancount-ai-ledger/issues/new/choose)提交缺陷或建议。
- **不得粘贴真实的账本内容。** 复现问题使用 `examples/demo` 的示例账本，或自行构造虚拟数据。
- 附上 `python3 scripts/ledger.py doctor` 的输出，粘贴前删除仓库地址等个人信息。
- 安全问题不得公开提交，处理方式见 [SECURITY.md](SECURITY.md)。

## 2 开发环境

```bash
git clone https://github.com/Xbang0222/beancount-ai-ledger.git
cd beancount-ai-ledger
python3 -m venv .venv
. .venv/bin/activate              # Windows：.venv\Scripts\activate
pip install -r requirements-dev.txt
python3 -m pytest tests/ -q
```

## 3 提交 Pull Request

1. Fork 本仓库，从 `main` 新建分支。Fork 仅用于提交代码，不得在其中登记真实账目。
2. 修改代码时同步补充测试。测试使用 `tests/conftest.py` 的 fixture 在临时目录构建账套，不得读写仓库中的账本文件。
3. 在本地执行下列检查。仓库没有云端 CI，合并前的质量由这一步保证：

   ```bash
   python3 -m ruff check scripts tests
   python3 -m pytest tests/ -q
   python3 scripts/ledger.py check
   python3 scripts/ledger.py fmt --check
   python3 scripts/ledger.py --root examples/demo check
   bean-check examples/cookbook.beancount
   ```

4. 提交信息首行为 `类型: 摘要`：类型取自 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/v1.0.0/)，摘要使用书面中文，不带括号，例如 `fix: 修正 add 读取带 BOM 的文件`、`docs: 补充导入账单的说明`。`scripts/hooks/commit-msg` 负责检查，规范见 [`docs/COMMITS.md`](../docs/COMMITS.md)。
5. 用户可感知的改动在 [CHANGELOG.md](../CHANGELOG.md) 的 `[Unreleased]` 下补充一条。
6. 发起 Pull Request，说明改动内容与原因。

## 4 约定

- 代码中不得写死账本名。账本、往来镜像、时区、本位币均从 `ledger.toml` 读取。
- 用户与 AI 均依赖现有命令的用法与输出格式；需要变更时先开 Issue 讨论。
- 只使用标准库与 `requirements.txt` 中的依赖；新增依赖须先讨论。
- 面向用户的输出、文档与注释使用中文，文体按现有文档：条款化表述、统一术语、章节编号。

## 5 发布新版本

本节适用于维护者。

1. 更新 `scripts/ledgerlib/__init__.py` 的 `__version__`，将 `CHANGELOG.md` 的 `[Unreleased]` 整理为新版本的条目。
2. 合并到 `main` 后推送 `v<版本号>` 标签，或在 Actions 页面手动运行 Release 工作流。
3. 工作流先执行测试，再按 `CHANGELOG.md` 创建 GitHub Release。
