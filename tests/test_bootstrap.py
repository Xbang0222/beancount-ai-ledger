"""bootstrap：只在缺依赖时建 .venv 安装，不往系统 Python 里装包。"""
import sys

import bootstrap


def _recorder(monkeypatch, rc=0):
    calls = []

    def call(cmd, **kwargs):
        calls.append(cmd)
        return rc
    monkeypatch.setattr(bootstrap.subprocess, "call", call)
    return calls


def test_依赖齐全时不安装_只校验(monkeypatch, capsys):
    monkeypatch.setattr(bootstrap.env, "missing_modules", lambda: [])
    calls = _recorder(monkeypatch)
    assert bootstrap.main([]) == 0
    assert calls == [[sys.executable, bootstrap.LEDGER, "check"]]
    assert "不需要安装" in capsys.readouterr().out


def test_缺依赖时装进已有的_venv_并用它校验(monkeypatch):
    monkeypatch.setattr(bootstrap.env, "missing_modules", lambda: ["beancount"])
    monkeypatch.setattr(bootstrap.env, "in_venv", lambda: False)
    monkeypatch.setattr(bootstrap.env, "venv_python", lambda: "/repo/.venv/bin/python")
    calls = _recorder(monkeypatch)
    assert bootstrap.main(["-i", "https://mirror.example/simple"]) == 0
    pip = [c for c in calls if "install" in c][0]
    assert pip[:4] == ["/repo/.venv/bin/python", "-m", "pip", "install"]
    assert pip[-2:] == ["--index-url", "https://mirror.example/simple"]
    assert calls[-1] == ["/repo/.venv/bin/python", bootstrap.LEDGER, "check"]


def test_建不了_venv_时给出办法(monkeypatch, capsys):
    monkeypatch.setattr(bootstrap.env, "missing_modules", lambda: ["beancount"])
    monkeypatch.setattr(bootstrap.env, "in_venv", lambda: False)
    monkeypatch.setattr(bootstrap.env, "venv_python", lambda: None)
    _recorder(monkeypatch, rc=1)
    assert bootstrap.main([]) == 3
    assert "创建虚拟环境失败" in capsys.readouterr().out


def test_安装失败时提示换镜像(monkeypatch, capsys):
    monkeypatch.setattr(bootstrap.env, "missing_modules", lambda: ["beancount"])
    monkeypatch.setattr(bootstrap.env, "in_venv", lambda: True)
    calls = []

    def call(cmd, **kwargs):
        calls.append(cmd)
        return 0 if "--version" in cmd else 1  # pip 可用，但 install 失败
    monkeypatch.setattr(bootstrap.subprocess, "call", call)
    assert bootstrap.main(["--no-check"]) == 3
    assert "换镜像" in capsys.readouterr().out
