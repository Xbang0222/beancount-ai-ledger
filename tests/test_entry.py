"""分录文本预处理：time 注入、未来时间守卫、include 识别、多笔守卫、月份校验。"""
import pytest

from ledgerlib import entry

from conftest import FIXED_NOW as FIXED


def test_注入_time_到交易首行之后():
    block = '2026-09-23 * "食堂" "餐饮-午餐"\n  Expenses:Food:Dining  20.00 CNY\n  Assets:Alipay'
    out = entry.inject_time(block, now=FIXED).split("\n")
    assert out[1] == '  time: "21:30"'
    assert out[0].startswith("2026-09-23")


def test_补记历史账同样注入_time():
    """口径统一为“所有交易都带 time”，补记的旧账不留空。"""
    block = '2026-01-05 * "食堂" "餐饮-午餐"\n  Expenses:Food:Dining  20.00 CNY\n  Assets:Alipay'
    assert '  time: "21:30"' in entry.inject_time(block, now=FIXED)


def test_已有_time_不覆盖():
    block = '2026-09-23 * "基金公司" "指数基金定投"\n  time: "09:40"\n  Assets:Alipay  50.00 CNY\n  Assets:Wechat'
    assert entry.inject_time(block, now=FIXED) == block


def test_块首有注释时_time_不插错位置():
    """固定插在第 2 行的话，块首带注释会把 time 插进注释和交易行之间导致语法错误。"""
    block = '; 补记：对账发现遗漏\n2026-09-23 * "食堂" "餐饮-午餐"\n  Expenses:Food:Dining  20.00 CNY\n  Assets:Alipay'
    out = entry.inject_time(block, now=FIXED).split("\n")
    assert out[0].startswith(";")
    assert out[1].startswith("2026-09-23")
    assert out[2] == '  time: "21:30"'


@pytest.mark.parametrize("block, bad", [
    ('2026-09-24 * "甲" "明天的账"\n  Expenses:Other  1.00 CNY\n  Assets:Alipay', "晚于今天"),
    ('2027-09-23 * "甲" "年份写错"\n  Expenses:Other  1.00 CNY\n  Assets:Alipay', "晚于今天"),
    ('2026-09-23 * "甲" "估的时间"\n  time: "23:10"\n  Expenses:Other  1.00 CNY\n  Assets:Alipay', "不要估"),
])
def test_未来日期或时间被拒(block, bad):
    assert bad in entry.future_error(block, now=FIXED)


@pytest.mark.parametrize("block", [
    '2026-09-23 * "甲" "今天早上"\n  time: "08:00"\n  Expenses:Other  1.00 CNY\n  Assets:Alipay',
    '2026-09-22 * "甲" "昨晚"\n  time: "23:10"\n  Expenses:Other  1.00 CNY\n  Assets:Alipay',
    '2026-09-23 * "甲" "没写时间"\n  Expenses:Other  1.00 CNY\n  Assets:Alipay',
    '2026-12-31 price USD 7.10 CNY',  # 非交易指令不管日期
])
def test_合理的日期时间放行(block):
    assert entry.future_error(block, now=FIXED) is None


@pytest.mark.parametrize("flag", ["*", "!", "txn"])
def test_多笔守卫识别三种交易写法(flag):
    one = f'2026-09-23 {flag} "甲" "摘要"\n  Expenses:Other  1.00 CNY\n  Assets:Alipay'
    two = one + f'\n2026-09-23 {flag} "乙" "摘要"\n  Expenses:Other  1.00 CNY\n  Assets:Alipay'
    assert entry.count_transactions(one) == 1
    assert entry.count_transactions(two) == 2


def test_first_date():
    assert entry.first_date('2026-09-23 * "甲" "摘要"') == ("2026", "09")
    assert entry.first_date("没有日期") is None


@pytest.mark.parametrize("comment", [";", "//", "#"])
def test_被注释的_include_不算生效(comment):
    rel = "personal/journal/2026-10.beancount"
    text = f'include "personal/accounts.beancount"\n{comment} include "{rel}"\n'
    assert entry.has_active_include(text, rel) is False


def test_有效_include_被识别():
    rel = "personal/journal/2026-10.beancount"
    assert entry.has_active_include(f'include "{rel}"\n', rel) is True


def test_往来科目按整词匹配():
    block = '2026-09-23 * "甲" "摘要"\n  Assets:Receivable:ShopHK  1.00 HKD\n  Assets:Alipay'
    assert entry.touched_accounts(block, ["Assets:Receivable:Shop"]) == []
    assert entry.touched_accounts(block, ["Assets:Receivable:ShopHK"]) == ["Assets:Receivable:ShopHK"]


@pytest.mark.parametrize("bad", ["2026-13", "2026-00", "202609", "2026-9", "", None, "九月"])
def test_非法月份被拒(bad):
    with pytest.raises(ValueError):
        entry.parse_ym(bad)


def test_合法月份通过():
    assert entry.parse_ym("2026-09") == "2026-09"
    assert entry.parse_ym("2026-12") == "2026-12"
