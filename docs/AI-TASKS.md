# AI 作业须知 · 常见请求

面向 AI。入账以外的请求，按用户的表述找到对应一节后读取；用户的常见表述见 `docs/GUIDE.md`。

| 用户说 | 读哪一节 |
|---|---|
| "刚才那笔不是花呗，是微信"、"那笔记重了" | 更正与删除 |
| "对一下账：支付宝现在还剩 427" | 余额核对 |
| "这是支付宝导出的账单，帮我记进去" | 导入账单 |
| "我 10 月 1 号到 5 号去成都" | 行程与临时状态 |
| "以后奶茶单独算一类" | 修改规则 |
| "帮我升级记账项目" | 升级工具 |
| "我开了个网店，帮我建本店铺账" | 新建账本 |
| "这个月花了多少"、"我有多少钱" | 常用查询 |

## 更正与删除（"刚才那笔不是花呗，是微信"）

先用 `find` 或 `recent` 找到那一笔，行首方括号里是它的编号：

```bash
python3 scripts/ledger.py find personal 打车 32        # 对方、摘要、科目、金额、标签都能搜
python3 scripts/ledger.py amend personal <编号> <<'EOF'
2026-09-26 * "网约车" "交通-打车"
  Expenses:Transport:Local  32.00 CNY
  Assets:Wechat
EOF
python3 scripts/ledger.py void personal <编号>          # 作废：删除这一笔，比如记重了
```

- `amend` 用新分录整笔替换原来那笔，新分录没写 `time` 就沿用原来的。没有 heredoc 的终端用 `--file`，同 `add`。
- 编号取自分录内容，改过一次就变了，接着再改要重新 `find`。
- 往来分录要两本账一起改（各自 `amend` / `void`），改完跑 `reconcile` 确认每对镜像科目仍相加为 0。
- 提交用 `fix: 更正<账本>…`（写法见 `AGENTS.md` 第三步），写清改了什么。不要用"再记一笔反向分录"修正录错的账；反向分录只用于真实发生的冲回，比如退款。

## 余额核对（"对一下账：支付宝现在还剩 427"）

用 `add` 写 `balance` 断言，日期写**明天**：balance 断言的是"当天开始时"的余额，用户报的是此刻的余额，写明天才包含今天已发生的交易。

```bash
python3 scripts/ledger.py add personal <<'EOF'
2026-09-27 balance Assets:Alipay  427.00 CNY
EOF
```

- 通过：告诉用户对上了，然后提交。断言留在账里，以后再出偏差 `check` 会发现。
- 不通过：`add` 会回滚并报出差额。把差额告诉用户，用 `recent` 列出相关账户的近期交易，帮用户找漏记或记错的那笔；找到后补记或更正，再核对一次。**不得擅自用 `Equity:Adjustment` 找平**；只有用户确认找不到原因、同意调整时，才记一笔调整分录，摘要写明原因。

## 导入账单（"这是支付宝导出的账单，帮我记进去"）

- 导出文件只在本地读，不要提交（`.gitignore` 已忽略 `*.csv`、`*.xlsx`）。
- 先和用户确认：导入哪段时间，账单里的支付方式各对应哪个账户，和已经记过的账怎么去重（按日期、金额、对方比对序时簿）。
- 仍然逐笔调用 `add`，可以写循环；不要直接写序时簿。账单里的交易时间写进 `time` 行，这是用户提供的数据，不算估时间。
- 账户之间的划转（充值、提现、还信用卡、转入余额宝）不是收支；退款冲减原支出（`rules/daily.md` 第 5 至 7 节）。
- 导完跑 `check`，告诉用户导入了几笔、跳过了几笔重复、几笔拿不准暂记在 `Expenses:Other`。

## 行程与临时状态（"我 10 月 1 号到 5 号去成都"）

- 写进 `STATE.md`：日期区间和默认标签（如 `#trip #chengdu`）。区间内发生的交易带上这些标签，按交易发生日判断，不按录入日。
- 用户说回来了，或者区间已经过去，就从 `STATE.md` 删掉并提交。

## 修改规则（"以后奶茶单独算一类"）

