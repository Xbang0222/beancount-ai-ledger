# AI 记账作业须知

这是一套 **beancount 纯文本复式账套**，不是普通代码仓库：每次改动改的都是用户的真实账目。
动手前请把下面这些当作硬约束。

> 本文件给 Codex 等读取 `AGENTS.md` 的 AI 使用；Claude Code 通过 `CLAUDE.md` 引用本文件，内容以这里为准。

## 开始前

1. 先 `git pull --ff-only` 同步远程，避免多设备同时记账产生冲突。
2. 看账套里有哪些账本：`python3 scripts/ledger.py books`（配置在 `ledger.toml`）。只有一本 `personal` 时不存在"记哪本账"的问题。
3. 读 **`CATEGORIES.md`**：分类与核算口径的唯一依据，包括付款渠道对应哪个账户、科目怎么归类、摘要怎么写、往来和标签怎么处理、时间戳规则。
4. 读 **`STATE.md`**：当前生效的临时上下文，比如进行中的行程和它的默认标签、临时的默认付款账户。事项结束后删掉。
5. `CATEGORIES.md` 和 `STATE.md` 冲突时以 `CATEGORIES.md` 为准。稳定规则只写进 CATEGORIES，易变上下文只写进 STATE，两者不混放。
6. 缺依赖（报 `ModuleNotFoundError: beancount`）时，运行 `bash scripts/setup.sh`，或 `pip install -r requirements.txt`。

## 入账硬规矩

- **只能通过 `ledger.py add` 入账，不要手动编辑序时簿**（`<账本>/journal/*.beancount`）。脚本会自动注入时间戳、追加 include、跑平衡校验，校验不通过整笔回滚。手改会绕过这些保护。唯一的例外是更正已入账的分录，见下文「更正与删除」。

  ```bash
  printf '%s' '<分录>' | python3 scripts/ledger.py add personal   # personal 换成 ledger.toml 里的账本名
  ```

- **不许估时间。** 用户没报具体时间就不写 `time` 行，由脚本注入录入时刻；"7 点半"这类分不清上下午的先问。手写的 time 晚于当前时间会被 `add` 拒绝，交易日期晚于今天也会被拒绝。
- **一次只录一笔。** 多笔分多次提交，脚本检测到多笔会直接拒绝。
- **账本之间的往来必须两边都记。** 两本账之间的资金往来是双边镜像登记，beancount 只校验单本账内部平衡，**只记一边它发现不了**。`add` 碰到往来科目时会打印 `[提示]`，告诉你另一边该记到哪本账的哪个科目。两边记完跑 `python3 scripts/ledger.py reconcile`，确认每对镜像科目仍然相加为 0。
- **不确定上一笔记没记上**时，先 `python3 scripts/ledger.py recent <账本>` 看最近几笔，再决定是否重录，避免重复入账。
- **科目未开立**时 `add` 会失败回滚。不要自造科目名硬记。先对照 `<账本>/accounts.beancount` 选一个已有科目；确实需要新科目，就按原格式在 accounts 里 `open`，带上中文注释，和这笔分录一起提交，并在回复里告诉用户新开了什么科目。
- **分类不确定时不要硬猜**。只有"确定是消费、只是不知道归哪类"才暂记 `Expenses:Other`，并在回复里说明；连是消费、借款还是代垫都分不清时，先问用户，**不得直接记成费用**。

## 每次改动后

```bash
python3 scripts/ledger.py check          # 全部账本校验（有往来镜像时连带对账），必须通过
python3 -m pytest tests/ -q              # 改了 scripts/ 才需要
```

然后 `git status` 过一遍变更清单再提交。提交信息遵循 Conventional Commits（`type(scope): 摘要`）：

- `type`：`feat` 记新账，`fix` 更正账目，`docs` 改规则或文档，`refactor` / `test` / `chore` 用于脚本与杂务；
- `scope`：账本名（如 `personal`、`shop`），或 `script` / `docs`；
- 示例：`feat(personal): 餐饮-午餐 18 元`，`fix(personal): 打车改记花呗`，`docs: 新增宠物支出分类`。

**每次改动后立即提交**；配置了远程仓库就立即推送，账本以远程为准。

## 回报用户

入账后用一句话回报**一级大类、金额、结算账户、所打标签**，用户一句话就能纠正。
对用户说话可以口语化，但写进账本的 payee 和摘要一律用书面会计语言（规范见 `CATEGORIES.md` 0.1）。

## 常见请求的处理办法

用户能说的话，`docs/GUIDE.md` 里列了一遍。下面是几类不是"记一笔"的请求，处理办法固定如下。

### 首次使用（"帮我初始化账本"）

