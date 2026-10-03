# AGENTS.md

本仓库是一套 [Beancount](https://github.com/beancount/beancount) 纯文本复式账本，不是普通代码仓库。
用户让你记的、改的都是他的真实账目，下面的规则是硬约束。

Windows 上把命令里的 `python3` 换成 `python` 或 `py`。

## 第一次接手

1. 运行 `python3 scripts/ledger.py doctor`。它会报告依赖是否齐全、有哪些账本、账本有没有初始化、Git 远程仓库是否安全，最后列出下一步。
2. 缺依赖时（任何命令退出码为 3）运行 `python3 scripts/bootstrap.py`。官方源装不上时它会自动换清华镜像再试一次，还不行再用 `-i <镜像地址>` 指定别的镜像。
   依赖装在仓库的 `.venv` 里，之后照常运行 `python3 scripts/ledger.py`，入口会自动改用 `.venv`。
   不要加 `--break-system-packages` 往系统 Python 里装包。
3. doctor 提示 origin 是公开的模板仓库，或远程仓库是公开的：**先停下来告诉用户**，等用户有了自己的私有仓库再提交账目。
   - 做法：在 GitHub 打开模板仓库，点 Use this template，可见性选 Private。不要 Fork，公开仓库的 Fork 也是公开的。
   - 装了 `gh` 且用户同意时，可以代为执行 `gh repo create <仓库名> --private --template Xbang0222/beancount-ai-ledger --clone`。
   - 已经在模板的克隆里改了东西：`git remote rename origin upstream`，再 `git remote add origin <私有仓库地址>` 并推送。
4. doctor 提示提交前自动检查没有启用：运行 `git config core.hooksPath scripts/hooks`。之后每次提交会自动跑账本校验和排版检查，不通过就提交不了。
5. doctor 提示账套目录不是 Git 仓库：先 `git init` 并提交。在自己电脑上用 Claude Code、Codex 的，再建议建一个私有远程仓库；只用豆包这类云电脑、不会用 GitHub 的，按下文「没有远程仓库时」做，**不要让用户去学 Git**。
6. doctor 提示账本还没初始化：按下文「首次使用」引导用户。

## 每次开始前

1. 配置了远程仓库就先 `git pull --ff-only`，避免多台设备同时记账产生冲突。没有远程仓库的，按「没有远程仓库时」找到账本。
2. 看有哪些账本：`python3 scripts/ledger.py books`（配置在 `ledger.toml`）。只有一本 `personal` 时不存在记哪本账的问题。
3. 读 `CATEGORIES.md` 和 `STATE.md`。
   - `CATEGORIES.md`：分类与核算口径的唯一依据，包括付款渠道对应哪个账户、科目怎么归类、摘要怎么写、往来和标签怎么处理、时间戳规则。
   - `STATE.md`：当前生效的临时情况，比如进行中的行程和它的默认标签、临时的默认付款账户。事项结束后删掉。
   - 两者冲突时以 `CATEGORIES.md` 为准。长期规则只写进 CATEGORIES，会过期的情况只写进 STATE。
4. 分录写法参照 `examples/cookbook.beancount`：AA、代垫、信用卡还款、退款、押金、贷款、基金、外币等都有范例。

## 入账

只能通过 `add` 入账，一次一笔。分录用 heredoc 从标准输入传入：

```bash
python3 scripts/ledger.py add personal <<'EOF'
2026-09-26 * "面馆" "餐饮-午餐"
  Expenses:Food:Dining  18.00 CNY
  Assets:Wechat
EOF
```

- `personal` 换成 `ledger.toml` 里的账本名。标签写在首行末尾，如 `"餐饮-午餐" #trip #chengdu`。
- 没有 heredoc 的终端（如 Windows PowerShell）：先把分录写进 UTF-8 编码的 `entry.tmp`（已被 `.gitignore` 忽略），再运行 `python scripts/ledger.py add personal --file entry.tmp`。不要在 PowerShell 里用管道传分录，中文会变成问号。
- `add` 会注入 `time`、写进 `<账本>/journal/YYYY-MM.beancount`、追加 include 并校验整本账；不通过就整笔回滚，账本保持原样。

硬规矩：

- **不要手动编辑序时簿**（`<账本>/journal/*.beancount`）。入账只用 `add`，改账只用 `amend` / `void`（见「更正与删除」）。这三条命令写盘后都会校验整本账，不通过就原样还原；手改会绕过这些保护。
- **对方和摘要都要写。** 首行缺任何一段，`add` 会拒绝。
- **不许估时间。** 用户没报具体时间就不写 `time` 行，由脚本注入录入时刻。"7 点半"这类分不清上下午的先问。手写的 `time` 晚于此刻、交易日期晚于今天，`add` 都会拒绝。
- **一次只录一笔。** 多笔分多次调用，脚本检测到多笔会直接拒绝。
- **账本之间的往来两边都记。** beancount 只校验单本账内部平衡，只记一边它发现不了。`add` 碰到往来科目会打印 `[提示]`，告诉你另一边该记到哪本账的哪个科目。两边记完运行 `python3 scripts/ledger.py reconcile`，确认每对镜像科目相加为 0。
- **不确定上一笔记没记上**时，先 `python3 scripts/ledger.py recent <账本>` 看最近几笔，再决定是否重录。日期、对方、摘要、各科目金额都相同的分录第二次入账会被 `add` 拒绝；确实是两笔（同一天在同一家店买了两次一样的东西）才加 `--allow-duplicate`。
- **序时簿只收交易和余额断言。** `open` 这类科目表指令 `add` 会拒绝，新科目写进 `<账本>/accounts.beancount`，这个文件可以直接编辑。
- **科目未开立**时 `add` 会失败回滚。不要自造科目名硬记：先对照 `<账本>/accounts.beancount` 选已有科目；确实需要新科目，就按原格式在 accounts 里 `open`，带上中文注释，和这笔分录一起提交，并告诉用户新开了什么科目。
- **分类拿不准不要硬猜。** 只有"确定是消费、只是不知道归哪类"才暂记 `Expenses:Other`，并在回复里说明；连是消费、借款还是代垫都分不清时，先问用户，**不得直接记成费用**。

`ledger.py` 的退出码：0 成功；1 校验不通过或输入有误；2 命令参数不对或 `ledger.toml` 有误；3 缺依赖或 Python 版本太低。

## 每次改动后

```bash
python3 scripts/ledger.py check          # 全部账本校验（有往来镜像时连带对账），必须通过
python3 scripts/ledger.py fmt --check    # 序时簿排版，不过就运行 ledger.py fmt
.venv/bin/python -m ruff check scripts tests && .venv/bin/python -m pytest   # 改了 scripts/ 或 tests/ 才需要
```

启用了提交前自动检查（`scripts/hooks/pre-commit`）的仓库，提交时会自动跑上面这些。改脚本要用的 pytest、ruff 用 `.venv/bin/python -m pip install -r requirements-dev.txt` 安装。

然后 `git status` 过一遍变更清单再提交。提交信息用 Conventional Commits（`type(scope): 摘要`）：

- `type`：`feat` 记新账，`fix` 更正账目，`docs` 改规则或文档，`refactor` / `test` / `chore` 用于脚本与杂务；
- `scope`：账本名（如 `personal`、`shop`），或 `script` / `docs`；
- 示例：`feat(personal): 餐饮-午餐 18 元`，`fix(personal): 打车改记花呗`，`docs: 新增宠物支出分类`。

**每次改动后立即提交**；配置了远程仓库就立即推送，账本以远程为准。没有远程仓库的照常提交，推送改为下一节的备份。

## 没有远程仓库时（豆包等云电脑）

用户不会用 GitHub、没有远程仓库时走这一节。Git 照用，只是没有远程：在本地提交，不需要账号，也不联网。**这些都由你来做，不要让用户去学 Git，也不要跟他提 Git。**

下面用「AI记账」举例：账本目录是个人目录下的 `~/AI记账/ledger`，云盘里的备份文件夹也叫「AI记账」。用户指定了别的位置就用他指定的。

### 先弄清账本放哪

看这个环境里有没有**换一个对话还在**的目录。实际检查，不要猜：个人目录是不是独立挂载的盘、里面有没有以前的对话留下的文件。

- **有**（豆包云电脑的个人目录 `~` 就是：重启只清系统盘，个人目录一直在，任何对话都能读写）：账本常驻 `~/AI记账/ledger`，云盘只做保险，按下面「账本常驻」做。不要把账本放在这次对话的工作目录或 `/tmp` 里。
- **没有**（每次对话都是全新的环境）：账本以压缩包形式存在云盘，按下面「账本存云盘」做。

### 账本常驻（目录能保留）

开始时：

1. 进 `~/AI记账/ledger`，一条命令自检：

   ```bash
   python3 scripts/bootstrap.py && python3 scripts/ledger.py doctor
   ```

2. doctor 的「账本」一节会列出每本账的最后一笔。用大白话告诉用户，比如"账本里最后一笔是 10 月 3 日买菜 35 元"。用户这句话里已经带了要记的账，报完可以直接记，不用等回复。
3. 目录不在时，**不要凭空新建账本**。先到云盘「AI记账」文件夹找文件名里日期最新的 `ledger-backup-*.zip`：
   - 找到了：下载并 `unzip` 到 `~/AI记账/`，得到 `ledger/`。告诉用户"原来的位置找不到账本了，已从云盘 X 月 X 日的备份恢复"，报出最后一笔请他核对，那天之后记的账要补。
   - 云盘里也没有：问用户是不是第一次用。确认是，才按下文「第一次建账」做。

每批改动后（记账、更正、改规则都算），一条命令：

```bash
git add -A && git commit -q -m "feat(personal): 餐饮-午餐 18 元、交通-打车 32 元" && python3 scripts/ledger.py backup --daily
```

- 提交信息按「提交信息」一节写。一批里有好几笔时逐笔 `add`，全部记完再提交一次。
- `backup --daily` 今天已经备份过就什么都不做；今天还没备份就生成一个 `backups/ledger-backup-*.zip`。**生成了就把它传到云盘「AI记账」文件夹**，回报用户时带一句"今天的备份已存到云盘"。没传成功要明说。
- 用户说"存一下云盘"：去掉 `--daily` 再运行一次并上传。

### 账本存云盘（目录留不住）

1. 开始时到云盘「AI记账」取文件名里日期最新的 `ledger-backup-*.zip`，`unzip` 得到 `ledger/`，在里面运行上面那条自检命令，报最后一笔。用户说不对，说明取到的是旧备份，停下来找最新的那份。云盘里找不到时不要凭空新建，先问用户。
2. 每批改动后提交并打包（上面那条命令去掉 `--daily`），把压缩包传到云盘，回报"已存到云盘"。不要攒到对话最后。没存成功要明说，并把压缩包直接发给用户，请他自己保存。

### 云盘里的备份

- 一律用 `backup` 生成的带日期时间的文件名上传，**不要传同名文件去覆盖**：很多云盘会变成两个同名文件，分不清新旧。
- 只留最新一份 `ledger-backup-*.zip`（改动历史已经在压缩包里，旧的没有额外价值）。**新的上传成功、确认云盘里能看到之后**，再删更早的；只删这个文件夹里符合这个命名的压缩包，别的文件不碰。
- 找不到云盘工具时，先看 `~/vm/resource-loader/bin/`（豆包云电脑的云盘工具 `lark-cli` 在这里，不在 PATH 里）。还是没有，或者连不上云盘，就把压缩包直接作为文件发在对话里，请用户自己保存，并明说"这次没存到云盘"。不要跳过备份不提。
- 提示授权过期时，告诉用户"需要重新授权云盘，点一下同意就行，账本不受影响"，授权好之后补存。

### 第一次建账

1. 把模板放到账本目录：`git clone --depth 1 https://github.com/Xbang0222/beancount-ai-ledger ~/AI记账/ledger`，然后删掉里面的 `.git`（那是模板的历史，不是用户的）。克隆不了就下载 `https://github.com/Xbang0222/beancount-ai-ledger/archive/refs/heads/main.zip` 解压。
2. 按「首次使用」和「引导新手」建账。
3. 建好后建本地仓库并提交，只需要做这一次：

   ```bash
   git init -q && git config user.name "记账助手" && git config user.email "ledger@localhost" && git config core.hooksPath scripts/hooks && git add -A && git commit -q -m "chore: 初始化账本"
   ```

4. 运行 `python3 scripts/ledger.py backup`，把压缩包传到云盘「AI记账」文件夹（没有就新建）。

doctor 提示账套目录不是 Git 仓库（旧版本留下的账本）时，补做第 3 步。环境里没有 git、也装不上时跳过所有 git 命令，其余照做，只是查不了改动历史。

### 其他

- 用户问"上周那笔我改过什么""之前是怎么记的"，用 `git log -p` 查，把结果用大白话告诉他。
- 没实测过的事要说明是推断，不要说成事实。命令报错了照实说，不要绕过去。
- 其余规矩照旧：只能用 `add` 入账，一次一笔，不估时间。推送这一步跳过。

## 回报用户

入账后用一句话回报**一级大类、金额、结算账户、所打标签**，用户一句话就能纠正。
对用户说话可以口语化，写进账本的 payee 和摘要一律用书面语（规范见 `CATEGORIES.md` 0.1）。用户用什么语言说话，就用什么语言回复。

用户问"我有多少钱""列一下资产"时，有多本账且都归他一个人，就按合并口径回答（`networth`）：各本账的钱合在一起列，只列真实的钱（银行卡、微信、支付宝、现金、基金等）和对外的欠款、债权（信用卡、花呗、别人欠的钱等）。账本之间的往来科目合并后互相抵销，**不要列出来**，用户问到或对账需要时才单独说。

## 常见请求

用户可能怎么说，`docs/GUIDE.md` 里列了一遍。下面是几类不是"记一笔"的请求。

### 首次使用（doctor 提示未初始化，或用户说"帮我建账"）

1. 一次问清：有哪些账户（银行卡、支付宝、微信、现金、信用卡、花呗等）、从哪天开始记、各账户那天开始时的余额、没说付款方式时默认用哪个账户。
2. 改 `personal/accounts.beancount`：按用户的真实账户增删、改名（如 `Assets:Bank:Main` 改成 `Assets:Bank:CMB`），用不到的删掉。
3. 在 `personal/opening.beancount` 登记期初：开账日前一天写 `pad`，开账日写 `balance`，负债写负数。
4. 改 `CATEGORIES.md`：第 0 节的付款渠道对照表和默认付款账户换成用户的账户，删掉文件开头的模板提示（doctor 靠它判断规则有没有改过）。
5. `check` 通过后提交，如 `chore(personal): 初始化账户与期初余额`。

### 引导新手（用户不懂记账、不懂技术，或说"我不知道要准备什么"）

用户很可能是第一次接触记账，也看不懂命令和科目。由你带着他走，他只需要回答问题。

- **一次只问一件事**，用大白话，给出例子。不要一口气列一张清单让他填，也不要出现"科目""分录""期初""借贷"这类词。按这个顺序问：
  1. "你平时的钱都放在哪？比如微信、支付宝、银行卡、现金，有几样说几样。"
  2. "有没有欠着的钱？比如花呗、信用卡、白条、借别人的。"
  3. 逐个问余额："打开微信看一下零钱，现在是多少？"用户说不准就让他报个大概，告诉他以后可以对账更正。
  4. "平时付款最常用哪个？以后你没说怎么付的，我就默认记它。"
- **命令、文件名、报错不要念给用户听。** 自己处理，只说结果。出错了说人话："刚才没存上，我再试一次"。
- **建好后复述一遍**，让用户确认：有哪几个账户、各多少钱、欠多少、默认用哪个付。
- **马上带他记第一笔。** 说："现在试一下，告诉我你今天最近的一笔花销，比如『午饭 18，微信付的』。"记完按「回报用户」的格式回一句，让他看到效果。
- **最后教他三件事**，每件一句话：
  1. 以后怎么开始：把「以后每次」那句开场白（见 `docs/NO-GIT.md`，有远程仓库的不需要）原样发给他，建议他存到备忘录。
  2. 记错了怎么办：直接说"刚才那笔不对，应该是……"。
  3. 能问什么："这个月花了多少""我现在有多少钱""这次旅行一共花了多少"。
  4. 没有远程仓库的再说一句：云盘「AI记账」文件夹里是账本的备份，只有一个压缩包，很小，别删这个文件夹。
- 用户一次说了好几笔、说得很乱、或者夹着闲聊，都正常。拆开逐笔记，拿不准的那一笔单独问，其余照记。

### 更正与删除（"刚才那笔不是花呗，是微信"）

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
- 往来分录要两本账一起改，改完跑 `reconcile`。
- 提交用 `fix(<账本>): …`，写清改了什么。不要用"再记一笔反向分录"修正录错的账；反向分录只用于真实发生的冲回，比如退款。

### 余额核对（"对一下账：支付宝现在还剩 427"）

用 `add` 写 `balance` 断言，日期写**明天**：balance 断言的是"当天开始时"的余额，用户报的是此刻的余额，写明天才包含今天已发生的交易。

```bash
python3 scripts/ledger.py add personal <<'EOF'
2026-09-27 balance Assets:Alipay  427.00 CNY
EOF
```

- 通过：告诉用户对上了，然后提交。断言留在账里，以后再出偏差 `check` 会发现。
- 不通过：`add` 会回滚并报出差额。把差额告诉用户，用 `recent` 列出相关账户的近期交易，帮用户找漏记或记错的那笔；找到后补记或更正，再核对一次。**不得擅自用 `Equity:Adjustment` 找平**；只有用户确认找不到原因、同意调整时，才记一笔调整分录，摘要写明原因。

### 导入账单（"这是支付宝导出的账单，帮我记进去"）

- 导出文件只在本地读，不要提交（`.gitignore` 已忽略 `*.csv`、`*.xlsx`）。
- 先和用户确认：导入哪段时间，账单里的支付方式各对应哪个账户，和已经记过的账怎么去重（按日期、金额、对方比对序时簿）。
- 仍然逐笔调用 `add`，可以写循环；不要直接写序时簿。账单里的交易时间写进 `time` 行，这是用户提供的数据，不算估时间。
- 账户之间的划转（充值、提现、还信用卡、转入余额宝）不是收支；退款冲减原支出（`CATEGORIES.md` 第 4、5 节）。
- 导完跑 `check`，告诉用户导入了几笔、跳过了几笔重复、几笔拿不准暂记在 `Expenses:Other`。

### 行程与临时状态（"我 10 月 1 号到 5 号去成都"）

- 写进 `STATE.md`：日期区间和默认标签（如 `#trip #chengdu`）。区间内发生的交易带上这些标签，按交易发生日判断，不按录入日。
- 用户说回来了，或者区间已经过去，就从 `STATE.md` 删掉并提交。

### 修改规则（"以后奶茶单独算一类"）

- 长期规则改 `CATEGORIES.md`；需要新科目时在 `accounts.beancount` 里开立。提交信息如 `docs: 奶茶单独分类`。
- 以前已经记了的分录要不要跟着改，先问用户，不要自作主张批量改历史账。

### 升级工具（"帮我升级记账项目"）

只换脚本、测试和说明文档，账本数据和用户自己的规则不动：

```bash
git remote add upstream https://github.com/Xbang0222/beancount-ai-ledger.git 2>/dev/null; git fetch -q upstream
git checkout upstream/main -- scripts tests docs AGENTS.md requirements.txt requirements-dev.txt pyproject.toml
python3 scripts/bootstrap.py && git commit -q -m "chore(script): 同步上游脚本"
```

- `CATEGORIES.md`、`STATE.md`、`ledger.toml` 和各账本目录不要覆盖。用户改过 `AGENTS.md` 的，先问他再覆盖。
- 升级后重读一遍 `AGENTS.md`，告诉用户升到了哪个版本（`CHANGELOG.md` 最上面一条）和最后一笔是什么。

### 新建账本（"我开了个网店，帮我建本店铺账"）

- 用 `new-book`：经营账加 `--template business`；要和个人账互相垫付、代收的加 `--link personal`；与他人共有、不算个人资产的（如家庭共同账）加 `--no-consolidate`。
- 建好后在 `CATEGORIES.md` 第 3 节写清这本账记什么，然后提交。

## 常用查询

| 想知道 | 命令 |
|---|---|
| 最近记了什么 | `ledger.py recent personal [-n 20]` |
| 某一笔记在哪、记成了什么 | `ledger.py find personal 超市 128` |
| 这个月花了多少、花在哪 | `ledger.py summary personal 2026-09` |
| 月度报告（收入、支出占比、储蓄率） | `ledger.py report personal 2026-09` |
| 每个账户还剩多少 | `ledger.py balances personal` |
| 某次旅行、某件事总共花了多少 | `ledger.py tag personal trip` |
| 总资产、净资产（多本账合并、外币折算） | `ledger.py networth` |
| 账本之间的往来对不对得上 | `ledger.py reconcile` |

有外币时，算总资产前按 `CATEGORIES.md` 第 5 节现查当天汇率，用 `--rate` 传给 `networth`。

## 隐私

账本是用户的隐私数据。不要把账本内容、余额、交易明细发给任何外部服务（搜索引擎、粘贴站、第三方 API），除非用户明确要求。

## 改脚本时

- 实现在 `scripts/ledgerlib/`，`scripts/ledger.py` 只是入口。已有命令的用法不要随意改，用户和规则文档都依赖它们。命令清单以 `python3 scripts/ledger.py --help` 为准。
- 各模块只管一件事，新逻辑放进对应模块，不要跨模块借用下划线开头的内部函数：
  - `config`：读 `ledger.toml`。
  - `entry`：分录文本的检查与预处理，不碰磁盘。
  - `journal`：序时簿分块、行号与分录编号。
  - `store`：加锁、写盘、整本校验、失败还原。**所有改动序时簿的命令都必须经 `store.commit`**。
  - `add` / `edit` / `fmt`：入账、更正与作废、排版。
  - `books` / `query` / `reconcile` / `networth` / `display`：加载账本、查询、对账、合并资产、输出对齐。
  - `doctor` / `env` / `backup` / `newbook`：环境自检、依赖与 `.venv`、打包备份、新建账本。
- 代码里不写死任何账本名。账本、往来镜像、时区、本位币一律从 `ledger.toml` 读取（`ledgerlib/config.py`）。
- 新增或修改逻辑要配套 `tests/` 用例。测试用 `conftest.py` 的 `ledger`（两本账）、`solo`（只有个人账）、`empty_root`（空目录）fixture 在临时目录搭账套，**不要让测试碰真实账本**。
- 改了查询类命令，要拿改动前的 `balances` / `report` 输出比对，确认口径没有意外变化。
