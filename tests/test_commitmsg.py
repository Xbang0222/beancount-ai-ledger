"""提交信息检查：首行 `type: 摘要`，不带括号；改了账本要用对类型、动词开头、写明账本。"""
import pytest

from ledgerlib import cli, commitmsg
from ledgerlib.config import Book

BOOKS = [
    Book("personal", "个人账本", "personal", "personal.beancount", "personal/journal", True),
    Book("shop", "商店账本", "business", "shop.beancount", "shop/journal", True),
]
P, S = ["personal/journal/2026-10.beancount"], ["shop/journal/2026-10.beancount"]


@pytest.mark.parametrize("title,label", [("个人账本", "个人账"), ("我的小店", "我的小店")])
def test_账本称呼取自标题(title, label):
    assert commitmsg.book_label(Book("x", title, "personal", "x.beancount", "x/journal", True)) == label


@pytest.mark.parametrize("files,names", [
    (P, ["personal"]),
    (S + P, ["personal", "shop"]),
    (["shop.beancount"], ["shop"]),
    (["personal/accounts.beancount", "scripts/ledgerlib/naming.py"], ["personal"]),
    (["README.md", "ledger.toml", "scripts/ledgerlib/cli.py"], []),
])
def test_按改动文件判断账本(files, names):
    assert [b.name for b in commitmsg.touched_books(files, BOOKS)] == names


@pytest.mark.parametrize("message,files", [
    ("feat: 登记个人账10月28日晚餐支出30.00元，支付宝付款", P),
    ("feat: 登记个人账与商店账10月28日代收营业款200.00元，微信收款", P + S),
    ("feat: 补记商店账10月26日至28日币安定投及预付摊销", S),
    ("fix: 更正个人账10月25日京东退款，改记开账前资产收回", P),
    ("fix: 作废商店账10月27日重复登记的营业收入1844.92元", S),
    ("fix: 对账调整个人账兴业银行差额0.60元，计入利息支出", P),
    ("style: 重排个人账与商店账9月序时簿，余额不变", P + S),
    ("feat: 新开个人账利息收入科目", ["personal/accounts.beancount"]),
    ("feat: 初始化个人账", ["personal.beancount", "personal/opening.beancount"]),
    ("feat: 新增提交信息检查钩子\n\n- 正文可以有（括号）\n\nCo-Authored-By: x <y@z>", ["scripts/ledgerlib/a.py"]),
    ("chore: 更新USDT汇率为6.7069", ["common/prices.beancount"]),
    ("Merge branch 'main'", P),
    ("# 注释行不算\nfeat: 登记个人账10月28日午餐支出18.00元，微信付款", P),
    ("fix: 只改提交信息", []),  # --amend 不改文件时不核对账本
])
def test_合规提交信息通过(message, files):
    assert commitmsg.problems(message, files, BOOKS) == []


@pytest.mark.parametrize("message,files,expect", [
    ("记了一笔晚餐", P, "格式"),
    ("feat：登记个人账晚餐", P, "格式"),
    ("feat(personal): 登记个人账晚餐", P, "格式"),
    ("update: 登记个人账晚餐", P, "不认识"),
    ("feat: 登记个人账晚餐支出30.00元（支付宝）", P, "不用括号"),
    ("feat: 晚餐支出30.00元，个人账", P, "开头"),
    ("feat: 登记10月28日晚餐支出30.00元", P, "缺「个人账」"),
    ("feat: 登记个人账10月28日代收营业款200.00元", P + S, "缺「商店账」"),
    ("docs: 更正个人账分类表", P, "类型只能是"),
    ("feat: 登记个人账" + "长" * 80, P, "超过"),
])
def test_不合规提交信息被拒(message, files, expect):
    msgs = commitmsg.problems(message, files, BOOKS)
    assert msgs and any(expect in m for m in msgs)


def test_钩子命令读文件并按暂存区判断(ledger, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(commitmsg, "_staged_files", lambda: S)
    good, bad = tmp_path / "good", tmp_path / "bad"
    good.write_text("feat: 登记测试商店账10月28日营业收入100.00元，建行入账\n", encoding="utf-8")
    bad.write_text("feat: 登记个人账营业收入100.00元\n", encoding="utf-8")
    assert cli.main(["commit-msg", str(good)]) == 0
    assert cli.main(["commit-msg", str(bad)]) == 1
    assert "测试商店账" in capsys.readouterr().err