- 长期规则写入 `rules/` 下对应主题的文件：结算账户、账本范围改 `rules/daily.md`，分类改 `rules/classification.md` 并同步 `rules/dictionary.md`，其余按 `AGENTS.md` 第 6 节的主题；需要新科目时在 `accounts.beancount` 里开立。提交信息如 `docs: 奶茶单独分类`。
- 以前已经记了的分录要不要跟着改，先问用户，不要自作主张批量改历史账。

## 升级工具（"帮我升级记账项目"）

只替换脚本、测试和说明文档，账本数据和用户自己的规则不动：

```bash
git remote add upstream https://github.com/Xbang0222/beancount-ai-ledger.git 2>/dev/null; git fetch -q upstream
git checkout upstream/main -- scripts tests docs AGENTS.md requirements.txt requirements-dev.txt pyproject.toml
python3 scripts/bootstrap.py && git commit -q -m "chore: 同步上游脚本"
```

- `rules/`、`STATE.md`、`ledger.toml` 和各账本目录属于用户数据，不得覆盖。用户改过 `AGENTS.md` 的，先征得同意再覆盖。
- 旧布局账本（规则在根目录的 `CATEGORIES.md`、`CLASSIFY.md`，没有 `rules/` 目录）升级后照常可用：这些文件不得覆盖或删除，新版 `AGENTS.md` 第 6.1 节给出了新旧文件的对应关系，`ledger.py lookup` 同样检索它们。
- 升级后重读 `AGENTS.md`，向用户报告升级到的版本（`CHANGELOG.md` 最上面一条）和最后一笔分录。

旧布局迁移为 `rules/` 布局属于可选操作，须先征得用户同意：

1. 取上游的规则文件：`git checkout upstream/main -- rules`。
2. 将用户在旧文件中修改过的内容逐项并入对应文件：结算账户对照表与账本范围并入 `rules/daily.md`，分类表并入 `rules/classification.md`，速查词典与判例并入 `rules/dictionary.md`、`rules/cases.md`，标签登记并入 `rules/tags.md`，自定的专题口径并入对应主题文件或新建文件。
3. 删除 `rules/daily.md` 开头的模板提示；将 `CLAUDE.md`、`GEMINI.md` 中的 `CATEGORIES.md` 引用改为 `rules/daily.md`；`ledger.toml` 的 `[naming].fallback` 中的文件名同步修改。
4. 逐条核对旧文件的规则均已迁入后，删除根目录的旧规则文件，执行 `python3 scripts/ledger.py doctor` 与 `check`，以 `docs: 规则文档迁移至rules目录` 提交。

## 新建账本（"我开了个网店，帮我建本店铺账"）

- 用 `new-book`：经营账加 `--template business`；要和个人账互相垫付、代收的加 `--link personal`；与他人共有、不算个人资产的（如家庭共同账）加 `--no-consolidate`。
- 建好后在 `rules/daily.md` 第 2 节的账本范围表登记这本账的记账范围，然后提交。加了 `--link` 的两本账之间的往来用 `ledger.py pair` 两边一起录（`rules/daily.md` 第 4 节）。

## 常用查询

| 想知道 | 命令 |
|---|---|
| 最近记了什么 | `ledger.py recent personal [-n 20]` |
| 某一笔记在哪、记成了什么 | `ledger.py find personal 超市 128` |
| 这个月花了多少、花在哪 | `ledger.py summary personal 2026-09` |
| 月度报告（收入、支出占比、储蓄率） | `ledger.py report personal 2026-09` |
| 每个账户还剩多少 | `ledger.py balances personal` |
| 某次旅行、某件事总共花了多少 | `ledger.py tag personal trip` |
| 总资产、净资产（多本账合并、外币金银基金股票按现价折算） | `ledger.py networth` |
| 美元、金价、基金净值、股价现在多少 | `ledger.py quote USD AU F161226 SH600519` |
| 账本之间的往来对不对得上 | `ledger.py reconcile` |

`networth` 会自动现拉外币、金银、基金、股票的当天价格折成本位币，回报时说明用的价格和数据时间；单独查价用 `ledger.py quote <代码>`（写法见 `rules/valuation.md` 第 2 节）。养老金、医保个人账户标了 `networth: FALSE`，不算进净资产。
