"""新建账本：从零生成可用账套；关联账本自动建往来与镜像；失败必须整体还原。"""
from ledgerlib import cli, config, newbook


def _snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_空目录从零生成个人账并通过校验(empty_root, capsys):
    assert newbook.cmd_new_book("personal") == 0
    for rel in ("ledger.toml", "personal.beancount", "personal/accounts.beancount",
                "personal/opening.beancount", "common/commodities.beancount", "common/prices.beancount"):
        assert (empty_root / rel).exists(), rel
    assert (empty_root / "personal" / "journal").is_dir()
    cfg = config.load()
    assert list(cfg.books) == ["personal"] and cfg.books["personal"].kind == "personal"
    assert cli.main(["check"]) == 0


def test_生成的科目表可以直接记账(empty_root):
    import io

    from ledgerlib import add

    assert newbook.cmd_new_book("personal") == 0
    block = '2026-09-23 * "面馆" "餐饮-午餐"\n  Expenses:Food:Dining  18.00 CNY\n  Assets:Wechat'
    assert add.cmd_add("personal", stream=io.StringIO(block)) == 0


def test_关联账本生成往来科目与镜像并通过对账(empty_root, capsys):
    assert newbook.cmd_new_book("personal") == 0
    assert newbook.cmd_new_book("shop", template="business", title="商店账本", link="personal") == 0
    cfg = config.load()
    assert cfg.books["shop"].kind == "business"
    assert [m.sides() for m in cfg.mirrors] == [
        (("personal", "Assets:Receivable:Shop"), ("shop", "Liabilities:OwnerLoan")),
        (("personal", "Liabilities:Shop"), ("shop", "Assets:Receivable:Owner")),
    ]
    personal_accounts = (empty_root / "personal" / "accounts.beancount").read_text(encoding="utf-8")
    assert "open Assets:Receivable:Shop CNY" in personal_accounts
    assert "open Liabilities:Shop CNY" in personal_accounts
    capsys.readouterr()
    assert cli.main(["check"]) == 0
    assert "全部镜像一致" in capsys.readouterr().out


def test_账本名转科目名片段():
    assert newbook.camel("shop") == "Shop"
    assert newbook.camel("my-shop") == "MyShop"
    assert newbook.camel("travel_fund2") == "TravelFund2"


def test_在已有账套里追加账本(ledger):
    assert newbook.cmd_new_book("family", template="minimal", title="家庭共同账", link="personal") == 0
    cfg = config.load()
    assert list(cfg.books) == ["personal", "shop", "family"]
    assert len(cfg.mirrors) == 4
    assert cli.main(["check"]) == 0


def test_开户日期可指定(empty_root):
    assert newbook.cmd_new_book("personal", open_date="2026-01-01") == 0
    text = (empty_root / "personal" / "accounts.beancount").read_text(encoding="utf-8")
    assert "2026-01-01 open Assets:Cash CNY" in text
    assert "1970-01-01" not in text


def test_已存在的账本不覆盖(ledger, capsys):
    before = _snapshot(ledger)
    assert newbook.cmd_new_book("shop") == 1
    assert _snapshot(ledger) == before
    assert "已经有账本 shop" in capsys.readouterr().out


def test_同名文件或目录已存在时不覆盖(ledger):
    (ledger / "notes").mkdir()
    before = _snapshot(ledger)
    assert newbook.cmd_new_book("notes") == 1
    assert _snapshot(ledger) == before


def test_非法账本名被拒(empty_root):
    assert newbook.cmd_new_book("Shop") == 1
    assert newbook.cmd_new_book("1shop") == 1
    assert list(empty_root.iterdir()) == []


def test_关联不存在的账本被拒且不留文件(ledger):
    before = _snapshot(ledger)
    assert newbook.cmd_new_book("studio", link="nobody") == 1
    assert _snapshot(ledger) == before


def test_校验失败时整体还原(ledger, monkeypatch, capsys):
    """模拟新账本校验不过：新建的文件要删掉，被追加的 ledger.toml 与对方科目表要原样还原。"""
    before = _snapshot(ledger)
    real_load = newbook.load_book

    def flaky(book):
        entries, errors, options = real_load(book)
        return (entries, ["模拟的校验错误"], options) if book == "studio" else (entries, errors, options)

    monkeypatch.setattr(newbook, "load_book", flaky)
    assert newbook.cmd_new_book("studio", template="business", link="personal") == 1
    assert _snapshot(ledger) == before
    assert not (ledger / "studio").exists()
    assert "已还原全部改动" in capsys.readouterr().out
