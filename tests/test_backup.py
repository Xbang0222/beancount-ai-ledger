"""backup：把账套打成一个压缩包，给不用 Git 的环境（云盘、网盘）保存和搬运。"""
import zipfile

from ledgerlib import cli


def _names(path):
    with zipfile.ZipFile(path) as z:
        return set(z.namelist())


def _only_zip(folder):
    zips = list(folder.glob("*.zip"))
    assert len(zips) == 1
    return zips[0]


def test_打包账本规则和脚本(ledger, capsys):
    (ledger / "CATEGORIES.md").write_text("规则", encoding="utf-8")
    assert cli.main(["backup"]) == 0
    out = capsys.readouterr().out
    z = _only_zip(ledger / "backups")
    assert z.name == "ledger-backup-20260923-213000.zip"
    names = _names(z)
    assert "ledger/ledger.toml" in names
    assert "ledger/CATEGORIES.md" in names
    assert "ledger/personal/journal/2026-09.beancount" in names
    assert "ledger/shop.beancount" in names
    assert "[OK] 已备份" in out
    assert "backups/ledger-backup-20260923-213000.zip" in out


def test_回报各账本最后一笔方便核对版本(ledger, capsys):
    assert cli.main(["backup"]) == 0
    out = capsys.readouterr().out
    assert "personal：交易 2 笔，最后一笔 2026-09-02 12:30 食堂 餐饮-午餐" in out
    assert "shop：交易 1 笔，最后一笔 2026-09-01 09:00 供应商 主营业务成本-采购" in out


def test_不打包环境目录原始账单和旧备份(ledger):
    for rel in (".venv/bin/python", ".git/config", "scripts/__pycache__/x.pyc",
                "exports/alipay.csv", "bill.xlsx", "old.zip", ".ledger.lock"):
        p = ledger / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    assert cli.main(["backup"]) == 0
    assert cli.main(["backup", "-o", str(ledger / "out")]) == 0
    names = _names(_only_zip(ledger / "out"))
    assert not [n for n in names if n.split("/")[1] in (".venv", ".git", "exports", "backups", "out")]
    assert not [n for n in names if n.endswith((".pyc", ".csv", ".xlsx", ".zip", ".lock"))]
    assert "ledger/personal.beancount" in names


def test_账本有错时不生成压缩包(ledger, capsys):
    j = ledger / "personal" / "journal" / "2026-09.beancount"
    j.write_text(j.read_text(encoding="utf-8") +
                 '\n2026-09-06 * "甲" "坏账"\n  Expenses:Food:Dining  1.00 CNY\n  Expenses:Other  1.00 CNY\n',
                 encoding="utf-8")
    assert cli.main(["backup"]) == 1
    assert "没有生成压缩包" in capsys.readouterr().out
    assert not (ledger / "backups").exists()


def test_空账本也能打包(empty_root, capsys):
    from ledgerlib import newbook

    assert newbook.cmd_new_book("personal") == 0
    capsys.readouterr()
    assert cli.main(["backup"]) == 0
    assert "personal：还没有交易" in capsys.readouterr().out


def test_解压后的账套可以直接校验(ledger, tmp_path_factory, capsys):
    assert cli.main(["backup"]) == 0
    dest = tmp_path_factory.mktemp("restore")
    with zipfile.ZipFile(_only_zip(ledger / "backups")) as z:
        z.extractall(dest)
    capsys.readouterr()
    assert cli.main(["--root", str(dest / "ledger"), "check"]) == 0
    assert "[OK] personal" in capsys.readouterr().out
