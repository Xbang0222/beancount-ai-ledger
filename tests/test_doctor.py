"""doctor：第一次接手仓库时，一条命令说清该先做什么。"""
import shutil
import subprocess

import pytest

from ledgerlib import cli, doctor, newbook

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="需要 git")


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    """不真的调用 gh 查可见性；git 也不往 tmp_path 外面找仓库。"""
    monkeypatch.setattr(doctor, "github_visibility", lambda repo: None)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.mark.parametrize("url, repo", [
    ("https://github.com/Xbang0222/beancount-ai-ledger.git", "Xbang0222/beancount-ai-ledger"),
    ("https://github.com/someone/my-ledger", "someone/my-ledger"),
    ("git@github.com:someone/my-ledger.git", "someone/my-ledger"),
    ("ssh://git@ssh.github.com:443/someone/my-ledger.git", "someone/my-ledger"),  # 云电脑走 443 端口
    ("https://gitee.com/someone/my-ledger.git", None),
    ("", None),
])
def test_解析_GitHub_仓库名(url, repo):
    assert doctor.github_repo(url) == repo


def test_正常账套报告各账本且退出码为零(ledger, capsys):
    assert cli.main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "[OK] personal（测试个人账）：校验通过，交易 2 笔" in out
    assert "[OK] shop（测试商店账）" in out
    assert "[FAIL]" not in out


def test_新账本提示先初始化(empty_root, capsys):
    assert newbook.cmd_new_book("personal") == 0
    capsys.readouterr()
    assert cli.main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "[WARN] personal 还没有期初余额，也没有任何交易" in out
    assert "问清用户的账户和余额" in out
    assert "AGENTS.md" not in out   # 账套里没有引导章节，就不往那儿指


def test_AGENTS里有引导章节时提示指过去(empty_root, capsys):
    (empty_root / "AGENTS.md").write_text("# 须知\n\n### 首次使用（doctor 提示未初始化）\n", encoding="utf-8")
    assert newbook.cmd_new_book("personal") == 0
    capsys.readouterr()
    cli.main(["doctor"])
    assert "按 AGENTS.md「首次使用」，问清用户的账户和余额" in capsys.readouterr().out


def test_引导章节在_docs_里时优先指到那里(empty_root, capsys):
    (empty_root / "AGENTS.md").write_text("# 须知\n\n## 按情况查阅\n\n首次使用见 docs。\n", encoding="utf-8")
    (empty_root / "docs").mkdir()
    (empty_root / "docs" / "AI-SETUP.md").write_text("# 建账\n\n## 首次使用（doctor 提示未初始化）\n", encoding="utf-8")
    assert newbook.cmd_new_book("personal") == 0
    capsys.readouterr()
    cli.main(["doctor"])
    assert "按 docs/AI-SETUP.md「首次使用」，问清用户的账户和余额" in capsys.readouterr().out


def test_账本有错时报_FAIL_且退出码非零(ledger, capsys):
    j = ledger / "personal" / "journal" / "2026-09.beancount"
    j.write_text(j.read_text(encoding="utf-8") +
                 '\n2026-09-06 * "甲" "坏账"\n  Expenses:Food:Dining  1.00 CNY\n  Expenses:Other  1.00 CNY\n',
                 encoding="utf-8")
    assert cli.main(["doctor"]) == 1
    assert "[FAIL] personal：1 个校验错误" in capsys.readouterr().out


def test_配置写错时报_FAIL(ledger, capsys):
    (ledger / "ledger.toml").write_text("[books.personal]\nkind = \"family\"\n", encoding="utf-8")
    assert cli.main(["doctor"]) == 1
    assert "kind 只能是" in capsys.readouterr().out


def test_模板原样的_CATEGORIES_给出提醒(ledger, capsys):
    (ledger / "CATEGORIES.md").write_text(f"> **{doctor.TEMPLATE_MARK}。**\n", encoding="utf-8")
    cli.main(["doctor"])
    assert "CATEGORIES.md 还是模板原样" in capsys.readouterr().out


def test_模板原样的日常规则在_rules_目录时同样提醒(ledger, capsys):
    (ledger / "rules").mkdir()
    (ledger / "rules" / "daily.md").write_text(f"> **{doctor.TEMPLATE_MARK}。**\n", encoding="utf-8")
    cli.main(["doctor"])
    assert "rules/daily.md 还是模板原样" in capsys.readouterr().out


