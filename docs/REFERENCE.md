# 命令与配置

- [命令](#命令)
- [多本账](#多本账)
- [利润分配](#利润分配)
- [目录结构](#目录结构)

## 命令

完整的命令和参数以 `python3 scripts/ledger.py --help` 为准，这里列常用的。格式为 `python3 scripts/ledger.py <命令>`，加 `--root <目录>` 可以操作其他目录里的账套。

| 命令 | 说明 |
|---|---|
| `doctor` | 检查依赖、各账本状态，以及 Git 远程仓库是否私有 |
| `check [--no-reconcile]` | 校验全部账本，有往来镜像时连带对账 |
| `add <账本> [--file 文件]` | 从标准输入或文件写入一笔分录，校验失败整笔回滚 |
| `find <账本> <关键词...>` | 按关键词找分录并显示编号，对方、摘要、科目、金额、标签都能搜 |
| `amend <账本> <编号> [--file 文件]` | 更正一笔：用新分录整笔替换，校验失败自动还原 |
| `void <账本> <编号>` | 作废一笔：从序时簿删除 |
| `recent <账本> [-n N]` | 按发生时间列出最近 N 笔，默认 10 笔 |
| `summary <账本> [YYYY-MM]` | 按一级科目汇总支出和收入 |
| `report <账本> [YYYY-MM]` | 月报：收入、支出占比、结余与储蓄率（经营账为利润率） |
| `balances <账本>` | 科目余额表 |
| `tag <账本> <标签> [YYYY-MM]` | 按标签汇总明细 |
| `networth [--rate 代码=价格] [--offline]` | 合并资产负债：抵销账本之间的往来，外币、金银、基金、股票现拉当天价格折合本位币 |
| `quote <代码...> [--date YYYY-MM-DD]` | 现拉价格：`USD`、`USDT`、`AU`（每克）、`F161226`、`SH600519`、`HK00700`、`US.AAPL`，写法见 CATEGORIES 第 5 节 |
| `reconcile` | 核对账本之间的往来 |
| `dividend YYYY-MM [--rate 币种=汇率]` | 按月利润分配：算当月净利润（外币现拉汇率折算），按 `[dividend]` 比例拆分，见[利润分配](#利润分配) |
| `fmt [--check] [账本]` | 整理序时簿格式、按日期时间排序，不改金额 |
| `books` | 列出账本与往来镜像 |
| `new-book <名称> [选项]` | 新建账本，见[多本账](#多本账) |
| `backup [-o 目录] [--daily]` | 把整个账套连同 Git 历史打成一个压缩包，没有远程仓库时存到云盘、网盘。`--daily` 今天备份过就跳过；默认目录只留最新一份 |

不经过 AI、手动入账时这样写：

```bash
python3 scripts/ledger.py add personal <<'EOF'
2026-09-26 * "面馆" "餐饮-午餐"
  Expenses:Food:Dining  18.00 CNY
  Assets:Wechat
EOF
```

AA、代垫、信用卡还款、退款、押金、贷款、基金、外币等写法见 [`examples/cookbook.beancount`](../examples/cookbook.beancount)。

## 多本账

一本账对应一个会计主体。需要单独核算盈亏，或者钱不全归你（店铺、工作室、家庭共同账、活动经费）时，才需要新建账本。只想统计一件事花了多少，比如一次旅行，打标签就够了：`ledger.py tag personal chengdu`。

```bash
# 店铺账：经营科目模板，并与个人账建立往来
python3 scripts/ledger.py new-book shop --template business --title "我的小店" --link personal

# 家庭共同账：不并入个人净资产
python3 scripts/ledger.py new-book family --template minimal --title "家庭共同账" --no-consolidate
```

`--link personal` 会在两本账各开一对往来科目，并在 `ledger.toml` 里登记为镜像：

| 情形 | 个人账 | 店铺账 |
|---|---|---|
| 用个人账户替店里付款 | `Assets:Receivable:Shop` | `Liabilities:OwnerLoan` |
| 店里的钱进了个人账户 | `Liabilities:Shop` | `Assets:Receivable:Owner` |

每对镜像科目的余额相加应当为 0。Beancount 只校验单本账内部平衡，只记了一边它发现不了，所以 `add` 碰到往来科目会提示另一边该记在哪，`reconcile` 逐对核对，`networth` 合并时自动抵销。

`ledger.toml` 的完整写法：

```toml
[ledger]
timezone = "Asia/Shanghai"      # 注入 time、判断未来日期都按这个时区
base_currency = "CNY"           # networth 折算的目标币种

[books.personal]                # 账本名：小写字母开头
title = "个人账本"
kind = "personal"               # personal 月报算储蓄率；business 月报看经营结余

[books.shop]
title = "我的小店"
kind = "business"
consolidate = true              # 是否并入 networth，默认 true
# main = "shop.beancount"       # 入口文件，默认 <账本名>.beancount
# journal = "shop/journal"      # 序时簿目录，默认 <账本名>/journal

[[mirrors]]                     # 一对往来镜像科目，两侧余额相加必须为 0
name = "personal 垫付 shop"
currency = "CNY"
accounts = { personal = "Assets:Receivable:Shop", shop = "Liabilities:OwnerLoan" }
```

键名拼错、引用了不存在的账本、同一个科目出现在多对镜像里，都会直接报错。

## 利润分配

店铺和别人合伙、每月按净利润分钱时，在 `ledger.toml` 里配置 `[dividend]`，每月初跑 `python3 scripts/ledger.py dividend 2026-10`：

```toml
[ledger]
fx_alias = { USDT = "USD" }     # 可选：现拉汇率时某币种按另一币种的汇率折算

[dividend]
book = "shop"                   # 在哪本账上算
# account = "Equity:Distributions"   # 记已分配利润的科目（默认，经营账模板已开立）
partners = [
  { name = "我", payee = "股东", share = 0.6 },
  { name = "合伙人小王", share = 0.4, offset = "Assets:Receivable:Wang" },
]
```

- **净利润**：该月这本账全部收入减全部支出。外币部分默认从开源数据集 fawazahmed0/exchange-api 现拉当天汇率折成本位币（不写入账本），也可以用 `--rate USD=7.1` 指定；拉不到会报错让你指定。
- **已分配**：分红分录要带 `period: "YYYY-MM"` 元数据标明属于哪个月的利润，脚本按对方名称（`payee`，默认同 `name`）归集各方已分了多少，列出「应得 − 已分配 = 差额」。发完分红后又补记了当月收支，再跑一次就能看出要补多少。
- **扣抵**：配了 `offset` 的一方，把该科目余额（比如上个月多发、记成对方欠款的部分）从差额里扣掉，得出本次实付。
- `share` 合计必须为 1。

分红分录这样写：

```beancount
2026-11-02 * "合伙人小王" "利润分配-10月分红"
  period: "2026-10"
  Equity:Distributions  4000.00 CNY
  Assets:Bank:Main
```

## 写法规则

`ledger.toml` 的 `[naming]` 是对方与摘要写法的唯一来源，`ledger.py rules [账本]` 把它打印成对照表。配了就由 `add` / `amend` 拦截、`check` 扫全账；整段删掉就不做写法检查。

| 键 | 作用 |
|---|---|
| `markers` | 摘要括号里允许的固定标记，其他补充写进 `note:` |
| `banned_payees` / `vague_items` | 不能当对方名称的空泛词 / 不能单独当事项的笼统词 |
| `refund_suffix` | 费用冲回、收入冲减时摘要必须的结尾（「退款」「退回」） |
| `note_required` | 记到这些兜底科目必须写 `note:` |
| `fallback` | 找不到分类时的处理步骤，`rules` 原样打印 |
| `[naming.prefix.<账本>]` | 科目前缀 → 摘要开头；一笔有几个收支科目按金额最大的那个定。账本配了这张表，新开的收支科目没配开头 `check` 会报错 |
| `[[naming.patterns]]` | 固定场景：分录出现 `when` 里的科目、其余科目都在 `with` 里时，对方只能是 `payee`，摘要只能以 `narration` 开头 |

`new-book` 建账时会按所选模板自动追加这本账的 `[naming.prefix.<账本>]`。

## 目录结构

```text
.
├── ledger.toml              账套配置：账本、往来镜像、时区、本位币
├── personal.beancount       个人账入口（Fava 也打开这个文件）
├── personal/
│   ├── accounts.beancount   科目表
│   ├── opening.beancount    期初余额
│   └── journal/             按月的序时簿，由 add 自动创建
├── common/                  币种声明、汇率与净值
├── AGENTS.md                给 AI 的操作规范
├── CLAUDE.md, GEMINI.md     让 Claude Code、Gemini CLI 载入 AGENTS.md
├── CATEGORIES.md            分类与核算规则
├── STATE.md                 临时状态，如进行中的行程
├── docs/GUIDE.md            使用指南
├── examples/                分录范例与示例账本
├── scripts/                 ledger.py、bootstrap.py 及实现
└── tests/                   pytest 用例
```
