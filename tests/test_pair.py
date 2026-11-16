"""往来两边一起录：要么两本账都记上，要么都不动。"""
import io

from ledgerlib import pair

PERSONAL = '2026-09-23 * "商店" "代垫商店采购款（股东往来）"\n  Assets:Receivable:Shop  50.00 CNY\n  Assets:Wechat'
SHOP = '2026-09-23 * "某供应商" "主营业务成本-采购"\n  Expenses:COGS  50.00 CNY\n  Liabilities:OwnerLoan'


def _pair(personal=PERSONAL, shop=SHOP, **kw):
    return pair.cmd_pair(stream=io.StringIO(f"[personal]\n{personal}\n[shop]\n{shop}\n"), **kw)


def _bytes(root):
    return {b: (root / b / "journal" / "2026-09.beancount").read_bytes() for b in ("personal", "shop")}


def _text(root, book):
    return (root / book / "journal" / "2026-09.beancount").read_text(encoding="utf-8")


def test_两本账一起入账且_time_相同(ledger, capsys):
    assert _pair() == 0
    assert "两本账已一起入账" in capsys.readouterr().out
    for book, mark in (("personal", "代垫商店采购款（股东往来）"), ("shop", "某供应商")):
        tail = _text(ledger, book).split("2026-09-23")[1]
        assert mark in tail and '  time: "21:30"' in tail


def test_入账后镜像仍然一致(ledger):
    from ledgerlib.reconcile import cmd_reconcile

    assert _pair() == 0
    assert cmd_reconcile() == 0


def test_一边校验不过两本账都不动(ledger, capsys):
    before = _bytes(ledger)
    assert _pair(shop=SHOP.replace("Expenses:COGS", "Expenses:NotOpened")) == 1
    assert _bytes(ledger) == before
    assert "已回滚" in capsys.readouterr().out


def test_一边写法不合规两本账都不动(ledger, capsys):
    before = _bytes(ledger)
    assert _pair(personal=PERSONAL.replace("2026-09-23", "2026-09-30")) == 1  # 未来日期
    assert _bytes(ledger) == before
    assert "[personal] 这一段" in capsys.readouterr().out


def test_两边金额对不上被拒并回滚(ledger, capsys):
    before = _bytes(ledger)
    assert _pair(shop=SHOP.replace("50.00", "5.00")) == 1
    assert _bytes(ledger) == before
    out = capsys.readouterr().out
    assert "往来金额对不上" in out and "相差 45.00" in out


def test_两边同方向被拒(ledger, capsys):
    before = _bytes(ledger)
    wrong = '2026-09-23 * "股东" "归还股东往来款"\n  Liabilities:OwnerLoan  50.00 CNY\n  Assets:Bank:Main'
    assert _pair(shop=wrong) == 1
    assert _bytes(ledger) == before
    assert "往来金额对不上" in capsys.readouterr().out


def test_有一段没用到往来科目被拒(ledger, capsys):
    before = _bytes(ledger)
    plain = '2026-09-23 * "某供应商" "主营业务成本-采购"\n  Expenses:COGS  50.00 CNY\n  Assets:Bank:Main'
    assert _pair(shop=plain) == 1
    assert _bytes(ledger) == before
    assert "不是往来分录" in capsys.readouterr().out


def test_重复入账被拒并回滚(ledger, capsys):
    assert _pair() == 0
    before = _bytes(ledger)
    assert _pair() == 1
    assert _bytes(ledger) == before
    assert "疑似重复入账" in capsys.readouterr().out
    assert _pair(allow_duplicate=True) == 0


def test_段落不是恰好两本不同的账被拒(ledger, capsys):
    before = _bytes(ledger)
    assert pair.cmd_pair(stream=io.StringIO(f"[personal]\n{PERSONAL}\n")) == 1
    assert pair.cmd_pair(stream=io.StringIO(f"[personal]\n{PERSONAL}\n[personal]\n{PERSONAL}\n")) == 1
    assert pair.cmd_pair(stream=io.StringIO(PERSONAL)) == 1
    assert _bytes(ledger) == before
    assert "恰好两段" in capsys.readouterr().out


def test_整段带缩进贴进来也能录(ledger):
    indented = "\n".join("  " + line for line in f"[personal]\n{PERSONAL}\n[shop]\n{SHOP}".split("\n"))
    assert pair.cmd_pair(stream=io.StringIO(indented)) == 0


def test_一段里塞了两笔被拒(ledger):
    before = _bytes(ledger)
    assert _pair(personal=PERSONAL + "\n\n" + PERSONAL) == 1
    assert _bytes(ledger) == before


def test_命令行入口(ledger, monkeypatch):
    from ledgerlib import cli

    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(
        f"[personal]\n{PERSONAL}\n[shop]\n{SHOP}\n".encode())))
    assert cli.main(["pair"]) == 0
    assert "某供应商" in _text(ledger, "shop")
