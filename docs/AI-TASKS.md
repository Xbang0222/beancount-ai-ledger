# 常见请求的处理

- 适用对象：AI。
- 读取时机：用户提出入账以外的请求时，按下表找到对应一节后读取。用户的常见表述另见 `docs/GUIDE.md`。
- 相关文档：入账流程与强制约束见 `AGENTS.md`；提交信息规范见 `docs/COMMITS.md`。

| 用户表述示例 | 章节 |
|---|---|
| 「刚才那笔不是花呗，是微信」「那笔记重了」 | 1 更正与删除 |
| 「对一下账：支付宝现在还剩 427」 | 2 余额核对 |
| 「这是支付宝导出的账单，帮我记进去」 | 3 导入账单 |
| 「我 10 月 1 号到 5 号去成都」 | 4 行程与临时状态 |
| 「以后奶茶单独算一类」 | 5 修改规则 |
| 「帮我升级记账项目」 | 6 升级工具 |
| 「我开了个网店，帮我建本店铺账」 | 7 新建账本 |
| 「这个月花了多少」「我有多少钱」 | 8 常用查询 |

## 1 更正与删除

先用 `find` 或 `recent` 定位分录，行首方括号内为分录编号：

```bash
python3 scripts/ledger.py find personal 打车 32        # 对方、摘要、科目、金额、标签均可检索
python3 scripts/ledger.py amend personal <编号> <<'EOF'
2026-09-26 * "网约车" "交通-打车"
  Expenses:Transport:Local  32.00 CNY
  Assets:Wechat
EOF
python3 scripts/ledger.py void personal <编号>          # 作废：删除该笔，例如重复登记
```

- `amend` 以新分录整笔替换原分录；新分录未写 `time` 时沿用原值。不支持 heredoc 的终端使用 `--file`，用法同 `add`。
- 编号由分录内容生成，更正后即变化；再次修改须重新 `find`。
- 往来分录须两本账同步处理（各自 `amend` / `void`），处理后执行 `reconcile` 确认每对镜像科目合计仍为 0。
- 提交信息使用 `fix: 更正<账本>…`，写明更正内容，规范见 `docs/COMMITS.md`。
- 不得以追加反向分录的方式修正录错的账目；反向分录仅用于真实发生的冲回，例如退款。

## 2 余额核对

使用 `add` 写入 `balance` 断言，日期写次日：`balance` 断言的是当日开始时的余额，用户报告的是当前余额，写次日才能包含当日已发生的交易。

```bash
python3 scripts/ledger.py add personal <<'EOF'
2026-09-27 balance Assets:Alipay  427.00 CNY
EOF
```

| 结果 | 处理 |
|---|---|
| 通过 | 告知用户余额相符，然后提交。断言保留在账本中，日后出现偏差时 `check` 会报告 |
| 未通过 | `add` 还原并报出差额。将差额告知用户，用 `recent` 列出相关账户的近期交易，协助查找漏记或记错的分录；补记或更正后再次核对 |

不得擅自以 `Equity:Adjustment` 调平。仅当用户确认无法查明原因并同意调整时，才登记一笔调整分录，摘要写明原因。

## 3 导入账单

- 导出文件只在本地读取，不得提交；`.gitignore` 已忽略 `*.csv`、`*.xlsx`。
- 导入前与用户确认：导入的时间范围；账单中各支付方式对应的账户；与已入账分录的去重方式，按日期、金额、对方比对序时簿。
- 仍须逐笔调用 `add`，可使用循环；不得直接写入序时簿。账单中的交易时间写入 `time` 行，该时间由用户提供，不属于估算。
- 账户之间的划转（充值、提现、信用卡还款、转入余额宝）不属于收支；退款冲减原支出。口径见 `rules/daily.md` 第 6、7 节与 `rules/dictionary.md` 第 3 节。
- 导入完成后执行 `check`，并向用户报告：导入笔数、跳过的重复笔数、无法判断而暂记 `Expenses:Other` 的笔数。

## 4 行程与临时状态

- 在 `STATE.md` 登记日期区间与默认标签，例如 `#trip #chengdu`。区间内发生的交易标注这些标签；按交易发生日判断，不按录入日判断。
- 用户告知行程结束，或区间已过时，从 `STATE.md` 删除该条并提交。

## 5 修改规则

