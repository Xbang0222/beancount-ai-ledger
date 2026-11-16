# 命令与配置

- 适用对象：用户与 AI。
- 内容：`ledger.py` 的常用命令，以及 `ledger.toml` 各配置段的写法。
- 完整的命令与参数以 `python3 scripts/ledger.py --help` 为准。

| 章节 | 内容 |
|---|---|
| [1 命令](#1-命令) | 常用命令一览、手动入账的写法 |
| [2 多本账](#2-多本账) | 新建账本、往来镜像、`ledger.toml` 的 `[ledger]`、`[books]`、`[[mirrors]]` |
| [3 利润分配](#3-利润分配) | `[dividend]` 与 `dividend` 命令的口径 |
| [4 周期事项](#4-周期事项) | `[[recurring]]` |
| [5 写法规则](#5-写法规则) | `[naming]` |
| [6 目录结构](#6-目录结构) | 仓库各文件的用途 |

## 1 命令

调用格式为 `python3 scripts/ledger.py <命令>`；加 `--root <目录>` 可操作其他目录中的账套。

| 命令 | 说明 |
|---|---|
| `doctor` | 检查依赖、各账本状态（含有余额但久未核对的账户）、提交前自动检查是否启用、Git 远程仓库是否私有 |
| `check [--no-reconcile]` | 校验全部账本；配置了往来镜像时同时对账 |
| `brief [账本]` | 输出入账所需的现场信息：当前日期与时间、`STATE.md` 中生效的内容、待补记的周期分录、可用科目及其中文说明与摘要开头、写法规则、最近的分录范例 |
| `lookup <关键词...>` | 按关键词检索规则文档与科目说明：输出命中的分类表行及表头、条款所在的文件与章节、科目表中的说明。用于归类或业务处理不确定时，可一次给出多个关键词 |
| `add <账本> [--file 文件]` | 从标准输入或文件写入一笔分录，校验失败时整笔回滚。分录用到账本之间的往来科目时拒绝入账并提示改用 `pair`；补平既有差额时加 `--one-sided` |
| `pair [--file 文件]` | 账本之间的往来在两本账同时登记：输入分两段，每段首行为 `[账本名]`，其下为该账本的一笔分录。任一边不合规或两边金额不符时，两本账均不改动 |
| `find <账本> <关键词...>` | 按关键词查找分录并显示编号；对方、摘要、科目、金额、标签均可检索 |
| `amend <账本> <编号> [--file 文件]` | 更正一笔：以新分录整笔替换，校验失败时自动还原 |
| `void <账本> <编号>` | 作废一笔：从序时簿删除 |
| `recent <账本> [-n N]` | 按发生时间列出最近 N 笔，默认 10 笔 |
| `summary <账本> [YYYY-MM]` | 按一级科目汇总支出与收入 |
| `report <账本> [YYYY-MM]` | 月度报告：收入、支出占比、结余与储蓄率；经营账为利润率 |
| `balances <账本>` | 科目余额表 |
| `tag <账本> <标签> [YYYY-MM]` | 按标签汇总明细 |
| `networth [--rate 代码=价格] [--offline]` | 合并资产负债：抵销账本之间的往来，外币、金银、基金、股票按联网取得的当日价格折合本位币；`[dividend]` 标注了 `owner` 时再扣除合伙人尚未分配的利润，给出扣后净资产 |
| `quote <代码...> [--date YYYY-MM-DD]` | 联网查询价格：`USD`、`USDT`、`AU`（每克）、`F161226`、`SH600519`、`HK00700`、`US.AAPL`；代码写法见 `rules/valuation.md` 第 2 节 |
| `reconcile` | 核对账本之间的往来 |
| `dividend YYYY-MM [--rate 币种=汇率] [--recalc]` | 按月利润分配：计算当月净利润，外币按联网取得的汇率折算，按 `[dividend]` 的比例拆分；月份结束后发放过分红的视为已结清，见[第 3 节](#3-利润分配) |
| `fmt [--check] [账本]` | 整理序时簿排版并按日期、时间排序，不改动金额 |
| `books` | 列出账本与往来镜像 |
| `rules [账本]` | 将 `[naming]` 的写法规则输出为对照表，见[第 5 节](#5-写法规则) |
| `new-book <名称> [选项]` | 新建账本，见[第 2 节](#2-多本账) |
| `commit-msg <文件>` / `commit-msg --range A..B` | 检查提交信息：前者由 `scripts/hooks/commit-msg` 钩子调用；后者逐条检查范围内已有的提交，可用于自建 CI。规范见 `docs/COMMITS.md` |
| `backup [-o 目录] [--daily]` | 将整个账套连同 Git 历史打包为一个压缩包，供没有远程仓库时存入云盘。`--daily` 在当日已备份时跳过；默认目录只保留最新一份 |

不经过 AI、手动入账的写法：

```bash
python3 scripts/ledger.py add personal <<'EOF'
2026-09-26 * "面馆" "餐饮-午餐"
  Expenses:Food:Dining  18.00 CNY
  Assets:Wechat
EOF
```

AA、代垫、信用卡还款、退款、押金、贷款、基金、外币等写法见 [`examples/cookbook.beancount`](../examples/cookbook.beancount)。

## 2 多本账

一本账对应一个会计主体。需要单独核算盈亏，或者资金不完全归本人所有（店铺、工作室、家庭共同账、活动经费）时，才需要新建账本。只统计某一事项的花费（例如一次旅行）时使用标签即可：`ledger.py tag personal chengdu`。

```bash
# 店铺账：经营科目模板，并与个人账建立往来
python3 scripts/ledger.py new-book shop --template business --title "我的小店" --link personal

# 家庭共同账：不并入个人净资产
python3 scripts/ledger.py new-book family --template minimal --title "家庭共同账" --no-consolidate
```

`--link personal` 在两本账各开立一对往来科目，并在 `ledger.toml` 中登记为镜像：

| 情形 | 个人账 | 店铺账 |
|---|---|---|
| 以个人账户为店铺付款 | `Assets:Receivable:Shop` | `Liabilities:OwnerLoan` |
| 店铺的款项进入个人账户 | `Liabilities:Shop` | `Assets:Receivable:Owner` |

每对镜像科目的余额合计应为 0。Beancount 只校验单本账内部的平衡，无法发现只登记一边的往来；因此 `add` 遇到往来科目时拒绝入账并提示使用 `pair`，`reconcile` 逐对核对，`networth` 合并时自动抵销。

`ledger.toml` 的完整写法：

```toml
[ledger]
timezone = "Asia/Shanghai"      # 注入 time、判断未来日期所用的时区
base_currency = "CNY"           # networth 折算的目标币种
reconcile_days = 35             # 可选：有余额的账户超过该天数未用 balance 核对时，doctor 给出提醒；默认 35，0 为不提醒

[books.personal]                # 账本名：小写字母开头
title = "个人账本"
kind = "personal"               # personal 的月度报告计算储蓄率；business 计算经营结余

[books.shop]
title = "我的小店"
kind = "business"
consolidate = true              # 是否并入 networth，默认 true
# main = "shop.beancount"       # 入口文件，默认 <账本名>.beancount
# journal = "shop/journal"      # 序时簿目录，默认 <账本名>/journal

[[mirrors]]                     # 一对往来镜像科目，两侧余额合计必须为 0
name = "personal 垫付 shop"
currency = "CNY"
accounts = { personal = "Assets:Receivable:Shop", shop = "Liabilities:OwnerLoan" }
```

键名拼写错误、引用不存在的账本、同一科目出现在多对镜像中，均直接报错。

## 3 利润分配

店铺与他人合伙、按月以净利润分配时，在 `ledger.toml` 中配置 `[dividend]`，每月初执行 `python3 scripts/ledger.py dividend 2026-10`：

```toml
[ledger]
fx_alias = { USDT = "USD" }     # 可选：取汇率时某币种按另一币种的汇率折算

[dividend]
book = "shop"                   # 计算利润的账本
# account = "Equity:Distributions"   # 登记已分配利润的科目；此为默认值，经营账模板已开立
partners = [
  { name = "我", payee = "股东", share = 0.6, owner = true },   # owner 可选：标注账本所有者本人
  { name = "合伙人小王", share = 0.4, offset = "Assets:Receivable:Wang" },
]
```

| 项目 | 口径 |
|---|---|
| 净利润 | 该月该账本的全部收入减全部支出。外币部分默认从开源数据集 fawazahmed0/exchange-api 取得当日汇率并折合本位币，汇率不写入账本；也可用 `--rate USD=7.1` 指定。无法取得汇率时报错并要求指定 |
| 已分配 | 分红分录须带 `period: "YYYY-MM"` 元数据，标明所属的利润月份。脚本按对方名称（`payee`，默认同 `name`）归集各方的已分配金额，列出「应得 − 已分配 = 差额」 |
| 结清 | 月份结束后登记过该月的分红分录（分录日期在次月或更晚）即视为该月已结清；再次执行只列示各方实发金额，不再取汇率重算，汇率变动与事后补记产生的差额不予补发。确需按补记后的账目重算时（例如漏记大额收入并已商定补差）加 `--recalc` |
| 月内预发 | 月内预发不构成结清：当时全月利润尚未确定，月份结束后仍按全月利润多退少补；补发，或将多发部分转为欠款的分录登记在月后，登记后方为结清 |
| 扣抵 | 配置了 `offset` 的一方，将该科目的余额（例如上月多发并记为对方欠款的部分）从差额中扣除，得出本次实付 |
| 扣后净资产 | 为账本所有者本人标注 `owner = true` 后，其余各方在未结清月份中「应得 − 已分配」的利润虽仍留在账本内，但不属于所有者。`networth` 在折合本位币的净资产之后单列「应付某某未分利润」，再给出「扣后净资产」；已发分红超过当前应得（预支）时反向加回。没有任何一方标注 `owner`，或分红账本不并入 `networth`（`consolidate = false`）时不扣除；利润中有币种无法取得价格时，说明该项未计入 |
| 比例 | `share` 合计必须为 1 |

分红分录的写法：

```beancount
2026-11-02 * "合伙人小王" "利润分配-10月分红"
  period: "2026-10"
  Equity:Distributions  4000.00 CNY
  Assets:Bank:Main
```

## 4 周期事项

按固定周期发生的业务（每周定投、每月房租、每月还贷）在 `ledger.toml` 中配置 `[[recurring]]`。`brief` 与 `doctor` 列出尚未登记的日期，`brief` 同时给出可直接提交的分录。脚本只提醒，不自动入账：扣款是否实际发生，脚本无从得知。

```toml
[[recurring]]
book = "personal"
name = "每月房租"
every = 5                    # "daily"、星期的英文（"monday"）或每月几号；当月没有该日时取月末
since = 2026-10-05           # 起算日期
match = "房租"               # 当日已有对方或摘要包含该词的交易时，视为已登记
confirm = true               # 可省略。false 表示已约定到期直接补记，不必先询问用户，适用于自动扣款
entry = '''
{date} * "房东" "居住-房租"
  Expenses:Housing:Rent  1800.00 CNY
  Assets:Bank:Main
'''
```

- `entry` 可省略；省略时只提醒，不给出分录。
- 一条规则最多列出最近 31 个漏记的日期。

## 5 写法规则

`ledger.toml` 的 `[naming]` 是对方与摘要写法的唯一来源，`ledger.py rules [账本]` 将其输出为对照表。配置后由 `add`、`pair`、`amend` 拦截不合规的分录，`check` 检查全部账目；整段删除即不做写法检查。

| 键 | 作用 |
|---|---|
| `markers` | 摘要括号内允许的固定标记；其他补充信息写入 `note:` |
| `banned_payees` / `vague_items` | 不得用作对方名称的空泛词 / 不得单独用作事项的笼统词 |
| `refund_suffix` | 费用冲回、收入冲减时摘要必须使用的结尾（「退款」「退回」） |
| `note_required` | 记入这些兜底科目时必须写 `note:` |
| `fallback` | 找不到分类时的处理步骤，`rules` 原样输出 |
| `[naming.prefix.<账本>]` | 科目前缀与摘要开头的对应关系；一笔分录有多个收支科目时按金额最大者确定。账本配置了该表后，新开的收支科目未配置摘要开头时 `check` 报错 |
| `[[naming.patterns]]` | 固定场景：分录出现 `when` 中的科目、其余科目均在 `with` 中时，对方只能为 `payee`，摘要只能以 `narration` 开头 |

`new-book` 建账时按所选模板自动追加该账本的 `[naming.prefix.<账本>]`。

## 6 目录结构

```text
.
├── ledger.toml              账套配置：账本、往来镜像、时区、本位币
├── personal.beancount       个人账入口，Fava 亦打开此文件
├── personal/
│   ├── accounts.beancount   科目表
│   ├── opening.beancount    期初余额
│   └── journal/             按月的序时簿，由 add 自动创建
├── common/                  币种声明、汇率与净值
├── AGENTS.md                AI 作业规程
├── CLAUDE.md, GEMINI.md     供 Claude Code、Gemini CLI 载入 AGENTS.md
├── rules/                   记账规则，按主题分文件；daily.md 为每次入账必读
├── STATE.md                 临时状态，例如进行中的行程
├── docs/GUIDE.md            使用指南
├── docs/AI-SETUP.md         供 AI 读取：第一次接手、账本存放、没有远程仓库时、首次使用、引导新手
├── docs/AI-TASKS.md         供 AI 读取：更正、余额核对、导入账单、升级等常见请求的处理
├── docs/COMMITS.md          提交信息规范
├── docs/DEVELOPMENT.md      开发规范：环境、模块职责、约束
├── examples/                分录范例与示例账本
├── scripts/                 ledger.py、bootstrap.py 及实现
└── tests/                   pytest 用例
```
