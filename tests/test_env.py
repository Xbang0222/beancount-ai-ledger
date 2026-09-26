"""运行环境：缺依赖时给出能照做的提示，有 .venv 时自动改用它，不抛 traceback。"""
import os
import sys

from ledgerlib import env


def _fake_call(calls, rc=0):
    def call(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return rc
    return call


def test_依赖齐全时不干预(monkeypatch):
    monkeypatch.setattr(env, "missing_modules", lambda: [])
    assert env.ensure("ledger.py", ["check"]) is None


def test_缺依赖且有_venv_时用_venv_重跑同一条命令(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(env, "missing_modules", lambda: ["beancount"])
    monkeypatch.setattr(env, "venv_python", lambda: str(tmp_path / "python"))
    monkeypatch.setattr(env, "in_venv", lambda: False)
    monkeypatch.delenv(env.REEXEC_FLAG, raising=False)
    monkeypatch.setattr(env.subprocess, "call", _fake_call(calls, rc=7))

    assert env.ensure("scripts/ledger.py", ["add", "personal"]) == 7
    cmd, kwargs = calls[0]
    assert cmd[0] == str(tmp_path / "python")
    assert cmd[1] == os.path.abspath("scripts/ledger.py")
    assert cmd[2:] == ["add", "personal"]
    assert kwargs["env"][env.REEXEC_FLAG] == "1"


def test_已经切换过一次仍缺依赖时不再循环重启(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(env, "missing_modules", lambda: ["beancount"])
    monkeypatch.setattr(env, "venv_python", lambda: "/somewhere/python")
    monkeypatch.setattr(env, "in_venv", lambda: False)
    monkeypatch.setenv(env.REEXEC_FLAG, "1")
    monkeypatch.setattr(env.subprocess, "call", _fake_call(calls))

    assert env.ensure("ledger.py", ["check"]) == 3
    assert not calls
    assert ".venv 里也缺依赖" in capsys.readouterr().out


def test_没有_venv_时提示运行_bootstrap(monkeypatch, capsys):
    monkeypatch.setattr(env, "missing_modules", lambda: ["beancount"])
    monkeypatch.setattr(env, "venv_python", lambda: None)
    assert env.ensure("ledger.py", ["check"]) == 3
    out = capsys.readouterr().out
    assert "缺少依赖：beancount" in out and "scripts/bootstrap.py" in out


def test_beancount_2_视为缺依赖(monkeypatch):
    monkeypatch.setattr(env, "find_spec", lambda name: object())
    monkeypatch.setattr(env, "beancount_version", lambda: "2.3.6")
    assert any("beancount>=3" in m for m in env.missing_modules())


def test_beancount_3_视为齐全(monkeypatch):
    monkeypatch.setattr(env, "find_spec", lambda name: object())
    monkeypatch.setattr(env, "beancount_version", lambda: "3.2.3")
    assert env.missing_modules() == []


def test_按平台列出需要的模块(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    assert "tzdata" in env.required_modules()
    monkeypatch.setattr(sys, "platform", "linux")
    assert "tzdata" not in env.required_modules()


def test_找得到各平台的_venv_解释器(monkeypatch, tmp_path):
    monkeypatch.setattr(env, "VENV_DIR", str(tmp_path / ".venv"))
    assert env.venv_python() is None
    win = tmp_path / ".venv" / "Scripts" / "python.exe"
    win.parent.mkdir(parents=True)
    win.write_text("")
    assert env.venv_python() == str(win)
