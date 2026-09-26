# 参与贡献

感谢你愿意改进这个项目。提交之前，请先看完下面几条。

## 报告问题

- 通过 [Issue 表单](https://github.com/Xbang0222/beancount-ai-ledger/issues/new/choose) 提交 bug 或建议。
- **不要贴真实的账本内容。** 复现问题请用 `examples/demo` 里的示例账本，或者自己造几笔假数据。
- 附上 `python3 scripts/ledger.py doctor` 的输出，贴之前删掉仓库地址等个人信息。
- 安全问题不要公开提交，见 [SECURITY.md](SECURITY.md)。

## 开发环境

```bash
git clone https://github.com/Xbang0222/beancount-ai-ledger.git
cd beancount-ai-ledger
python3 -m venv .venv
. .venv/bin/activate              # Windows：.venv\Scripts\activate
pip install -r requirements-dev.txt
python3 -m pytest tests/ -q
```

## 提交 Pull Request

1. Fork 本仓库，从 `main` 新建分支。Fork 只用来提交代码，不要在里面记真实的账。
2. 改代码的同时补测试。测试用 `tests/conftest.py` 里的 fixture 在临时目录搭账套，不要读写仓库里的账本文件。
3. 在本地跑一遍 CI 会跑的检查：

   ```bash
   python3 -m pytest tests/ -q
   python3 scripts/ledger.py check
   python3 scripts/ledger.py fmt --check
   python3 scripts/ledger.py --root examples/demo check
   bean-check examples/cookbook.beancount
   ```

4. 提交信息使用 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/v1.0.0/)，格式为 `type(scope): 摘要`，如 `fix(script): add 读取带 BOM 的文件`、`docs: 补充导入账单的说明`。
5. 用户能感知到的改动，在 [CHANGELOG.md](../CHANGELOG.md) 的 `[Unreleased]` 下补一条。
6. 发起 Pull Request，写清楚改了什么、为什么改。

## 约定

- 代码里不写死账本名。账本、往来镜像、时区、本位币都从 `ledger.toml` 读取。
- 用户和 AI 都依赖现有命令的用法与输出格式，要改的话请先开 Issue 讨论。
- 只用标准库和 `requirements.txt` 里的依赖。新增依赖请先讨论。
- 面向用户的输出、文档和注释用中文。

## 发布新版本（维护者）

1. 更新 `scripts/ledgerlib/__init__.py` 里的 `__version__`，把 `CHANGELOG.md` 的 `[Unreleased]` 整理成新版本的条目。
2. 合并到 `main` 后，推送 `v<版本号>` 标签，或者在 Actions 页面手动运行 Release 工作流。
3. 工作流会先跑测试，再按 `CHANGELOG.md` 创建 GitHub Release。
