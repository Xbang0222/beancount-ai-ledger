"""backup：把账套打成一个压缩包，给没有远程仓库的环境（云盘、网盘）保存和搬运。"""
import subprocess
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
    for rel in (".venv/bin/python", "scripts/__pycache__/x.pyc",
                "exports/alipay.csv", "bill.xlsx", "old.zip", ".ledger.lock"):
        p = ledger / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    assert cli.main(["backup"]) == 0
    assert cli.main(["backup", "-o", str(ledger / "out")]) == 0
    names = _names(_only_zip(ledger / "out"))
    assert not [n for n in names if n.split("/")[1] in (".venv", "exports", "backups", "out")]
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


def _git(ledger, *args):
    subprocess.run(["git", *args], cwd=ledger, check=True, capture_output=True)


def _init_repo(ledger):
    _git(ledger, "init", "-q")
    _git(ledger, "config", "user.name", "记账助手")
    _git(ledger, "config", "user.email", "ledger@localhost")
    _git(ledger, "config", "commit.gpgsign", "false")
    _git(ledger, "config", "core.autocrlf", "false")
    _git(ledger, "add", "-A")
    _git(ledger, "commit", "-q", "-m", "chore: 初始化")
    _git(ledger, "gc", "-q")  # 整理后引用被打包，refs/heads 变成空目录


def test_账套是Git仓库时连提交历史一起打包(ledger, capsys, tmp_path_factory):
    _init_repo(ledger)
    assert cli.main(["backup"]) == 0
    out = capsys.readouterr().out
    assert "含 Git 历史：1 次提交" in out
    assert "[WARN]" not in out
    z = _only_zip(ledger / "backups")
    assert "ledger/.git/HEAD" in _names(z)
    # 解压出来仍是能接着用的仓库：历史在，工作区干净
    dest = tmp_path_factory.mktemp("restore")
    with zipfile.ZipFile(z) as f:
        f.extractall(dest)
    log = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=dest / "ledger", capture_output=True)
    assert log.returncode == 0 and log.stdout.strip() == b"1"
    status = subprocess.run(["git", "status", "--porcelain"], cwd=dest / "ledger", capture_output=True)
    assert status.stdout.strip() == b""


def test_有未提交改动时提醒先提交(ledger, capsys):
    _init_repo(ledger)
    (ledger / "CATEGORIES.md").write_text("改了规则", encoding="utf-8")
    assert cli.main(["backup"]) == 0
    out = capsys.readouterr().out
    assert "[WARN] 有 1 个文件的改动还没提交" in out


def test_不是Git仓库时照常打包(ledger, capsys):
    assert cli.main(["backup"]) == 0
    out = capsys.readouterr().out
    assert "含 Git 历史" not in out
    assert not [n for n in _names(_only_zip(ledger / "backups")) if "/.git/" in n]


def test_daily_今天备份过就跳过(ledger, capsys):
    assert cli.main(["backup", "--daily"]) == 0
    assert "[OK] 已备份" in capsys.readouterr().out
    assert cli.main(["backup", "--daily"]) == 0
    assert "今天已经备份过（ledger-backup-20260923-213000.zip）" in capsys.readouterr().out
    assert len(list((ledger / "backups").glob("*.zip"))) == 1


def test_daily_只有前几天的备份时照常打包(ledger, capsys):
    (ledger / "backups").mkdir()
    (ledger / "backups" / "ledger-backup-20260922-080000.zip").write_bytes(b"old")
    assert cli.main(["backup", "--daily"]) == 0
    assert "[OK] 已备份" in capsys.readouterr().out
    assert len(list((ledger / "backups").glob("*.zip"))) == 2


def test_不带daily时同一天可以再存(ledger, monkeypatch):
    from datetime import timedelta

    from conftest import FIXED_NOW
    from ledgerlib import entry

    assert cli.main(["backup"]) == 0
    monkeypatch.setattr(entry, "now_local", lambda: FIXED_NOW + timedelta(minutes=5))
    assert cli.main(["backup"]) == 0
    assert len(list((ledger / "backups").glob("*.zip"))) == 2


def test_默认目录只留最近三份(ledger):
    (ledger / "backups").mkdir()
    for day in ("19", "20", "21", "22"):
        (ledger / "backups" / f"ledger-backup-202609{day}-080000.zip").write_bytes(b"old")
    (ledger / "backups" / "别的文件.txt").write_text("留着", encoding="utf-8")
    assert cli.main(["backup"]) == 0
    names = sorted(p.name for p in (ledger / "backups").iterdir())
    assert names == ["ledger-backup-20260921-080000.zip", "ledger-backup-20260922-080000.zip",
                     "ledger-backup-20260923-213000.zip", "别的文件.txt"]


def test_指定目录时不清理旧备份(ledger):
    out = ledger / "out"
    out.mkdir()
    for day in ("19", "20", "21", "22"):
        (out / f"ledger-backup-202609{day}-080000.zip").write_bytes(b"old")
    assert cli.main(["backup", "-o", str(out)]) == 0
    assert len(list(out.glob("*.zip"))) == 5