- 长期规则写入 `rules/` 下对应主题的文件：结算账户与账本范围修改 `rules/daily.md`；分类修改 `rules/classification.md` 并同步 `rules/dictionary.md`；其余按 `AGENTS.md` 第 6 节的主题归入对应文件。
- 需要新科目时在 `accounts.beancount` 中开立。提交信息示例：`docs: 奶茶单独分类`。
- 已入账的历史分录是否随之调整，须先询问用户；不得自行批量修改历史账目。

## 6 升级工具

只替换脚本、测试和说明文档，不改动账本数据与用户自己的规则：

```bash
git remote add upstream https://github.com/Xbang0222/beancount-ai-ledger.git 2>/dev/null; git fetch -q upstream
git checkout upstream/main -- scripts tests docs AGENTS.md requirements.txt requirements-dev.txt pyproject.toml
python3 scripts/bootstrap.py && git commit -q -m "chore: 同步上游脚本"
```

- `rules/`、`STATE.md`、`ledger.toml` 和各账本目录属于用户数据，不得覆盖。用户修改过 `AGENTS.md` 的，先征得同意再覆盖。
- 旧布局账本（规则位于根目录的 `CATEGORIES.md`、`CLASSIFY.md`，没有 `rules/` 目录）升级后照常可用：这些文件不得覆盖或删除，新版 `AGENTS.md` 第 6.1 节给出了新旧文件的对应关系，`ledger.py lookup` 同样检索这些文件。
- 升级后重新读取 `AGENTS.md`，向用户报告升级到的版本（`CHANGELOG.md` 最上面一条）和最后一笔分录。

### 6.1 旧布局迁移

旧布局迁移为 `rules/` 布局属于可选操作，须先征得用户同意：

1. 取上游的规则文件：`git checkout upstream/main -- rules`。
2. 将用户在旧文件中修改过的内容逐项并入对应文件：结算账户对照表与账本范围并入 `rules/daily.md`；分类表并入 `rules/classification.md`；速查词典与判例并入 `rules/dictionary.md`、`rules/cases.md`；标签登记并入 `rules/tags.md`；自定的专题口径并入对应主题文件或新建文件。
3. 删除 `rules/daily.md` 开头的模板提示；将 `CLAUDE.md`、`GEMINI.md` 中的 `CATEGORIES.md` 引用改为 `rules/daily.md`；同步修改 `ledger.toml` 的 `[naming].fallback` 中的文件名。
4. 逐条核对旧文件的规则均已迁入后，删除根目录的旧规则文件，执行 `python3 scripts/ledger.py doctor` 与 `check`，以 `docs: 规则文档迁移至rules目录` 提交。

## 7 新建账本

- 使用 `new-book`：经营账加 `--template business`；需要与个人账相互垫付、代收的加 `--link personal`；与他人共有、不计入个人资产的（例如家庭共同账）加 `--no-consolidate`。
- 建立后在 `rules/daily.md` 第 2 节的账本范围表登记该账本的记账范围，然后提交。
- 加了 `--link` 的两本账之间的往来使用 `ledger.py pair` 同时登记，口径见 `rules/daily.md` 第 4 节。

## 8 常用查询

| 查询内容 | 命令 |
|---|---|
| 最近的分录 | `ledger.py recent personal [-n 20]` |
| 某一笔的位置与记法 | `ledger.py find personal 超市 128` |
| 当月支出金额与构成 | `ledger.py summary personal 2026-09` |
| 月度报告：收入、支出占比、储蓄率 | `ledger.py report personal 2026-09` |
| 各账户余额 | `ledger.py balances personal` |
| 某次旅行、某项事务的总花费 | `ledger.py tag personal trip` |
| 总资产、净资产：多本账合并，外币、金银、基金、股票按现价折算 | `ledger.py networth` |
| 汇率、金价、基金净值、股价 | `ledger.py quote USD AU F161226 SH600519` |
| 账本之间的往来是否相符 | `ledger.py reconcile` |

- `networth` 联网取得外币、金银、基金、股票的当日价格并折算为本位币；回报时说明所用价格与数据时间。
- 单独查询价格使用 `ledger.py quote <代码>`，代码写法见 `rules/valuation.md` 第 2 节。
- 养老保险、医保个人账户标注了 `networth: FALSE`，不计入净资产。
