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
    assert "首次使用" in out


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
    assert "没有配置远程仓库" in capsys.readouterr().out


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
def test_带了提交前检查脚本却没启用时提醒(ledger, capsys):
    _git_init(ledger)
    (ledger / "scripts" / "hooks").mkdir(parents=True)
    (ledger / "scripts" / "hooks" / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
    doctor.cmd_doctor()
    assert "git config core.hooksPath scripts/hooks" in capsys.readouterr().out


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