@needs_git
def test_origin_指向公开模板仓库时警告(ledger, capsys):
    _git(ledger, "init", "-q")
    _git(ledger, "remote", "add", "origin", "https://github.com/Xbang0222/beancount-ai-ledger.git")
    assert cli.main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "origin 指向公开的模板仓库" in out
    assert "不要 Fork" in out


@needs_git
def test_远程仓库公开时警告(ledger, monkeypatch, capsys):
    monkeypatch.setattr(doctor, "github_visibility", lambda repo: "PUBLIC")
    _git(ledger, "init", "-q")
    _git(ledger, "remote", "add", "origin", "git@github.com:someone/my-ledger.git")
    cli.main(["doctor"])
    assert "远程仓库 someone/my-ledger 是公开的" in capsys.readouterr().out


@needs_git
def test_私有远程仓库不警告(ledger, monkeypatch, capsys):
    monkeypatch.setattr(doctor, "github_visibility", lambda repo: "PRIVATE")
    _git(ledger, "init", "-q")
    _git(ledger, "remote", "add", "origin", "git@github.com:someone/my-ledger.git")
    cli.main(["doctor"])
    out = capsys.readouterr().out
    assert "（PRIVATE）" in out and "[WARN] 远程" not in out


@needs_git
def test_没有远程仓库时提醒备份(ledger, capsys):
    _git(ledger, "init", "-q")
    cli.main(["doctor"])
    out = capsys.readouterr().out
    assert "没有配置远程仓库" in out
    assert "没有远程仓库时" not in out   # 同上：没有那一节就只说怎么做


@needs_git
def test_不是_Git_仓库时提醒(ledger, capsys):
    cli.main(["doctor"])
    assert "账套目录不是 Git 仓库" in capsys.readouterr().out


@needs_git
def test_下一步先建私有仓库再初始化(empty_root, capsys):
    assert newbook.cmd_new_book("personal") == 0
    _git(empty_root, "init", "-q")
    _git(empty_root, "remote", "add", "origin", "https://github.com/Xbang0222/beancount-ai-ledger")
    capsys.readouterr()
    cli.main(["doctor"])
    todo = capsys.readouterr().out.split("下一步：")[1]
    assert todo.index("私有仓库") < todo.index("第一次使用")


def _git_init(root):
    subprocess.run(["git", "init", "-q", str(root)], check=True)


@pytest.mark.skipif(not shutil.which("git"), reason="需要 git")
def test_带了提交前检查脚本却没启用时自动启用(ledger, capsys):
    _git_init(ledger)
    (ledger / "scripts" / "hooks").mkdir(parents=True)
    (ledger / "scripts" / "hooks" / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
    doctor.cmd_doctor()
    assert "已自动启用" in capsys.readouterr().out
    assert doctor.hooks_missing() is False


@pytest.mark.skipif(not shutil.which("git"), reason="需要 git")
def test_提交前检查已启用时不提醒(ledger, capsys):
    _git_init(ledger)
    (ledger / "scripts" / "hooks").mkdir(parents=True)
    (ledger / "scripts" / "hooks" / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(ledger), "config", "core.hooksPath", "scripts/hooks"], check=True)
    doctor.cmd_doctor()
    out = capsys.readouterr().out
    assert "提交前自动检查已启用" in out and "core.hooksPath" not in out


@pytest.mark.skipif(not shutil.which("git"), reason="需要 git")
@pytest.mark.parametrize("style", ["absolute", "dot", "slash"])
def test_提交前检查路径的各种写法都算启用(ledger, capsys, style):
    _git_init(ledger)
    hooks = ledger / "scripts" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
    value = {"absolute": str(hooks), "dot": "./scripts/hooks", "slash": "scripts/hooks/"}[style]
    subprocess.run(["git", "-C", str(ledger), "config", "core.hooksPath", value], check=True)
    doctor.cmd_doctor()
    assert "提交前自动检查已启用" in capsys.readouterr().out


