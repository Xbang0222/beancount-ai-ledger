"""跨账本往来对账：单边漏记必须被抓出来。"""
from ledgerlib import reconcile

# 只在 personal 侧记了代垫，shop 侧没记 —— beancount 单本账校验完全发现不了
ONE_SIDED = '''
2026-09-05 * "商店" "代垫商店采购款（股东往来）"
  time: "10:00"
  Assets:Receivable:Shop  250.00 CNY
  Assets:Wechat
'''

# 两侧都记，但金额录错一边
MISMATCHED_SHOP = '''
2026-09-05 * "供应商" "主营业务成本-采购"
  time: "10:00"
  Expenses:COGS  260.00 CNY
  Liabilities:OwnerLoan
'''


def _append(path, text):
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")


def test_镜像一致时通过(ledger, capsys):
    assert reconcile.cmd_reconcile() == 0
    assert "全部镜像一致" in capsys.readouterr().out


def test_单边漏记被检出(ledger, capsys):
    _append(ledger / "personal" / "journal" / "2026-09.beancount", ONE_SIDED)
    assert reconcile.cmd_reconcile() == 1
    out = capsys.readouterr().out
    assert "不一致" in out
    assert "250.00" in out


def test_两边金额不符被检出(ledger, capsys):
    _append(ledger / "personal" / "journal" / "2026-09.beancount", ONE_SIDED)
    _append(ledger / "shop" / "journal" / "2026-09.beancount", MISMATCHED_SHOP)
    assert reconcile.cmd_reconcile() == 1
    out = capsys.readouterr().out
    assert "不一致" in out
    assert "10.00" in out  # 260 - 250 的差额


def test_对账会列出最近触及的分录帮助定位(ledger, capsys):
    _append(ledger / "personal" / "journal" / "2026-09.beancount", ONE_SIDED)
    reconcile.cmd_reconcile()
    assert "代垫商店采购款（股东往来）" in capsys.readouterr().out


def test_账本有错时不出对账结论(ledger, capsys):
    _append(ledger / "personal" / "journal" / "2026-09.beancount",
            '\n2026-09-06 * "甲" "坏账"\n  Expenses:Food:Dining  1.00 CNY\n  Expenses:Other  1.00 CNY\n')
    assert reconcile.cmd_reconcile() == 1
    assert "无法对账" in capsys.readouterr().out


def test_没有镜像配置时直接通过(solo, capsys):
    assert reconcile.cmd_reconcile() == 0
    assert "没有需要对账的往来科目" in capsys.readouterr().out
