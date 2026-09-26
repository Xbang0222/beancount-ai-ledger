"""测试脚手架：每个用例在 tmp_path 里搭一套临时账套，全程不碰真实账本。

- ledger：个人 + 商店两本账，带一对往来镜像（覆盖多账本与对账）；
- solo：只有一本个人账、没有任何镜像（覆盖“只记个人账”的用户）。
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

# 固定“此刻”，让未来日期/时间的校验与 time 注入可重复
FIXED_NOW = datetime(2026, 9, 23, 21, 30, tzinfo=timezone(timedelta(hours=8)))

CONFIG_TWO_BOOKS = """\
[ledger]
timezone = "Asia/Shanghai"
base_currency = "CNY"

[books.personal]
title = "测试个人账"

[books.shop]
title = "测试商店账"
kind = "business"

[[mirrors]]
name = "个人垫付商店款"
currency = "CNY"
accounts = { personal = "Assets:Receivable:Shop", shop = "Liabilities:OwnerLoan" }

[[mirrors]]
name = "个人代收商店款"
currency = "CNY"
accounts = { personal = "Liabilities:Shop", shop = "Assets:Receivable:Owner" }
"""

CONFIG_SOLO = """\
[books.personal]
title = "测试个人账"
"""

PERSONAL_ACCOUNTS = """\
2026-08-31 open Assets:Alipay CNY
2026-08-31 open Assets:Wechat CNY
2026-08-31 open Assets:Bank:USD USD
2026-08-31 open Assets:Receivable:Shop CNY
2026-08-31 open Liabilities:Shop CNY
2026-08-31 open Liabilities:CreditCard CNY
2026-08-31 open Expenses:Food:Dining CNY
2026-08-31 open Expenses:Other CNY
2026-08-31 open Income:Other CNY, USD
2026-08-31 open Equity:OpeningBalances
"""

SHOP_ACCOUNTS = """\
2026-08-31 open Assets:Bank:Main CNY
2026-08-31 open Assets:Receivable:Owner CNY
2026-08-31 open Liabilities:OwnerLoan CNY
2026-08-31 open Expenses:COGS CNY
2026-08-31 open Income:Revenue CNY
2026-08-31 open Equity:OpeningBalances
"""

PERSONAL_JOURNAL = """\
; 测试个人账 · 2026-09 流水

2026-09-02 * "食堂" "餐饮-午餐"
  time: "12:30"
  Expenses:Food:Dining  20.00 CNY
  Assets:Alipay

2026-09-01 * "商店" "代垫商店采购款（股东往来）"
  time: "09:00"
  Assets:Receivable:Shop  100.00 CNY
  Assets:Wechat
"""

SHOP_JOURNAL = """\
; 测试商店账 · 2026-09 流水

2026-09-01 * "供应商" "主营业务成本-采购"
  time: "09:00"
  Expenses:COGS  100.00 CNY
  Liabilities:OwnerLoan
"""


def _entry(title, includes):
    lines = [f'option "title" "{title}"', 'option "operating_currency" "CNY"', ""]
    lines += [f'include "{i}"' for i in includes]
    return "\n".join(lines) + "\n"


def _write_book(root, name, title, accounts, journal):
    (root / name / "journal").mkdir(parents=True)
    (root / name / "accounts.beancount").write_text(accounts, encoding="utf-8")
    (root / name / "journal" / "2026-09.beancount").write_text(journal, encoding="utf-8")
    (root / f"{name}.beancount").write_text(
        _entry(title, [f"{name}/accounts.beancount", f"{name}/journal/2026-09.beancount"]),
        encoding="utf-8")


@pytest.fixture
def fixed_now(monkeypatch):
    from ledgerlib import entry

    monkeypatch.setattr(entry, "now_local", lambda: FIXED_NOW)
    return FIXED_NOW


@pytest.fixture
def ledger(tmp_path, monkeypatch, fixed_now):
    """个人 + 商店两本账的临时账套，并把 config.ROOT 指过去。"""
    from ledgerlib import config

    (tmp_path / "ledger.toml").write_text(CONFIG_TWO_BOOKS, encoding="utf-8")
    _write_book(tmp_path, "personal", "测试个人账", PERSONAL_ACCOUNTS, PERSONAL_JOURNAL)
    _write_book(tmp_path, "shop", "测试商店账", SHOP_ACCOUNTS, SHOP_JOURNAL)
    monkeypatch.setattr(config, "ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture
def solo(tmp_path, monkeypatch, fixed_now):
    """只有一本个人账、没有往来镜像的临时账套。"""
    from ledgerlib import config

    (tmp_path / "ledger.toml").write_text(CONFIG_SOLO, encoding="utf-8")
    accounts = "\n".join(l for l in PERSONAL_ACCOUNTS.splitlines() if "Shop" not in l) + "\n"
    journal = PERSONAL_JOURNAL.split("2026-09-01")[0].rstrip() + "\n"
    _write_book(tmp_path, "personal", "测试个人账", accounts, journal)
    monkeypatch.setattr(config, "ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture
def empty_root(tmp_path, monkeypatch, fixed_now):
    """空目录：用来测试从零 new-book。"""
    from ledgerlib import config

    monkeypatch.setattr(config, "ROOT", str(tmp_path))
    return tmp_path
