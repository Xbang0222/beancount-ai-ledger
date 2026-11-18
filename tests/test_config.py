"""ledger.toml 解析：写错的配置要大声报错，而不是悄悄关掉对账。"""
import pytest

from ledgerlib import config
from ledgerlib.config import ConfigError, parse

BASE = {"books": {"personal": {}}}


def _with(**extra):
    data = {"books": {"personal": {}, "shop": {"kind": "business"}}}
    data.update(extra)
    return data


def _mirror(**kw):
    m = {"name": "个人垫付商店款", "currency": "CNY",
         "accounts": {"personal": "Assets:Receivable:Shop", "shop": "Liabilities:OwnerLoan"}}
    m.update(kw)
    return m


def test_最小配置取默认值():
    cfg = parse(BASE)
    book = cfg.books["personal"]
    assert (book.title, book.kind, book.main, book.journal, book.consolidate) == (
        "personal", "personal", "personal.beancount", "personal/journal", True)
    assert cfg.timezone == "Asia/Shanghai"
    assert cfg.base_currency == "CNY"
    assert cfg.mirrors == ()


def test_账本保持书写顺序():
    cfg = parse({"books": {"shop": {}, "personal": {}, "family": {}}})
    assert list(cfg.books) == ["shop", "personal", "family"]


def test_镜像按书写顺序解析两侧():
    m = parse(_with(mirrors=[_mirror()])).mirrors[0]
    assert m.sides() == (("personal", "Assets:Receivable:Shop"), ("shop", "Liabilities:OwnerLoan"))


@pytest.mark.parametrize("data, hint", [
    ({}, "至少要声明一个账本"),
    ({"books": {}}, "至少要声明一个账本"),
    ({"books": {"Personal": {}}}, "账本名"),
    ({"books": {"personal": {"kind": "company"}}}, "kind"),
    ({"books": {"personal": {"kinds": "business"}}}, "不认识的键"),
    ({"books": {"personal": {"consolidate": "yes"}}}, "consolidate"),
    ({"books": {"personal": {"main": "/abs/path.beancount"}}}, "相对"),
    ({"books": {"personal": {}}, "mirror": []}, "不认识的键"),
    ({"books": {"personal": {}}, "ledger": {"timezone": "Mars/Base"}}, "timezone"),
    ({"books": {"personal": {}}, "ledger": {"base_currency": "rmb"}}, "base_currency"),
    ({"books": {"personal": {}}, "ledger": {"reconcile_days": -1}}, "reconcile_days"),
    ({"books": {"personal": {}}, "ledger": {"reconcile_days": True}}, "reconcile_days"),
    ({"books": {"personal": {}}, "ledger": {"tz": "Asia/Shanghai"}}, "不认识的键"),
])
def test_写错的配置被拒(data, hint):
    with pytest.raises(ConfigError, match=hint):
        parse(data)


@pytest.mark.parametrize("mirror, hint", [
    (_mirror(name=""), "缺少 name"),
    (_mirror(currency="cny"), "currency"),
    (_mirror(accounts={"personal": "Assets:Receivable:Shop"}), "恰好写两本账"),
    (_mirror(accounts={"personal": "Assets:Receivable:Shop", "family": "Liabilities:OwnerLoan"}), "未声明的账本"),
    (_mirror(accounts={"personal": "Receivable:Shop", "shop": "Liabilities:OwnerLoan"}), "科目名不合法"),
    (_mirror(note="x"), "不认识的键"),
])
def test_写错的镜像被拒(mirror, hint):
    with pytest.raises(ConfigError, match=hint):
        parse(_with(mirrors=[mirror]))


def test_同一科目重复出现在多个镜像被拒():
    with pytest.raises(ConfigError, match="重复"):
        parse(_with(mirrors=[_mirror(), _mirror(name="另一对")]))


def test_找不到配置文件时提示如何生成(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", str(tmp_path))
    with pytest.raises(ConfigError, match="new-book"):
        config.load()


def test_不是合法_TOML_时报错(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", str(tmp_path))
    (tmp_path / "ledger.toml").write_text("[books.personal\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="TOML"):
        config.load()


def test_未知账本名列出可选项(ledger):
    with pytest.raises(ConfigError, match="personal / shop"):
        config.get_book("family")


def _recurring(**kw):
    r = {"book": "shop", "name": "每周定投", "every": "monday", "since": "2026-09-07", "match": "定投"}
    r.update(kw)
    return r


def test_周期事项三种周期都能解析():
    from datetime import date

    cfg = parse(_with(recurring=[_recurring(), _recurring(every="daily", since=date(2026, 9, 1)),
                                 _recurring(every=31, entry="\n{date} * \"房东\" \"居住-房租\"\n")]))
    weekly, daily, monthly = cfg.recurring
    assert (weekly.kind, weekly.day, weekly.since) == ("weekly", 0, date(2026, 9, 7))
    assert (daily.kind, daily.since) == ("daily", date(2026, 9, 1))
    assert (monthly.kind, monthly.day) == ("monthly", 31)
    assert monthly.entry == '{date} * "房东" "居住-房租"'
    assert weekly.confirm is True
    assert parse(_with(recurring=[_recurring(confirm=False)])).recurring[0].confirm is False
    assert parse(BASE).recurring == ()


def test_周期事项支持工作日与休市日():
    from datetime import date

    skip = [date(2026, 10, 1), date(2026, 10, 2)]
    rule = parse(_with(recurring=[_recurring(every="weekday", skip=skip)])).recurring[0]
    assert rule.kind == "weekday"
    assert rule.skip == frozenset({date(2026, 10, 1), date(2026, 10, 2)})
    assert parse(_with(recurring=[_recurring()])).recurring[0].skip == frozenset()


@pytest.mark.parametrize("kw, expect", [
    ({"book": "nope"}, "已声明的账本"),
    ({"every": "everyday"}, "every 写"),
    ({"every": 0}, "every 写"),
    ({"every": True}, "every 写"),
    ({"since": "9月7日"}, "since 写起算日期"),
    ({"match": ""}, "match 写"),
    ({"name": ""}, "缺少 name"),
    ({"confirm": "no"}, "confirm 写"),
    ({"times": 3}, "不认识的键"),
    ({"skip": "2026-10-01"}, "skip"),
    ({"skip": ["国庆"]}, "skip"),
])
def test_周期事项写错时报错(kw, expect):
    with pytest.raises(ConfigError, match=expect):
        parse(_with(recurring=[_recurring(**kw)]))