1. 缺什么问什么：有哪些账户（银行卡、支付宝、微信、现金、信用卡、花呗等）、从哪天开始记、各账户那天的余额、没说付款方式时默认用哪个账户。
2. 改 `personal/accounts.beancount`：按真实账户增删、改名（如 `Assets:Bank:Main` 改成 `Assets:Bank:CMB`），用不到的删掉。
3. 在 `personal/opening.beancount` 登记期初：开账日前一天写 `pad`，开账日写 `balance`，负债写负数。
4. 同步改 `CATEGORIES.md` 第 0 节的对照表和默认付款账户。
5. `check` 通过后提交，提交信息如 `chore(personal): 初始化账户与期初余额`。

### 更正与删除（"刚才那笔不是花呗，是微信"）

- 更正已入账的分录，是唯一允许直接编辑序时簿的情形。先用 `recent` 或搜索定位到那一笔，只改需要改的字段，`time` 等元数据保留；删除重复的就删掉整个分录块。
- 改完必须跑 `check` 并通过。往来分录要两本账一起改，改完跑 `reconcile`。
- 提交用 `fix(<账本>): …`，写清改了什么。不要用"再记一笔反向分录"的办法修正录错的账；反向分录只用于真实发生的冲回，比如退款。

### 余额核对（"对一下账：支付宝现在还剩 427"）

- 用 `add` 写 `balance` 断言：`printf '%s' '<明天的日期> balance Assets:Alipay  427.00 CNY' | python3 scripts/ledger.py add personal`。balance 断言的是"当天开始时"的余额，用户报的是此刻余额，所以日期写**明天**，这样今天已发生的交易都算在内。
- 通过：告诉用户对上了，然后提交。断言留在账里，以后再出偏差会被 `check` 发现。
- 不通过：`add` 会回滚并报出差额。把差额告诉用户，用 `recent` 列出相关账户的近期交易，帮用户回忆漏记或记错的那笔；找到后补记或更正，再核对一次。**不得擅自用 `Equity:Adjustment` 找平**；只有用户确认找不到原因、同意调整时，才记一笔调整分录，摘要写明原因。

### 行程与临时状态（"我 10 月 1 号到 5 号去成都"）

- 写进 `STATE.md`：日期区间、默认标签（如 `#trip #chengdu`）。区间内发生的交易带上这些标签，按交易发生日判断，不按录入日。
- 用户说回来了，或者区间已经过去，就从 `STATE.md` 删掉并提交。

### 修改规则（"以后奶茶单独算一类"）

- 长期规则改 `CATEGORIES.md`，需要新科目时在 `accounts.beancount` 里开立，提交信息如 `docs: 奶茶单独分类`。
- 以前已经记了的分录要不要跟着改，先问用户，不要自作主张批量改历史账。

### 新建账本（"我开了个网店，帮我建本店铺账"）

- 用 `new-book`：经营账加 `--template business`；要和个人账互相垫付或代收的加 `--link personal`；与他人共有、不算个人资产的（如家庭共同账）加 `--no-consolidate`。
- 建好后在 `CATEGORIES.md` 第 3 节写清这本账记什么，然后提交。

## 常用查询

| 想知道 | 命令 |
|---|---|
| 最近记了什么 | `ledger.py recent personal [-n 20]` |
| 这个月花了多少、花在哪 | `ledger.py summary personal 2026-09` |
| 月度报告（收入、支出占比、储蓄率） | `ledger.py report personal 2026-09` |
| 每个账户还剩多少 | `ledger.py balances personal` |
| 某次旅行 / 某件事总共花了多少 | `ledger.py tag personal trip` |
| 总资产、净资产（多本账合并、外币折算） | `ledger.py networth` |
| 账本之间的往来对不对得上 | `ledger.py reconcile` |

算总资产前，按 `CATEGORIES.md` 第 5 节先更新当天汇率和净值。

## 隐私

账本是用户的隐私数据。不要把账本内容、余额、交易明细发给任何外部服务（搜索引擎、粘贴站、第三方 API），除非用户明确要求。

## 改脚本时

- 实现在 `scripts/ledgerlib/`，`scripts/ledger.py` 只是入口转发。已有命令的用法不要随意改，用户和规则文档都依赖它们。
- 代码里不写死任何账本名。账本、往来镜像、时区、本位币一律从 `ledger.toml` 读取（`ledgerlib/config.py`）。
- 新增或修改逻辑要配套 `tests/` 用例。测试用 `conftest.py` 的 `ledger`（两本账）、`solo`（只有个人账）、`empty_root`（空目录）fixture 在 tmp_path 搭临时账套，**不要让测试碰真实账本**。
- 改了查询类命令，要拿改动前的 `balances` / `report` 输出比对，确认口径没有意外变化。
