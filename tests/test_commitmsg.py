"""提交信息检查：首行 `type: 摘要`，不带括号；改了账本要用对类型、动词开头、写明账本。"""
import shutil
import subprocess

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


def _diff(path, *heads):
    """构造统一差异：heads 中以 + 或 - 开头的交易首行。"""
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n" + "\n".join(heads) + "\n"


def test_按差异统计各账本净新增的交易笔数():
    diff = (_diff(P[0], '+2026-10-28 * "食堂" "餐饮-午餐"', "+  Expenses:Food:Dining  5.00 CNY",
                  '+2026-10-28 * "充电桩" "交通-电瓶车充电"')
            + _diff(S[0], '-2026-10-27 * "客户" "营业收入"', '+2026-10-27 * "客户" "营业收入"'))
    assert commitmsg.added_entries(diff, BOOKS) == {"personal": 2, "shop": 0}


@pytest.mark.parametrize("message,added,bad", [
    ("feat: 登记个人账10月28日午餐支出5.00元与电瓶车充电1.28元", {"personal": 2}, True),
    ("feat: 登记个人账10月28日午餐支出5.00元，工行付款", {"personal": 1}, False),
    ("feat: 登记个人账与商店账10月28日代收营业款200.00元，微信收款", {"personal": 1, "shop": 1}, False),
    ("fix: 更正个人账共3笔餐饮摘要，金额不变", {"personal": 0}, False),
    ("feat: 补记个人账10月26日至28日基金定投", {"personal": 3}, False),
])
def test_登记的提交一本账只能新增一笔(message, added, bad):
    files = P + (S if "shop" in added else [])
    msgs = commitmsg.problems(message, files, BOOKS, added)
    assert any("只提交一笔" in m for m in msgs) is bad


def test_钩子命令读文件并按暂存区判断(ledger, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(commitmsg, "_staged_files", lambda: S)
    good, bad = tmp_path / "good", tmp_path / "bad"
    good.write_text("feat: 登记测试商店账10月28日营业收入100.00元，建行入账\n", encoding="utf-8")
    bad.write_text("feat: 登记个人账营业收入100.00元\n", encoding="utf-8")
    assert cli.main(["commit-msg", str(good)]) == 0
    assert cli.main(["commit-msg", str(bad)]) == 1
    assert "测试商店账" in capsys.readouterr().err


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   check=True, capture_output=True)


@pytest.mark.skipif(not shutil.which("git"), reason="需要 git")
def test_按范围逐条检查已有提交(ledger, monkeypatch, capsys):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(ledger.parent))
    _git(ledger, "init", "-q")
    _git(ledger, "add", "-A")
    _git(ledger, "commit", "-q", "-m", "feat: 初始化测试个人账与测试商店账")
    journal = ledger / "shop" / "journal" / "2026-09.beancount"
    journal.write_text(journal.read_text(encoding="utf-8") + "\n; 备注\n", encoding="utf-8")
    _git(ledger, "commit", "-qam", "fix: 更正测试商店账9月采购备注")
    assert cli.main(["commit-msg", "--range", "HEAD~1..HEAD"]) == 0
    assert "1 条提交信息合规" in capsys.readouterr().out

    journal.write_text(journal.read_text(encoding="utf-8") + "; 再备注\n", encoding="utf-8")
    _git(ledger, "commit", "-qam", "fix: 营业收入改为零点口径(time 00:00)")
    assert cli.main(["commit-msg", "--range", "HEAD~2..HEAD"]) == 1
    err = capsys.readouterr().err
    assert "零点口径" in err and "括号" in err and "测试商店账" in err
    assert "更正测试商店账9月采购备注" not in err   # 合规的那条不报


@pytest.mark.skipif(not shutil.which("git"), reason="需要 git")
def test_范围取不到时只查最新一条(ledger, monkeypatch, capsys):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(ledger.parent))
    _git(ledger, "init", "-q")
    _git(ledger, "add", "-A")
    _git(ledger, "commit", "-q", "-m", "feat: 初始化测试个人账与测试商店账")
    zeros = "0" * 40
    assert cli.main(["commit-msg", "--range", f"{zeros}..HEAD"]) == 0
    assert "只检查最新一条" in capsys.readouterr().out


def test_既没给文件也没给范围时报错(ledger, capsys):
    assert cli.main(["commit-msg"]) == 1
    assert "--range" in capsys.readouterr().out
