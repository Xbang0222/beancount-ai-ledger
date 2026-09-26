"""CLI：缺参数或参数非法时给出友好报错与非零退出码，绝不抛 traceback。"""
import pytest

from ledgerlib import cli, config


def _exit_code(argv):
    """argparse 的用法错误走 SystemExit；正常路径返回 main 的返回值。"""
    try:
        return cli.main(argv)
    except SystemExit as ex:
        return ex.code


@pytest.mark.parametrize("argv", [
    ["add"],                      # 缺账本名
    ["summary"],                  # 缺账本名
    ["balances"],                 # 缺账本名
    ["tag", "personal"],          # 缺标签
    ["report"],                   # 缺账本名
    ["recent"],                   # 缺账本名
    ["new-book"],                 # 缺账本名
])
def test_缺参数不抛_traceback_且退出码非零(argv, capsys):
    assert _exit_code(argv) != 0
    assert "Traceback" not in capsys.readouterr().err


@pytest.mark.parametrize("book", ["foo", "Personal", ""])
def test_错误账本名被拒(ledger, book, capsys):
    assert _exit_code(["balances", book]) != 0
    assert "Traceback" not in capsys.readouterr().err


@pytest.mark.parametrize("ym", ["2026-13", "2026-00", "202609", "2026-9", "九月"])
def test_非法月份被拒而不是静默出空报表(ledger, ym, capsys):
    """打错月份曾经会输出一张空报表且退出码 0，看起来像“这个月没花钱”。"""
    assert _exit_code(["summary", "personal", ym]) != 0
    assert "支出大类" not in capsys.readouterr().out


@pytest.mark.parametrize("rate", ["7.1", "usd=7.1", "USD=", "USD=-1", "USD=abc", "USD=0"])
def test_非法汇率参数被拒(ledger, rate):
    assert _exit_code(["networth", "--rate", rate]) != 0


@pytest.mark.parametrize("n", ["0", "-3", "abc"])
def test_recent_笔数必须为正整数(ledger, n):
    assert _exit_code(["recent", "personal", "-n", n]) != 0


def test_version_输出版本号(capsys):
    from ledgerlib import __version__

    assert _exit_code(["--version"]) == 0
    assert __version__ in capsys.readouterr().out


def test_无命令时打印帮助并返回非零(capsys):
    assert cli.main([]) == 1
    out = capsys.readouterr().out
    assert "usage" in out and "check" in out


def test_没有配置文件时友好报错(empty_root, capsys):
    assert cli.main(["check"]) == 2
    assert "找不到 ledger.toml" in capsys.readouterr().out


def test_合法月份零笔记录时明确提示而非空表(ledger, capsys):
    assert cli.main(["summary", "personal", "2026-01"]) == 0
    assert "无收支记录" in capsys.readouterr().out


def test_report_零笔记录时明确提示(ledger, capsys):
    assert cli.main(["report", "personal", "2026-01"]) == 0
    assert "无收支记录" in capsys.readouterr().out


def test_check_默认连带对账(ledger, capsys):
    assert cli.main(["check"]) == 0
    assert "跨账套往来对账" in capsys.readouterr().out


def test_check_可跳过对账(ledger, capsys):
    assert cli.main(["check", "--no-reconcile"]) == 0
    assert "跨账套往来对账" not in capsys.readouterr().out


def test_只有个人账时_check_不出对账段落(solo, capsys):
    assert cli.main(["check"]) == 0
    out = capsys.readouterr().out
    assert "[OK] personal" in out
    assert "跨账套往来对账" not in out


def test_账本有错时_check_不出对账结论(ledger, capsys):
    j = ledger / "personal" / "journal" / "2026-09.beancount"
    j.write_text(j.read_text(encoding="utf-8") +
                 '\n2026-09-06 * "甲" "坏账"\n  Expenses:Food:Dining  1.00 CNY\n  Expenses:Other  1.00 CNY\n',
                 encoding="utf-8")
    assert cli.main(["check"]) == 1
    out = capsys.readouterr().out
    assert "跳过跨账套对账" in out
    assert "personal/journal/2026-09.beancount:" in out  # 错误带文件与行号


def test_查询命令在正常账本上可用(ledger):
    assert cli.main(["balances", "personal"]) == 0
    assert cli.main(["summary", "personal", "2026-09"]) == 0
    assert cli.main(["report", "personal", "2026-09"]) == 0
    assert cli.main(["report", "shop"]) == 0
    assert cli.main(["tag", "personal", "trip", "2026-09"]) == 0
    assert cli.main(["recent", "personal", "-n", "1"]) == 0
    assert cli.main(["reconcile"]) == 0
    assert cli.main(["networth"]) == 0
    assert cli.main(["books"]) == 0
    assert cli.main(["fmt", "--check", "shop"]) == 0


def test_books_列出账本与镜像(ledger, capsys):
    assert cli.main(["books"]) == 0
    out = capsys.readouterr().out
    assert "personal" in out and "shop" in out and "business" in out
    assert "往来镜像 2 对" in out


def test_root_参数切换账套目录(ledger, monkeypatch, capsys):
    monkeypatch.setattr(config, "ROOT", "/nonexistent")
    assert cli.main(["--root", str(ledger), "check"]) == 0
    assert "[OK] shop" in capsys.readouterr().out
