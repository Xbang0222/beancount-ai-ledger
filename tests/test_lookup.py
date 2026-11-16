"""lookup：按关键词检索规则文档与科目表。"""
from ledgerlib import cli, lookup, rulebook

DOC = """# 分类指南

## 5. 速查词典

### 5.1 按东西找

| 东西 | 科目 | 摘要开头 |
|---|---|---|
| 猫粮、猫砂 | `Expenses:Pet` | 宠物- |
| 奶茶、咖啡 | `Expenses:Food:Snack` | 餐饮- |

## 6. 退款

- 退款冲减原科目，摘要末尾加「退款」。

```
2026-09-01 * "宠物店" "宠物-猫粮退款"
```
"""


def test_表格行命中带出章节和表头():
    hits = lookup.scan("CLASSIFY.md", DOC, "猫粮")
    assert [(h.section, h.text, h.header) for h in hits] == [
        ("5.1 按东西找", "| 猫粮、猫砂 | `Expenses:Pet` | 宠物- |", "| 东西 | 科目 | 摘要开头 |")]


def test_条款命中给出行号_代码块里的示例不算():
    hits = lookup.scan("CLASSIFY.md", DOC, "退款")
    assert [(h.section, h.header) for h in hits] == [("6. 退款", None), ("6. 退款", None)]
    assert hits[0].text == "（本节标题命中，整节相关）"
    assert hits[1].lineno == 14 and hits[1].text.startswith("- 退款冲减原科目")


def test_检索不分大小写():
    assert lookup.scan("x.md", DOC, "expenses:pet")


def test_lookup_列出文档命中和科目说明(ledger, capsys):
    (ledger / "CLASSIFY.md").write_text(DOC, encoding="utf-8")
    assert cli.main(["lookup", "猫粮", "alipay"]) == 0
    out = capsys.readouterr().out
    assert "===== 猫粮 =====" in out and "CLASSIFY.md「5.1 按东西找」" in out
    assert "| 东西 | 科目 | 摘要开头 |" in out and "`Expenses:Pet`" in out
    assert "===== alipay =====" in out and "科目表" in out and "Assets:Alipay" in out


def test_lookup_未命中时说明下一步(ledger, capsys):
    assert cli.main(["lookup", "不存在的东西"]) == 0
    assert "未命中。换用通称、商家或平台名再查" in capsys.readouterr().out


def test_lookup_命中过多时只列前几条并说明其余在哪(ledger, capsys, monkeypatch):
    rows = "\n".join(f"| 零食{i} | `Expenses:Food:Snack` |" for i in range(5))
    (ledger / "CLASSIFY.md").write_text(f"## 表\n\n| 东西 | 科目 |\n|---|---|\n{rows}\n", encoding="utf-8")
    monkeypatch.setattr(lookup, "MAX_HITS", 3)
    assert cli.main(["lookup", "零食"]) == 0
    out = capsys.readouterr().out
    assert "零食2" in out and "零食3" not in out
    assert "另有 2 处命中未列出：CLASSIFY.md「表」" in out


def test_规则文档在_rules_目录时按主题文件检索_词典排前(ledger, capsys):
    rules = ledger / "rules"
    rules.mkdir()
    (rules / "tags.md").write_text("# 标签\n\n- 宠物相关支出不另设标签。\n", encoding="utf-8")
    (rules / "dictionary.md").write_text("# 词典\n\n| 东西 | 科目 |\n|---|---|\n| 宠物粮 | `Expenses:Pet` |\n",
                                         encoding="utf-8")
    (ledger / "CATEGORIES.md").write_text("# 旧规则\n\n- 宠物支出记 Pet。\n", encoding="utf-8")
    assert rulebook.files() == ["rules/dictionary.md", "rules/tags.md", "CATEGORIES.md"]
    assert cli.main(["lookup", "宠物"]) == 0
    out = capsys.readouterr().out
    assert out.index("rules/dictionary.md") < out.index("rules/tags.md") < out.index("CATEGORIES.md")


def test_提示里的文档路径随布局取(ledger):
    assert rulebook.ref("daily") == "CATEGORIES.md" and rulebook.ref("commits") == "AGENTS.md「每次改动后」"
    (ledger / "rules").mkdir()
    (ledger / "rules" / "daily.md").write_text("# 日常\n", encoding="utf-8")
    (ledger / "docs").mkdir()
    (ledger / "docs" / "COMMITS.md").write_text("# 提交\n", encoding="utf-8")
    assert rulebook.ref("daily") == "rules/daily.md" and rulebook.ref("books") == "rules/daily.md「账本与往来判定」"
    assert rulebook.ref("commits") == "docs/COMMITS.md"