@needs_git
def test_自己的仓库留着模板项目文件时提醒删除(ledger, monkeypatch, capsys):
    monkeypatch.setattr(doctor, "github_visibility", lambda repo: "PRIVATE")
    (ledger / ".github" / "ISSUE_TEMPLATE").mkdir(parents=True)
    (ledger / ".github" / "CONTRIBUTING.md").write_text("贡献指南\n", encoding="utf-8")
    _git(ledger, "init", "-q")
    _git(ledger, "remote", "add", "origin", "git@github.com:someone/my-ledger.git")
    cli.main(["doctor"])
    out = capsys.readouterr().out
    assert "只属于公开模板项目的文件" in out
    assert "git rm -r .github/CONTRIBUTING.md .github/ISSUE_TEMPLATE" in out


@needs_git
def test_模板仓库本身不提醒删除模板项目文件(ledger, capsys):
    (ledger / ".github").mkdir()
    (ledger / ".github" / "CONTRIBUTING.md").write_text("贡献指南\n", encoding="utf-8")
    _git(ledger, "init", "-q")
    _git(ledger, "remote", "add", "origin", "https://github.com/Xbang0222/beancount-ai-ledger.git")
    cli.main(["doctor"])
    assert "只属于公开模板项目的文件" not in capsys.readouterr().out


ENTRY = '''2026-09-03 * "食堂" "餐饮-晚餐"
  time: "18:30"
  Expenses:Food:Dining  18.00 CNY
  Assets:Alipay
'''


@needs_git
@pytest.mark.parametrize("enabled", [False, True])
def test_改账后自动启用提交检查(ledger, capsys, enabled):
    _git_init(ledger)
    (ledger / "scripts" / "hooks").mkdir(parents=True)
    (ledger / "scripts" / "hooks" / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
    if enabled:
        _git(ledger, "config", "core.hooksPath", "scripts/hooks")
    entry = ledger / "entry.tmp"
    entry.write_text(ENTRY, encoding="utf-8")
    assert cli.main(["add", "personal", "--file", str(entry)]) == 0
    assert ("已自动启用" in capsys.readouterr().out) is not enabled
    assert doctor.hooks_missing() is False


def test_不是_Git_仓库或没带检查脚本时不提醒(ledger):
    assert doctor.hooks_missing() is False
    (ledger / "scripts" / "hooks").mkdir(parents=True)
    (ledger / "scripts" / "hooks" / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
    assert doctor.hooks_missing() is False


# ---------- 余额久未核对的提醒 ----------

@pytest.fixture
def in_november(monkeypatch):
    """把「今天」挪到 11 月：脚手架里 9 月初的账户此时已经两个多月没核对。"""
    from datetime import datetime

    from ledgerlib import entry

    monkeypatch.setattr(entry, "now_local", lambda: datetime(2026, 11, 10, 9, 0))


def _stale(book="personal"):
    from ledgerlib import config
    from ledgerlib.books import load_book

    return doctor.stale_accounts(book, load_book(book)[0], config.load(), entry_today())


def entry_today():
    from ledgerlib import entry

    return entry.now_local().date()


def test_刚记不久的账户不提醒核对(ledger, capsys):
    assert _stale() == []
    cli.main(["doctor"])
    assert "没和实际余额核对" not in capsys.readouterr().out


def test_有余额的账户久未核对时提醒_往来镜像不算(ledger, capsys, in_november):
    assert _stale() == [("Assets:Wechat", 70), ("Assets:Alipay", 69)]   # 从第一笔发生额算起
    assert cli.main(["doctor"]) == 0                                     # 只是提醒，不算失败
    out = capsys.readouterr().out
    assert "[WARN] personal：2 个有余额的账户超过 35 天没和实际余额核对（最久 Assets:Wechat，70 天）" in out
    assert "Assets:Wechat、Assets:Alipay" in out and "Receivable:Shop" not in out


def test_核对过的账户从最近一次断言算起(ledger, in_november):
    j = ledger / "personal" / "journal" / "2026-09.beancount"
    j.write_text(j.read_text(encoding="utf-8") + "\n2026-11-01 balance Assets:Wechat -100.00 CNY\n",
                 encoding="utf-8")
    assert _stale() == [("Assets:Alipay", 69)]


def test_reconcile_days为零时不提醒(ledger, in_november):
    cfg = ledger / "ledger.toml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace(
        'base_currency = "CNY"\n', 'base_currency = "CNY"\nreconcile_days = 0\n'), encoding="utf-8")
    assert _stale() == []
