# AGENTS.md

本仓库是一套 [Beancount](https://github.com/beancount/beancount) 纯文本复式账本，不是普通代码仓库。
用户让你记的、改的都是他的真实账目，下面的规则是硬约束。记一笔账按三步走。

Windows 上把命令里的 `python3` 换成 `python` 或 `py`。

## 第一步：看现场

```bash
git pull --ff-only                    # 配置了远程仓库才跑，避免多台设备同时记账产生冲突
python3 scripts/ledger.py brief       # 入账前要知道的都在这一条命令里
```

`brief` 一次列出：**今天几号星期几、现在几点**；`STATE.md` 里当前生效的临时情况（进行中的行程和它的默认标签、临时的默认付款账户）；**该补的周期分录**（配了 `[[recurring]]` 才有）；每本账**能用的科目**（只能用列出来的）；对方与摘要的写法；最近几笔当范例。

- 命令退出码为 3 是缺依赖：运行 `python3 scripts/bootstrap.py` 后重试。不要加 `--break-system-packages` 往系统 Python 里装包。
- 第一次接手这个仓库，或 `brief` 报账本有错：运行 `python3 scripts/ledger.py doctor`，按 `docs/AI-SETUP.md`「第一次接手」处理它列出的问题。
- **没有远程仓库**（用户不会用 Git，如豆包云电脑）：见下面「没有远程仓库时」，每次开始先自检、报最后一笔。
- 「该补的周期分录」有内容，按它的提示处理（有的要先问用户，有的直接补），再记用户说的那笔。
- 「当前临时状态」里生效的默认标签、默认付款账户，写分录时一并套用。
- 然后读 **`CATEGORIES.md`**：日常入账的全部规则（付款渠道对应哪个账户、科目怎么归类、摘要怎么写、往来和标签怎么处理、时间戳）。
- 其余文档遇到才读，见下面「按情况查阅」。

## 第二步：写分录，用命令入账

只能通过命令入账，一次一笔。分录用 heredoc 从标准输入传入：

```bash
python3 scripts/ledger.py add personal <<'EOF'
2026-09-26 * "面馆" "餐饮-午餐"
  Expenses:Food:Dining  18.00 CNY
  Assets:Wechat
EOF
```

- `personal` 换成 `ledger.toml` 里的账本名（`brief` 会列出有哪些账本；只有一本 `personal` 时不存在记哪本账的问题）。标签写在首行末尾，如 `"餐饮-午餐" #trip #chengdu`。
- 没有 heredoc 的终端（如 Windows PowerShell）：先把分录写进 UTF-8 编码的 `entry.tmp`（已被 `.gitignore` 忽略），再运行 `python scripts/ledger.py add personal --file entry.tmp`。不要在 PowerShell 里用管道传分录，中文会变成问号。
- `add` 会注入 `time`、写进 `<账本>/journal/YYYY-MM.beancount`、追加 include 并校验整本账；不通过就整笔回滚，账本保持原样。
- 更多写法参照 `examples/cookbook.beancount`：AA、代垫、信用卡还款、退款、押金、贷款、基金、外币等都有范例。

有多本账、且两本账之间有往来时（用个人账户替店里付钱、店里的钱进了个人账户），**两本账一起记，用 `pair`**，一段一本账：

```bash
python3 scripts/ledger.py pair <<'EOF'
[personal]
2026-09-26 * "商店" "代垫商店采购款-某供应商（股东往来）"
  Assets:Receivable:Shop  200.00 CNY
  Assets:Wechat
[shop]
2026-09-26 * "某供应商" "主营业务成本-采购"
  Expenses:COGS  200.00 CNY
  Liabilities:OwnerLoan
EOF
```

硬规矩：

- **不要手动编辑序时簿**（`<账本>/journal/*.beancount`）。入账只用 `add` / `pair`，改账只用 `amend` / `void`（见 `docs/AI-TASKS.md`「更正与删除」）。这些命令写盘后都会校验整本账，不通过就原样还原；手改会绕过这些保护。
- **被拒绝就照提示改了再录，不要绕开。** 报错是中文的，会写明哪里不对、该用哪个科目或哪种写法。
- **对方和摘要都要写，而且要按规范写。** 首行缺任何一段会被拒绝；写法（摘要开头对应科目、括号只留固定标记、退款结尾加「退款」、记到 `Expenses:Other` 要写 `note:` 等）由 `ledger.toml` 的 `[naming]` 把关，对照表在 `brief` 输出里。
- **不许估时间。** 用户没报具体时间就不写 `time` 行，由脚本注入录入时刻。"7 点半"这类分不清上下午的先问。手写的 `time` 晚于此刻、交易日期晚于今天，都会被拒绝。
- **一次只录一笔。** 多笔分多次调用，脚本检测到多笔会直接拒绝（`pair` 是两本账各一笔）。
- **账本之间的往来两边都记。** beancount 只校验单本账内部平衡，只记一边它发现不了，所以 `add` 碰到往来科目会直接拒绝并给出 `pair` 的写法。`add --one-sided` 只用于补平已有的往来差额。更正、作废往来分录时两本账都要改，改完运行 `python3 scripts/ledger.py reconcile`，确认每对镜像科目相加为 0。
- **不确定上一笔记没记上**时，先 `python3 scripts/ledger.py recent <账本>` 看最近几笔，再决定是否重录。日期、对方、摘要、各科目金额都相同的分录第二次入账会被拒绝；确实是两笔（同一天在同一家店买了两次一样的东西）才加 `--allow-duplicate`。
- **序时簿只收交易和余额断言。** `open` 这类科目表指令 `add` 会拒绝，新科目写进 `<账本>/accounts.beancount`，这个文件可以直接编辑。
- **科目未开立**时入账会失败回滚，报错会列出已开的相近科目。不要自造科目名硬记：先从 `brief` 列出的科目里选；确实需要新科目，就按原格式在 accounts 里 `open`，带上中文注释，和这笔分录一起提交，并告诉用户新开了什么科目。
- **归类是 AI 的事，不问用户。** 用户只说发生了什么、买了什么，记哪个科目由你按 `CATEGORIES.md` 第 1 节自己定（分类只有大类 + 小类两级）。拿不准就翻 `CLASSIFY.md` 的速查词典和对照示例，或查通行分类口径后直接归类；现有科目都不合适、又是会反复出现的品类，就新开科目并补进分类表。**不要问用户"记在哪""选哪个分类"**，实在判断不了才暂记 `Expenses:Other` 并在回复里说明。
- **只有事实缺失才问**：金额、日期、花的是谁的钱（哪本账）、是消费还是借给/垫给别人。连是消费、借款还是代垫都分不清时，先问用户，**不得直接记成费用**。

`ledger.py` 的退出码：0 成功；1 校验不通过或输入有误；2 命令参数不对或 `ledger.toml` 有误；3 缺依赖或 Python 版本太低。

## 第三步：每次改动后校验、提交

```bash
python3 scripts/ledger.py check          # 全部账本校验（有往来镜像时连带对账），必须通过
python3 scripts/ledger.py fmt --check    # 序时簿排版，不过就运行 ledger.py fmt
.venv/bin/python -m ruff check scripts tests && .venv/bin/python -m pytest   # 改了 scripts/ 或 tests/ 才需要
```

启用了提交前自动检查（`scripts/hooks/pre-commit`）的仓库，提交时会自动跑上面这些。推送后没有云端检查兜底，钩子是唯一的关口：每台设备、每个克隆都要启用一次（`git config core.hooksPath scripts/hooks`），没启用时入账命令会在末尾提醒，看到就先启用再提交。改脚本要用的 pytest、ruff 用 `.venv/bin/python -m pip install -r requirements-dev.txt` 安装。

然后 `git status` 过一遍变更清单再提交。提交信息首行写 `类型: 摘要`：类型保留英文，摘要用书面中文，首行不带括号、不超过 80 字。启用了 `scripts/hooks/commit-msg` 的仓库会强制检查，不合规提交不了。

- 类型：`feat` 登记新账、补记、新开科目；`fix` 更正、作废、对账调整；`style` 只重排序时簿；`docs` 改规则或文档；`refactor` / `test` / `chore` 用于脚本与杂务。改了账本的提交只能用 `feat` / `fix` / `style`。
- 改了账本的摘要以「登记」「补记」「更正」「作废」「对账」「重排」（科目表、建账用「新开」「新建」「初始化」）之一开头，依次写账本、日期、业务、金额、结算方式，并写明改到的每本账（称呼取 `ledger.toml` 的 title，「个人账本」写「个人账」）。
- 金额保留两位小数带「元」，日期写「10月28日」，结算方式写「支付宝付款」「微信收款」。
- 示例：`feat: 登记个人账10月28日午餐支出18.00元，微信付款`，`feat: 登记个人账与商店账10月28日代垫进货款200.00元，微信付款`，`fix: 更正个人账10月25日打车费，改记花呗付款`，`docs: 新增宠物支出分类`。

**每次改动后立即提交**；配置了远程仓库就立即推送，账本以远程为准。没有远程仓库的照常提交，推送改为下一节的备份。

## 没有远程仓库时（豆包等云电脑）

用户不会用 GitHub、没有远程仓库时走这一节。Git 照用，只是没有远程：在本地提交，不需要账号，也不联网。**这些都由你来做，不要让用户去学 Git，也不要跟他提 Git。**

账本常驻个人目录（如 `~/AI记账/ledger`）时，日常只有两条命令：

```bash
python3 scripts/bootstrap.py && python3 scripts/ledger.py doctor    # 每次开始：自检，把 doctor 列出的最后一笔用大白话报给用户
```

```bash
git add -A && git commit -q -m "feat: 登记个人账10月28日午餐支出18.00元、打车支出32.00元" && python3 scripts/ledger.py backup --daily    # 每批改动后：提交并备份
```

`backup --daily` 当天第一次会生成 `backups/ledger-backup-*.zip`，**生成了就把它传到用户云盘的备份文件夹**，并告诉用户；没传成功要明说。

**其余情况先读 `docs/AI-SETUP.md`「没有远程仓库时」再动手**：账本目录找不到了（不要凭空新建）、每次对话都是全新环境、第一次建账、云盘备份怎么留怎么删、找不到云盘工具、授权过期。

## 回报用户

入账后用一句话回报**一级大类、金额、结算账户、所打标签**，用户一句话就能纠正。
对用户说话可以口语化，写进账本的 payee 和摘要一律用书面语（规范见 `CATEGORIES.md` 0.1）。用户用什么语言说话，就用什么语言回复。

用户问"我有多少钱""列一下资产"时，有多本账且都归他一个人，就按合并口径回答（`networth`）：各本账的钱合在一起列，只列真实的钱（银行卡、微信、支付宝、现金、基金等）和对外的欠款、债权（信用卡、花呗、别人欠的钱等）。账本之间的往来科目合并后互相抵销，**不要列出来**，用户问到或对账需要时才单独说。

## 隐私

账本是用户的隐私数据。不要把账本内容、余额、交易明细发给任何外部服务（搜索引擎、粘贴站、第三方 API），除非用户明确要求。

## 按情况查阅

日常记一笔只需要上面三步和 `CATEGORIES.md`。下面这些情况遇到了再读：

| 遇到什么 | 读哪里 |
|---|---|
| 不知道归哪个科目 | `CLASSIFY.md`：速查词典、「用户原话 → 怎么记」对照示例 |
| 贷款、基金股票、黄金、外币折现、与他人共有的账本、不计入净资产的钱 | `ACCOUNTING.md`（没有这个文件的旧账本，这些内容在 `CATEGORIES.md` 第 4、5 节） |
| 第一次接手、`doctor` 报了问题、远程仓库是公开的 | `docs/AI-SETUP.md`「第一次接手」 |
| 账本放哪、怎么同步、没有远程仓库 | `docs/AI-SETUP.md`「账本存哪」「没有远程仓库时」 |
| 账本还没初始化、用户说"帮我建账"（首次使用）、用户不懂记账 | `docs/AI-SETUP.md`「首次使用」「引导新手」 |
| 记错了要改、要删 | `docs/AI-TASKS.md`「更正与删除」 |
| 用户报了账户余额要核对 | `docs/AI-TASKS.md`「余额核对」 |
| 导入支付宝、微信账单 | `docs/AI-TASKS.md`「导入账单」 |
| 行程、临时默认账户等会过期的情况 | `docs/AI-TASKS.md`「行程与临时状态」，写进 `STATE.md` |
| 用户要改分类或规则 | `docs/AI-TASKS.md`「修改规则」 |
| 升级本项目的脚本 | `docs/AI-TASKS.md`「升级工具」 |
| 新建一本账（店铺、家庭共同账） | `docs/AI-TASKS.md`「新建账本」 |
| 用户问花了多少、有多少钱 | `docs/AI-TASKS.md`「常用查询」 |
| 每周定投、每月房租这类到日子就该有的账，想让脚本提醒 | `docs/REFERENCE.md`「周期事项」 |
| 有哪些命令、参数 | `python3 scripts/ledger.py --help`，`docs/REFERENCE.md` |

文档分工：长期规则只写进 `CATEGORIES.md`（日常）和 `ACCOUNTING.md`（专题），会过期的情况只写进 `STATE.md`；写法规则只在 `ledger.toml` 的 `[naming]`。冲突时以 `CATEGORIES.md` 为准（写法以 `[naming]` 为准）。

## 改脚本时

- 实现在 `scripts/ledgerlib/`，`scripts/ledger.py` 只是入口。已有命令的用法不要随意改，用户和规则文档都依赖它们。命令清单以 `python3 scripts/ledger.py --help` 为准。
- 各模块只管一件事，新逻辑放进对应模块，不要跨模块借用下划线开头的内部函数：
  - `config`：读 `ledger.toml`。
  - `naming`：对方与摘要的写法检查与 `rules` 对照表（规则在 `ledger.toml` 的 `[naming]`，没配就不查）。改写法规则只改 `[naming]`，文档不再抄表。
  - `entry`：分录文本的检查与预处理，不碰磁盘。
  - `journal`：序时簿分块、行号与分录编号。
  - `store`：加锁、写盘、整本校验、失败还原。**所有改动序时簿的命令都必须经 `store.commit` / `store.commit_many`**（唯一例外是 `fmt`：它要做更严的前后余额比对，自己写盘，但同样要拿 `store.book_lock`）。
  - `add` / `pair` / `edit` / `fmt`：入账、往来两本账一起入账、更正与作废、排版。
  - `brief` / `recurring`：入账前的一页现场信息、周期事项漏记提醒（规则在 `ledger.toml` 的 `[[recurring]]`，只提醒不代记）。
  - `books` / `query` / `reconcile` / `networth` / `display`：加载账本与报错翻译、查询、对账、合并资产、输出对齐。
  - `dividend` / `fxrate` / `quote`：按月利润分配、现拉汇率和金银价、按代码取基金股票等各类价格。
  - `doctor` / `env` / `backup` / `newbook`：环境自检、依赖与 `.venv`、打包备份、新建账本。
  - `commitmsg`：提交信息检查（commit-msg 钩子调用）。
- 代码里不写死任何账本名。账本、往来镜像、周期事项、时区、本位币、写法规则一律从 `ledger.toml` 读取（`ledgerlib/config.py`）。
- 新增或修改逻辑要配套 `tests/` 用例。测试用 `conftest.py` 的 `ledger`（两本账）、`solo`（只有个人账）、`empty_root`（空目录）fixture 在临时目录搭账套，**不要让测试碰真实账本**。
- 改了查询类命令，要拿改动前的 `balances` / `report` 输出比对，确认口径没有意外变化。
