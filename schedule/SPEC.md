# SuperMemo 20 文章 / 摘录排期与自动推迟 — 复刻规格（定稿）

> **注**：文中引用的 `逆向证据/`、调试器报告等原始记录未随本仓库公开，结论已并入正文。

> **证据来源**（三方）：
> 1. **M 包**：Muse 逆向 agent 的包（SPEC 存为 `逆向证据/旧版规格_Muse.md`，sched1–10 证据同目录）。内容最全，本稿以它为底本。
> 2. **G 包**：Grok 的包（SPEC 存为 `逆向证据/旧版规格_Grok.md`）。
> 3. **2026-10-19 四路独立反汇编裁决**（下称「裁决 N」，N = 1…12）。裁决已对二进制独立核过；与两包冲突时一律以裁决为准，被推翻的说法集中列在 §8。
>
> 二进制：`sm20.exe`（SuperMemo 20），SHA-256 `c58f89df51b6cf118ed8ca76a52017e2e7a82aa20ce3656d6e23d5801f0ccf68`，PE32+ x86-64 Delphi，ImageBase `0x400000`，地址均为 VA。
> 引用写法：`M包/schedN` = `逆向证据/schedN_*.md`；`M包 §x` = `逆向证据/旧版规格_Muse.md`；`G包 §x` = `逆向证据/旧版规格_Grok.md`；「裁决 N」= `逆向证据/裁决记录_2026-10-19.md`。
> 优先级算法见 `../priority/SPEC.md`（下称「优先级定稿」），本稿只在推迟用到优先级处引用，不重写。
> 参考实现：同目录 `schedule.py`（标准库，today 与 rng 由参数注入）；断言：`python3 -I test_vectors.py`，退出码 0 才算过。
>
> **图例**：✅ 静态闭环（地址 + 指令可复核）｜🧪 在原版进程里实测｜❓ 未确认（写明卡在哪）。
> **🧪 界面实测（2026-10-19 起，见 `../measurements/`）**：摘录 AF 两条公式、复习后调 AF（26/26）、逾期天数不参与新间隔、日切默认 0 吻合；冲突的几处经补查裁决（`逆向证据/补查_2026-10-19/裁决.md`，下称「补查裁决」）已定：新建 topic 按正文长度重写 AF（§3.2）、推迟对话框映射与 topic 保护方向（§5.1、§5.6）、复习后挪优先级（§4.4）、摘录 n（§3.3）。仍未定的见 §10 第 17–24 条。读数与比对见 `../measurements/实测报告_第一轮.md`、`实测报告_第二轮.md`。测试向量里新 topic AF、第八轮逐篇推迟（R8）、第九轮新间隔与 AF 调整（R9，§4.2、§4.3）是「原版实测」，其余是「公式推演」；复习后挪位的实测向量在优先级那边。
> **🧪 调试器实测（第四到第九轮，见 `../measurements/调试器报告_*.txt`）**：在原版进程上挂记录断点，自动推迟从触发到写回逐步取证。自动推迟实际用的设置（§5.1）、排序方向（§5.5）、逐篇推迟天数（§5.6，19/19 逐位回代）已定稿；第九轮核复习后新间隔与 AF 调整（§4.2、§4.3，15 + 5 次逐位吻合，原始日志 `../measurements/调试器日志_第九轮.txt`）。向量标「原版实测」。云电脑那份 exe 与本稿地址不同，换算表见 `逆向证据/自动推迟_2026-10-19/两份exe地址对照.md`。

---

## 1. 范围

| 在内 | 不在内 |
|---|---|
| 新元素初始 AF / 间隔 / LastRep；摘录时子与父的 AF | item 的 SM-18/20 记忆算法（评分提交 `0xd8f3e0`） |
| topic 复习提交后的新间隔与 AF 调整 | 优先级怎么算（见优先级定稿） |
| 逻辑日「今天」、当天待复习名单 | 手动改期、Mercy（只在 §7 摘录 M 包单方结论，未经裁决，不实现） |
| 自动推迟：触发、门、执行器、逐元素天数、写回 | `0xa0fbc0`（树控件 DoInit 的模拟计算，与 topic 排期无关） |

---

## 2. 模型

### 2.1 日期与单位 ✅

| 量 | 单位 / 表示 | 说明 |
|---|---|---|
| TDateTime | double，天 | 0 = 1899-12-30，小数是一天内的时刻。`Now()` = `0x4457a0` |
| 日号（day number） | 整数，天 | 集合内一切排期（LastRep、下次复习日、today）都用它 |
| 间隔 | word，天 | 上限 44530（`0xADF2`） |
| 日切偏移 | byte，**小时** | 全局 `[0x1165dd8]`，UI「Midnight shift」，样本 ini 默认 0（M包/sched8 §8） |
| 推迟倍率 | word w，显示 `1 + w/100` | 裁决 11 |
| 优先级 prio | double ∈ [0,100]，0 最高 | 来自优先级定稿 §4.2 `get_priority`（`0xc99450`） |

取整原语（写公式前先分清）✅：

| 地址 | 指令 | 语义 | 记号 |
|---|---|---|---|
| `0x40c5d0` | `cvtsd2si` | 四舍六入五成双 | `R(x)` |
| `0x40c6c0` | `cvttsd2si` | 向零截断 | `trunc(x)` |
| `0x40c5c0` | `sqrtsd` | 开方（不是取整） | `sqrt` |

随机数：`0x40a390` 取导入槽 `[0x1073078]` 的 32 位整数，乘 2⁻³²（常量 `0x1074018`），得 [0,1)。裁决 4：这是 Delphi Random。复刻时作为 `rng()` 注入。✅（LCG 本体 `0x40a350` 未拆 ❓）

### 2.2 元素记录（`0xd71680` 读出的 0x76 字节缓冲）✅

| 偏移 | 类型 | 字段 | 排期里干什么 |
|---|---|---|---|
| +0x00 | byte | etype | 1 = item；0/2/4 在推迟里按 topic；其他值见 §5.3。类型字节 1 是不是就是 item ❓（裁决 1） |
| +0x01 | byte | status | 1 = 已进入复习（memorized），3 = 已删除。推迟写回只认 1 |
| +0x0c | word | Repetitions | topic 提交 +1 |
| +0x10 | word | Interval | 下次复习日 = LastRep + Interval（名单收集时校验） |
| +0x12 | word，有符号读 | LastRep | 日号 |
| +0x14 | TDateTime | 新建 / 提交时刻 | 不是下次复习日 |
| +0x1c | Real48 | AF | 摘录、topic 提交改它；推迟不改 |
| +0x22 | Real48 | 比值槽 | 提交写 `max(1, 新/旧)`；推迟按新/旧缩放。名字 ❓（裁决 12） |
| +0x30 | byte | FI | 0 时 `0xd748e0` 取集合 `+0x11c` |
| +0x31 | dword | 计数 | 推迟使间隔变长时 +1。名字 ❓ |
| +0x35 | dword | 推迟计数 | 推迟使间隔变长时 +1；推迟保护比这一格；topic 提交 flag==0 清零。M 称 TotalPostpones，命名 ❓ |

双精度字段在磁盘上是 6 字节 Real48，经 `0x410400` 读 / `0x410490` 写（G 包 §2.3 给了位拼法）。参考实现**不**模拟写回 Real48 的精度损失 ❓。

### 2.3 集合 / 全局字段 ✅

| 位置 | 内容 |
|---|---|
| `[coll+0xe5]` | RepDates：下标 = 元素 id，值 = 下次复习日（`\info\repetitions.dat`） |
| `[coll+0xed]` / `+0xf5` / `+0xfd` | 当天名单 Outstanding / OutstandingItems / OutstandingTopics（`\info\Outstanding*.sub`） |
| `[coll+0xdd]` | 优先级队列 PQueue（推迟排序键来源） |
| `[app+0x11a]` word | 收集下界（逾期游标） |
| `[coll+0x118]` word | 日号起点偏移 |
| `[coll+0x109]` dword | 新元素写 LastRep、自动推迟「久未用」判定都看它 > 0。含义 ❓ |
| `[coll+0x4c5]` word | 上次自动推迟的日号 |
| `[coll+0x4d0]` double | 上次使用时刻（TDateTime）。写入点 ❓ |
| `[0x1166ea8]` → byte | 自动推迟开关 |
| `[0x1166c60]` → byte | 关开关时弹不弹框 |
| `[0x1163a80]` → 71 字节 | 推迟设置块（§5.1） |

---

## 3. 今天、新元素、摘录

### 3.1 今天 `0xd749b0` → `0xd739e0` ✅（裁决 6）

```
today = trunc(Now − byte[0x1165dd8] / 24) − trunc(base) − word[coll+0x118] + 1
if today == 0: today = 1
```

单位是天，日切偏移单位是小时（24.0 在 `0xd74a58`）。结果缓存在 `[coll+0xd51]`。
❓ epoch / base 的值（`.bss`，静态不可读）、缓存失效逻辑。G 包另记一支「`trunc(Now−shift) − trunc(base) < 0` 时直接返回 1」，裁决未单独覆盖，参考实现不含。

### 3.2 新元素初始值 `0xd72c40` + `0xd72070` ✅（裁决 1）

```
0xd72c40: 先清零 0x76 字节（0x40d1b0）
    类型字节 == 1 → AF(+0x1c) = Real48 82 00 00 00 00 60 = 3.5
    其他          → AF(+0x1c) = Real48 81 9a 99 99 99 19 = double 0x3ff3333333334000
    Interval(+0x10) = 0
0xd72070: 仅当 dword[coll+0x109] > 0 时 LastRep(+0x12) = today
```

`0x3ff3333333334000` 经 `struct` 核得 **1.2000000000007276**（不是字面 1.2 的 `0x3ff3333333333333`）。复刻写这个 double。
G 包补充（未经裁决单独复核）：模板还写 `+0x30 = byte[coll+0x11c]`、`+0x67 = Real48(dword[coll+0x105])`、`+0x14 = Now()` 等。
❓ 新元素的 RepDates 那一格由谁写、第一个复习日是哪天（G包 §4.4）；类型字节 1 是不是 item。

**新建 topic 按正文长度重写 AF** ✅ + 🧪（补查裁决 Q4）：模板之后，调用点 `0xbaa5ee`、`0xf2e055` 用 `0xf28d40` 取当前元素的正文字符串，拿长度前缀 `[rax−4]`（UTF-16 单位）作 L，调 `0xcf73f0(L)`，经 `0xd5c790` 写回 AF：

```
AF = length_af(L) = 1.25 + 150/(L + 200)；L == 0 → 2.0      # 与 §3.3 摘录的 f(n) 是同一个函数
```

`0xcf73f0` 共 5 个调用者：`0xbaa5ee`、`0xf2e055`（已核）、`0xcf6154`（摘录）、`0xbc5949`、`0xf0a509`（未核 ❓）。
🧪 第三轮实测：**L 在建立那一刻量**。Ctrl+N（Edit → Add a new article）会把剪贴板内容自动带进正文：带入 300 字 → 1.550（正好是 f(300)）；带入约 2300 字的任务书后清空，或清空后再手打 300 字 → 都是 1.311，点到别的元素再回来也不变。建好之后改正文不会重算。`0xf2e055` 在什么时候触发 ❓。回代：100 字符 → 1.75，9 篇全中；A01–A06 的 1.412 对应 L ≈ 726（建立时带着剪贴板里的杂文）；T1 的 1.297 对应 L ≈ 2991，当时正文来源没记录 ❓。
🧪 新建 topic 还有间隔 1、LastRep = 今天、下次 = 明天、Repetitions = 1，历史第一行 `Auto interval1`；这一步的代码路径 ❓（G4 说 `0xd73420 → 0xd8aff0`，未核），参考实现不模拟。
参考实现：`new_element` 是模板这一步，`new_topic_af(L)` 是重写这一步。

### 3.3 摘录的 AF ✅（裁决 2）

```
x = 父元素调整前的 AF
f = 0xcf73f0(n):  n == 0 → 2.0；否则 1.25 + 0.75·(10000/n) / (50 + 10000/n) = 1.25 + 150/(n + 200)
t = max(x − 1.01, 0)                     # 0xcf6130；NaN 不改（G包 §5.2）
w = 0.9 − 0.9·t / (0.29 + t)
新元素 AF = x·w + f·(1 − w)
父元素 AF = (x − 1.01)·0.95 + 1.01        # 不再夹紧
父元素的下次复习日、间隔不变
```

适用：ExtractSelection `0xf3a640`（新元素 `[rbp+0x1fc]`，父元素 `[rbp+0x200]`）、FinishGeneratedExtractChild `0xf25ab0`。
🧪 父元素链式衰减 1.377 → 1.341 → 1.325 → 1.309 与公式逐位吻合；新元素 AF 1.717 / 1.649 / 1.410 / 1.493 在三位小数内吻合，反推 n≈17 / 50 / 515 / 204（选区 16 / 50 / 500 / 200 字符）。
**n 的定义** ✅（补查裁决 Q6）：`0xf3a640`（`0xf3ae3a`）和 `0xf3ca90`（`0xf3d1b8`）都先把选区原文交给 `0xf9c9a0` 清洗，再取结果字符串的长度前缀 `[rax−4]`：n = 清洗后字符串的 **UTF-16 长度**，空串为 0。清洗步骤：

| 步 | 做什么 | 来源 |
|---|---|---|
| 1 | 剥掉 HTML 标签；`<P>` / `<BR…>` 先变成 `\r\n`（`0xf9c670`） | 只有 G4 写了 ❓（Grok 没提剥标签） |
| 2 | 三个 `\r\n` 收成一个，做两遍；三个制表符收成一个，做两遍 | 两份一致 |
| 3 | 删掉 `&#65532;` | 两份一致 |
| 4 | `0xf94ba0` 解码实体（`&lt;` `&gt;` `&quot;` `&nbsp;` `&apos;` `&amp;` 等各计 1 字符，`&#十进制;` 计 1 字符，未识别的 `&…;` 整段删） | Grok 写「一批替换没逐条抄完」，具体列表只有 G4 ❓ |
| 5 | 去掉首尾的 `\r` `\n`（空格不去） | 只有 G4 写了 ❓ |

所以选区末尾带的空格、跨段的换行都会算进 n。参考实现不做清洗，调用方直接传 n。`0xf3ca90` 谁父谁子仍 ❓。

---

## 4. topic 复习

### 4.1 disperse `0xcf9e20(x, d)` ✅（裁决 4）

```
d = max(d, 4);  d = min(d, x + 4);  d = clamp(d, 0, 100)
r1 = rng()
m  = −10.857763300760043 × ln(1 − 1.979793637145314 × r1 / 2)     # ln = 0x40c140
if rng() > 0.5: m = −m                                              # 等于 0.5 不翻
return max(1.0, x + m/50 × d)                                       # 调用方再取整
```

每次恰好抽 2 个随机数。

### 4.2 新间隔 `0xe145a0(&记录, mode)` ✅（裁决 3）

```
mode ∈ {5,6}（mode ≤ 7 且 (1<<mode) & 0x60）:
    x = max(1, 旧 >> 1);  d = max(1, x / 2)
否则:
    a = clamp(AF, 1.01, 3.0)                 # 只在计算时钳，不写回
    base = (旧 == 0) ? a³ : 旧 × a
    x = R(min(base, 44530.0));  d = x − 旧
r = R(disperse(x, d))
if r ≤ 旧: r = 旧 + 1
```

- mode 取自 `[[0x1163a28]+0x23f1]`，产品含义 ❓。
- **逾期天数完全不参与**：逾期一天和三个月，算出的新间隔分布相同。
- 🧪 第九轮调试器（11-07，Learn 点 5 篇）：15 次调用的 mode、旧、AF、x、d、两个随机数、抖动返回、新间隔全部逐位吻合；旧与 AF 就是记录 +0x10、+0x1c 原值。每篇除提交那一次外，Learn 还会为下一篇预算两次（不提交，但消耗随机数）。只覆盖了旧 = 1（d 被钳到 4），大间隔分支靠静态。向量 `test_vectors.py` R9。
- 第二轮界面实测「比 R(旧×AF) 偏正」不是规格错：本公式自带偏正（`max(1, …)` 与「≤ 旧 → 旧 + 1」只截负侧）。按本公式回放第二轮能还原的 16 次复习，实测总和 78、期望 75.8，P(≥ 78) ≈ 0.30，属正常波动。

### 4.3 AF 调整 `0xcf7800(&AF, 旧, 新, hard)` ✅（裁决 5）

```
旧 == 0 → 1;  新 == 0 → 1
旧 == 新 → AF 不变
ratio = max/min;  k = hard ≠ 0 ? 80 : 15;  f = ratio / (ratio + k)
delta = max((AF − 1.01)·f, 0.001)
AF = 新 > 旧 ? AF + delta : AF − delta
AF = clamp(AF, 1.01, 6.0)
```

🧪 第九轮 5 次提交逐位吻合（`[R1]`/`[R2]`，k = 15）。

### 4.4 复习提交 CommitTopicRepetition `0xd7ca60` ✅（裁决 3、5；其余步骤取自 M包 §5.3）

```
today = max(today, 1)
Repetitions > 0 → 先从当天名单删掉（0xd5e0d0）
Repetitions += 1
新 = r8d ≥ 0 ? r8d : 0xe145a0(记录, mode)     # 学习窗 Next 传 r8d = −1
LastRep = today
新 < 1 → 新 = 1, LastRep = today − 1          # 下次日 = today
status = 1
AF = 0xcf7800(AF, 旧, 新, hard = flag ≠ 0)    # 调用点 0xd7cee5，新间隔未经 44530 截断
+0x22 = max(1.0, (Repetitions==1 或 旧==0) ? 新 : 新/旧)
Interval = min(新, 44530)
flag == 0 → [rbp+0xd7]（即 +0x35 计数）清零
ScheduleRepetition 0xd8aff0(LastRep + Interval)
```

挪优先级 ✅ + 🧪（补查裁决 Q3）：`0xd7cf1c` 在调 AF 之后、写回 Interval（`0xd7cfc5`）之前调 `0xc99b30(el, 旧间隔, 新间隔, div3 = 0, 写回 = 0)`，新间隔是未经 44530 截断的那个。公式与「落位没变再挪 1 格」见优先级定稿 §4.9。参考实现 `commit_topic_repetition(..., pqueue=None)`：传了队列才挪。

历史记录追加、intact/drill 队列不影响日期，参考实现不建模。

---

## 5. 当天名单与自动推迟

### 5.1 推迟设置块（71 字节，偏移以代码为准）✅

| 偏移 | 宽 | 效果 | 偏移 | 宽 | 效果 |
|---|---|---|---|---|---|
| +0x05 | byte | ≠0：按 PQueue 位置排序、留 N 条、可能第二遍 | +0x1e | word | topic extra 下限 |
| +0x06 | byte | 执行器内部置位：优先级铺开分支 | +0x20 / +0x21 | byte | 对话框 Skip items / Skip topics：勾上（≠0）= 这一类整类不推迟 |
| +0x0f | byte | ≠1 时保护判断前先调 `0xb7edb0`（未拆 ❓，返回值忽略） | +0x22 / +0x26 | dword | base ≥ 它 → 保护（item / topic） |
| +0x10 | word | 留下的条数 N | +0x2a | byte | item FI < 它 → 保护 |
| +0x12 | byte | 0 = 要求「status==1 且已到期」；自动路径强制写 0 | +0x2b | double | topic AF ≤ 它 → 保护 |
| +0x13 | byte | ≠0 = 模拟：不扰动、不写日期 | +0x33 / +0x34 | byte | +0x35 计数 ≥ 它 → 保护 |
| +0x14 / +0x16 | word | item / topic 倍率 w（§5.4） | +0x35 / +0x3d | double | 阈值 > prio → 保护（item / topic） |
| +0x18 / +0x1c | word | item extra 上限 / 下限 | +0x1a | word | topic extra 上限 |
| +0x45 / +0x46 | byte | 对话框「按 FI 调 item」「按 AF 调 topic」，执行器不读 | — | — | 「按优先级调」的勾没接线、不进块；§5.6 的 sqrt 无条件执行 |

两套值：「对话框」= 打开 Postpone 对话框显示的出厂值（补查裁决 Q2，控件 → 偏移见 `逆向证据/补查_2026-10-19/Q2_设置块.md`）；「自动推迟运行时」= 第六轮调试器在进执行器前（T8）转储的块，集合里没有 `postpone.ini`，从没在对话框点过确定 🧪。**复刻自动推迟以运行时那列为准。** 两列只在加粗的三行不同。

| 控件（item / topic） | 偏移 | 对话框 | 自动推迟运行时 |
|---|---|---|---|
| **方法单选** | +0x05 | 0（第二项「按参数」） | **1 = Skip top N**：逾期数 − 已推 ≤ N 就停 |
| Skip top N | +0x10 | 50（灰） | 50 |
| Delay factor | +0x14 / +0x16 | 1.2 / 1.5 → word 20 / 50 | 同 |
| Max interval | +0x18 / +0x1a | 50 / 100 | 同 |
| Min interval | +0x1c / +0x1e | 1 / 6 | 同 |
| Interval beyond | +0x22 / +0x26 | 500 / 800 | 同 |
| FI below（只有 item） | +0x2a | 6 | 同 |
| A-Factor below（只有 topic） | +0x2b | 1.01 | 同 |
| Postpone count | +0x33 / +0x34 | 50 / 100 | 同 |
| Priority (%) | +0x35 / +0x3d | 6 / 3 | 同 |
| **Skip items** / Skip topics | +0x20 / +0x21 | 勾 / 不勾 | **不勾** / 不勾（item 也会被推迟） |
| 按 FI 调 item / 按 AF 调 topic | +0x45 / +0x46 | 勾 / 勾（执行器不读） | 同 |
| **Sub-branch** | +0x0f | 下标未对上 ❓ | **1**（不调 `0xb7edb0`） |
| — | +0x00 | — | 1（含义 ❓） |
| 模拟 / 不查到期 | +0x13 / +0x12 | — | 0 / 0 |

运行时块原文（71 字节）：`01 00 00 00 00 01 00 00 00 00 00 00 00 00 00 01 32 00 00 00 14 00 32 00 32 00 64 00 01 00 06 00 00 00 f4 01 00 00 20 03 00 00 06 29 5c 8f c2 f5 28 f0 3f 32 64 00 00 00 00 00 00 18 40 00 00 00 00 00 00 08 40 01 01`。
后果：**逾期篇数 ≤ 50 时自动推迟一篇都不推**（门 B 只要求 > 10，进了执行器第一篇就停）。逾期 > 50 时按 PQueue 位置排序，逐篇尝试推迟，按成功推迟的篇数判断停止（细则见 §5.5；只有没有跳过、没有保护时，才等于推前面的、留末尾 50 篇）。
❓ 在对话框点确定后自动推迟是不是改用对话框的值（会不会写出 `postpone.ini`）；运行时块从哪里初始化（没拆）。
界面上的「–」表示这一类没有这道保护（块里没有对应字段）。
参考实现：`PostponeSettings.factory_defaults()` 返回「对话框」列，`PostponeSettings.auto_runtime()` 返回「自动推迟运行时」列；`PostponeSettings()` 的默认值仍是「不限条数、除计数外不保护」（计数保护阈值 255，AF 阈值 −inf），测试用。

### 5.2 当天名单 ✅（裁决 7）

```
收集器 0xd87380(lo, hi):           # 不改任何日期
    for 每个元素 id:
        d = RepDates[id]
        lo ≤ d ≤ hi 且 d == LastRep + Interval（否则报 "Repetition date mismatch" 跳过）
        etype==1 → items，否则 → topics
    返回 items + topics（0xe24270 合并）

构建 0xd5e970:  收 [word app+0x11a, today]  —— 逾期的也收
    （若 "Outstanding day" 已是今天且 sub 文件在，只从文件重载，不扫描）
逾期游标 0xd87310（由 0xd87380 在 d8743e 调用）:
    while DayBurden(cursor) < 1 且 cursor < today: cursor += 1
ScheduleRepetition 0xd8aff0(id, newDate):
    RepDates[id] = newDate
    newDate ≤ today → 放回当天名单（0xe24a50）；newDate > today → 不放回
    newDate < word[app+0x11a] → 把 0x11a 下调到 newDate（0xd8b26a）
```

**推迟到今天之后会离开当天名单**：`0xd82aa0` 在 status==1 时先 `0xd5e0d0` 删除，之后 `0xd8aff0` 只在 newDate ≤ today 时加回。
❓ 放回的位置（`0x97b0a0` 未拆，参考实现放队首）；DayBurden `0xd5db60` 的确切返回值（参考实现按「当天到期数」）；游标挪动对本次收集下界是否生效（参考实现：收集开头推进，本次仍用传入下界）；比游标更早的逾期元素还有没有别的入口。

### 5.3 自动推迟的触发 `0xd60450` ✅（裁决 8）

学习启动 `0xd73050`：`0xd60450`（自动推迟）→ `0xd65d30`（auto-sort）→ 学习。

```
开关 byte[[0x1166ea8]] == 0                 → 返回
word[coll+0x4c5] == today                  → 返回（今天已跑过）
dl == 0 且 dword[coll+0x109] > 0（有符号）且 Now − double[coll+0x4d0] > 10.0（NaN 不成立）:
    byte[[0x1166c60]] > 0 才弹框
    开关清零；本次不推迟；返回
[coll+0x4c5] = today                         # 先写，再过门
门 A: Outstanding 元素数 ≤ 10               → 返回
overdue = 收集器([coll+0x11a], today − 1)    # 两端含，item 与 topic 都收，合并
门 B: len(overdue) ≤ 10                     → 返回
写 postpone.ini（0xb7e2f0）；设置 +0x12 = 0；执行器 0xb80c70(overdue)
```

- 当天到期（日期 == today）的元素不在推迟范围内。
- Tools 菜单 `0xe76560` 翻转开关时会把 `+0x4c5` 清零（M包/sched5），即当天可再跑。
- ❓ 写 `+0x4c5` 用的是全局 `0x12be400`，读用的是传入的 collection，是不是同一对象未证。

### 5.4 ItemDelay 的存法 ✅（裁决 11）

```
编辑框 → 设置: v = 文本，解析失败 → word 不变
              v = clamp(v, 1.01, item ? 5.0 : 20.0)
              word = R((v − 1)·100)
显示: 1 + word/100
```

文本 `1.01` → word 1 → 倍率 1.01。

### 5.5 执行器骨架 `0xb80c70 → 0xb81980 → 0xb81850` ✅（裁决 9）

```
+0x05 ≠ 0 → 按元素在 PQueue 的位置排序（0xe23bf0 → 0xe23450，0xe235b0 排序）
第一遍 +0x06 = 0:
    从下标 1 起逐个:
        +0x05 ≠ 0 且 队列数 − 已推迟数 ≤ word(+0x10) → 停（剩下的存 \unpostponed.sub）
        IsDeleted（0xd51690）→ 跳过
        +0x12 == 0 且 不是「status==1 且 LastRep+Interval ≤ today」（0xd586c0）→ 跳过
        已在结果队列 → 跳过
        0xb81280 → 受保护 → 跳过
        进结果队列，已推迟数 + 1（模拟也算）
        +0x13 == 0 → 0xd5c9c0 写日期
+0x05 ≠ 0 且 剩余 > N → 第二遍，+0x06 = 1（铺开分支），同样的停止条件
```

一般规则：按成功推迟的计数停止，第一遍后剩余仍 > N 就跑第二遍补足。只在没有跳过、没有保护的情况下，结果才等于「推迟排序后列表前面的那批（即 PQueue 队尾那批），留下列表末尾、也就是 PQueue 队首的 N 个」。
🧪 排序方向（第八轮定稿）：从队尾往前推。运行时传给逐篇推迟的优先级依次是 100、96.4、92.9 … 32.1（每步 100/28），留下队首最重要的 N 篇。参考实现 `run_postpone` 默认 `reverse=True`。比较函数 `0xb02fd0` / `0xb03030` 没拆，不再追。
🧪 第六轮：自动推迟时 +0x05 = 1、N = 50（§5.1）；逾期 24 篇，第一篇进循环就因 24 − 0 ≤ 50 停下。停止条件在调 `0xb81850` 之前判断。

### 5.6 逐元素推迟天数 `0xb81280` ✅（裁决 10）

```
base = max(today − LastRep, Interval, 1)
类别: etype==1 → item；etype ∈ {0,2,4} → topic；其他 → other（G包 §8.5）
(lo, hi) = item: (+0x1c, +0x18)；topic 与 other: (+0x1e, +0x1a)

铺开分支（+0x06 ≠ 0，helper 0xb81140）:       # 不做保护检查，不随机
    extra = lo + R((hi − lo)·prio/100)
    return extra, (base + extra)/base

保护（任一成立 → 跳过）:
    item : +0x20≠0 | base ≥ +0x22 | FI < +0x2a | 计数35 ≥ +0x33 | +0x35 > prio（0xb81499）
    topic: +0x21≠0 | base ≥ +0x26 | AF ≤ +0x2b | 计数35 ≥ +0x34 | +0x3d > prio（0xb81539）
           # AF 比较：0xb81518 xmm1 = 阈值；0xb81520 ucomisd xmm1,xmm0；jb 不保护；mov dil,1 保护
           # AF 或阈值为 NaN：无序比较 CF=1 → jb 跳走 → 不保护
    other: 无保护
    prio 为 NaN 时「阈值 > prio」不成立 → 不受保护
mult = item: 1 + w(+0x14)/100；topic: 1 + w(+0x16)/100；other: 1.01（0xb8141e）
extra = R(base·mult) − base                          # 减的是 base
extra = R(2·extra·sqrt(prio/100))                    # 无条件；对话框「按优先级调」的勾没接线（补查裁决 Q2）
extra = max(extra, 1)
item/topic: extra = clamp(extra, lo, hi)；other 不钳
extra > 200 → 只弹警告
+0x13 == 0: extra = max(R(disperse(extra, extra·0.5)), 1)
return extra, ratio = (base + extra)/base
```

- 「优先级越高推得越少」来自 sqrt 项；「阈值 > prio 不推迟」是另一道截断。两条都成立。
- 对话框说的「累计延迟超过间隔 x% 不推迟」在代码里不存在，它实际就是上面的优先级阈值。出厂值 item 6 / topic 3（§5.1 出厂表）；DFM 文本里的 5 只是旧默认文字。
- prio 用优先级定稿 §4.2 `get_priority` 的结果（count<2 时恒 0.0、缺席自修复等边界照那边）。
- 🧪 **第八轮逐篇定稿**：原版 19 篇的运行时优先级、乘倍率取整后、钳后、两个随机数、抖动返回、最终天数全部记下，按上面公式逐篇回代 19/19 一致，抖动返回的 double 误差为 0（向量 `#10 第八轮`，证据 `逆向证据/自动推迟_2026-10-19/test1快照分析.md` 末节）。prio 就是 PQueue 百分位（100 = 队尾）。
- ❓ `0xb7edb0`（+0x0f≠1 时在保护判断前调用）改了什么。other 类的 etype 集合取自 G 包，裁决未单列。

### 5.7 写回日期 `0xd5c9c0 → 0xd62f00 → 0xd82aa0 → 0xd8aff0` ✅（裁决 12）

```
0xd5c9c0(id, ratio):
    status(+0x01) ≠ 1 → 返回，不写
    edi = max(today − LastRep, Interval)
    iv = R(edi·ratio);  iv ≤ edi → iv = edi + 1;  iv = min(iv, 44530)
    newDate = LastRep + iv

0xd82aa0（status == 1 分支）:
    0xd5e0d0 从当天名单删掉
    旧 = max(Interval, 1)
    newDate > LastRep: 新 = newDate − LastRep;  +0x22 = max(+0x22 × 新/旧, 1.0)
    否则:              新 = 1;  +0x22 = 1.0;  LastRep = newDate − 1
    Interval = 新
    新 > 旧（无符号）→ +0x35 += 1, +0x31 += 1
    不动 AF
    0xd8aff0(newDate)
```

- topic 和 item 走同一条链，topic 没有提前返回。
- 这条链上没有挪优先级。`0xc99b30` 的 div3 = 1 调用者是 `0xd66670`（`0xd66a35`），sched1 / Muse 记它为 ForceTopicRepetition，不在本链（`0xd5c9c0 → 0xd62f00 → 0xd82aa0`）上；它是哪个界面操作、自动 / 手动推迟会不会走到它 ❓，参考实现不接（公式见优先级定稿 §4.9，div3 时挪动量再 ÷3）。- 只在 edi == today − LastRep ≥ 1（此时 base == edi）且没碰到 44530 上限时，newDate = today + extra，至少是明天；碰到上限时 newDate = LastRep + 44530，可能 ≤ today（例：today=44530、LastRep=0、Interval=40000 → newDate=44530=today）。edi=0（LastRep=today、Interval=0）时 base 被抬到 1、extra=2，但写回按 edi=0 算 iv=0→1，newDate=today+1，不是 today+extra（例：today=100 → 101，不是 102）。
- 裁决 12 原文写「iv ≤ 旧间隔时改为旧+1」，两包都写 `edi`。推迟路径上 ratio > 1，两种写法结果一致，参考实现按 `edi`。
- ❓ newDate > 0xFFFF 的处理（M 写 `min(…, 0xFFFF)`，G 写抛错）；+0x31、+0x22 的含义；status ≠ 1 分支的 `0xd8edd0`。

---

## 6. 参考实现对照

| SPEC | `schedule.py` |
|---|---|
| §3.1 | `logical_today` |
| §3.2 | `new_element`、`new_topic_af`、`real48_to_float` |
| §3.3 | `length_af`、`new_extract_af`、`extract_afs` |
| §4.1–4.4 | `disperse`、`topic_next_interval`、`adjust_af`、`commit_topic_repetition`（挪位调 `../priority/priority.py` 的 `adjust_priority_by_interval`） |
| §5.2 | `Collection.collect` / `build_outstanding` / `advance_cursor` / `schedule_repetition` / `remove_repetition` |
| §5.3 | `AutoState`、`auto_postpone` |
| §5.4 | `delay_text_to_word`、`delay_word_to_mult` |
| §5.5 | `run_postpone` |
| §5.6 | `postpone_protected`、`postpone_extra` |
| §5.7 | `write_postponed_date`、`commit_new_date` |

---

## 7. 未经裁决的 M 包单方内容（存档，不实现）

下列结论只有 M 包给出（G 包对其中多数写「没拆 / 没找到 LEA」），裁决未覆盖。用之前要先复核。

| 主题 | M 包结论 | 出处 |
|---|---|---|
| 浏览器 Reschedule | `0xc7c4a0 → 0xc78fc0 → SetNextRep 0xd72780`：只写下次复习日，不碰间隔 / AF | M包 §6.1 |
| Ctrl+J | `ShiftRepetition 0xf0e660`：默认天数 = 原到期日 − today（下限 1）；下次日 = today + days；etype==0 时 `AF = 0xcf7800(AF, Interval, days, 0)` | M包 §6.2 |
| Later today | 在 drill 队列中只重排，否则 `ShiftRepetition(0,0)` | M包 §6.3 |
| Dismiss | status = 2，清零 Repetitions / Interval / LastRep / +0x22 / +0x35 等，优先级 100 | M包 §6.5 |
| Forget | `0xd86f50`：只把 +0x28 清零并移出 pending 队列 | M包 §6.6 |
| AF 钳制 | `ModifyAF 0xd5fab0`：NaN/0/1.0 → 1.01；>6.5 → 2.0；<1.01 → 1.01 | M包 §4.2 |
| 导入 AF | `0xbc5810` 给 1.3 或 f(L)；YouTube 自动摘录 3.0 | M包 §4.2 |
| 新摘录当天 | 进 drill / intact 队列，不进 Outstanding | M包 §4.3 |
| Mercy | 收 `[cursor, today+days−1]`；第 k 个元素 newDate = today + ceil(k/bucket) − 1，bucket = ceil(total/days)。G 包只核到 `0xd3d8b0` 的一次整数 idiv | M包 §9；G包 §10 |

---

## 8. 两包与裁决出入一览

| # | 被推翻 / 补全的说法 | 出处 | 裁决 |
|---|---|---|---|
| 1 | 新元素「不写 AF / 间隔 / 日期」，参考实现 AF = 0.0 | M包 §4.2 | 推翻：模板写 AF（3.5 或 1.2000000000007276），0x109>0 时写 LastRep（裁决 1，G 对） |
| 2 | topic 复习后的间隔「没找到」；`0xa0fbc0` 的 `(iv+U)·A` 算术 | G包 §6 | 作废：间隔就是 `0xe145a0`（裁决 3，M 对） |
| 3 | 未写复习时的 AF 调整 | G包 | 补全：`0xcf7800`（裁决 5，M 对） |
| 4 | disperse 用 `log2` | M包 §5.2 及其向量 | 推翻：`ln`（裁决 4，G 对）。M 的向量 22.14 作废，现为 21.48 |
| 5 | 今天的公式没有「0 → 1」 | M包 §2.2 | 补全（裁决 6，G 对；偏移沿用 M） |
| 6 | 推迟到未来后「仍留在 Outstanding」；`0xd8aff0` 不删 | M包 §7.3 | 作废：`0xd82aa0` 先删，`0xd8aff0` 只在 ≤ today 时加回（裁决 7，G 对） |
| 7 | 久未用关开关的条件漏了 `dl == 0` | M包 §8.1 | 补全（裁决 8，G 对） |
| 8 | 只有收集后的 ≤10 门 | G包 §8.1 | 补全：门 A（名单 ≤10）也存在（裁决 8）。M 两道门都写了 |
| 9 | 「留下 N 条」从哪头留 ❓；M 参考实现没有排序和配额 | G包 §8.3；M schedule.py | 定为：按 PQueue 位置降序（从队尾往前）逐篇推，无跳过、无保护时留下队首 N 个（裁决 9；方向第八轮实测定稿，§5.5） |
| 10 | `extra = R(daysSince·mult)`（减旧 days，普通路径为 0） | M包 §8.3 | 推翻：减的是 base（裁决 10，G 对） |
| 11 | topic「AF ≥ 阈值」跳过 | M包 §8.3 | 推翻：严格大于（裁决 10，G 对）。方向本身又被第 21 条推翻 |
| 12 | 优先级阈值比较「NaN 也保护」 | G包 §8.5 | 推翻：NaN 不受保护（裁决 10） |
| 13 | etype ≠ 1 一律按 topic | M包 §3.2 | 推翻：0/2/4 是 topic，其他用 1.01、不保护、不钳（裁决 10 + G包） |
| 14 | 铺开分支用 `today − LastRep`（可除零） | M包 §8.3 | 推翻：用 base = max(…, 1)（裁决 10） |
| 15 | 「累计延迟 5%」对应哪条比较 ❓ | G包 §8.3 | 定为：就是优先级阈值（裁决 10，M 对） |
| 16 | ItemDelay 的 word 是 1 还是 101 ❓ | M包 §8.3、§12 | 已解决：word = R((v−1)·100)，1.01 → 1（裁决 11） |
| 17 | 推迟「不递增 Postpones」「自增点未找到」「不改 Interval」 | M包 §8.6、§12 | 作废：间隔改为新日期 − LastRep，变长时 +0x35、+0x31 各 +1（裁决 12） |
| 18 | `0xd5c9c0` 对 topic 提前返回 | M包/sched7（M 已自纠） | 作废：只看 status 字节（裁决 12，G 对） |
| 19 | 摘录的 n 是「文本长度 L」 | M包 §4.1 | 降为 ❓：是某个字符串或数组的长度（裁决 2） |
| 20 | 新元素初始 AF「约 1.2000000000018」 | 裁决 1 手算值 | 以 struct 核得 1.2000000000007276 为准 |
| 21 | topic「AF > 阈值」跳过（严格大于） | 本稿旧版 §5.6、裁决 10 | 推翻：AF ≤ 阈值保护（补查裁决 Q2，`0xb81520`） |
| 22 | 档位步进器 `tier_step_adjust`：间隔变长时 P 变小（往前挪），没有保底挪 1 格、没有上限 100，「可不实现」 | 优先级定稿旧版 §10 | 推翻：方向相反，改为 `adjust_priority_by_interval`（补查裁决 Q3） |
| 23 | 新 topic 的 AF 就是模板 1.2 | 本稿旧版 §3.2 | 补全：模板之后按正文长度 `0xcf73f0(L)` 重写（补查裁决 Q4） |
| 24 | 出厂 +0x05 = 0（按参数）、Skip items 勾，所以自动推迟不看 Skip top N | 本稿旧版 §5.1、§10 第 18–22 条 | 推翻：那是对话框显示的值；自动推迟实际用 +0x05 = 1、N = 50、Skip items 不勾（第六轮调试器转储，§5.1） |

---

## 9. 运行实测状态与操作指南 🧪（取自 M包 §11 / sched8）

逆向阶段没有运行实测；界面实测见文首与 `../measurements/`，结论已按补查裁决并进各节。M 包已试到头的路径：

- wine-9.0 + Xvfb 下 `sm20.exe` 无头启动稳定（存活 18s+，基址恒 `0x400000`）；
- 无 GUI 自动化（xdotool 未装），点不开学习窗 / Postpone 对话框；
- winedbg 挂不上（error 87，容器 ptrace/seccomp 限制）；
- 把 SM18 样本集合放到 ini 记录的路径，`WINEDEBUG=+file` 跑约 20 秒，3.4MB trace 里零次触碰 systems 目录：程序在该环境走不到打开集合这一步。
- G 包：本机执行该 PE，x86_64 探测返回 `bad CPU type`。

**真机实测路径（留给复核者）**：Windows 上用 Cheat Engine（或 x64dbg）按下表下断点（更正 10-19：PE 头开着 DYNAMIC_BASE，Wine 下恰好加载在 `0x400000`，Windows 上会被 ASLR 挪走，地址要按「实际基址 + RVA」换算；而且云电脑上装的 sm20.exe 和这份不是同一个文件，两份的 SHA-256 见仓库 README），把 `test_vectors.py` 的「公式推演」逐条换成「原版实测」：

| 断点 | 看什么 | 对应向量 |
|---|---|---|
| `0xe145a0` 入口 / 返回 | 入参旧间隔、mode；返回 ax | #3 |
| `0xcf9e20` 入口 / 返回 | xmm0 = x、xmm1 = d；返回 xmm0；两次 `0x40a390` 的返回值 | #4 |
| `0xd7ca60` | r8d、flag；`0xd7cee5` 处传给 `0xcf7800` 的新间隔 | #3 #5 |
| `0xcf7800` 入口 / 返回 | &AF 指向的值前后对比 | #5 |
| `0xd60450` | `d604aa` 的 today 与 +0x4c5；`d60649` 名单个数；`d60719` 逾期个数 | #8 |
| `0xb81280` | `b81499` / `b81539` 比较的阈值与 prio；`b8159c` 后的 extra | #10 |
| `0xd5c9c0` / `0xd82aa0` | iv、newDate；写回前后 +0x10、+0x31、+0x35 | #12 |

换成实测值后，把对应向量的第一个参数改为 `实测`。

---

## 10. 未确认清单 ❓

1. 类型字节 1 是否就是 item（裁决 1）。
2. 新元素 RepDates 那一格由谁写、第一个复习日是哪天（G包 §4.4）。
3. 摘录 n：已定为 `0xf9c9a0` 清洗后的 UTF-16 长度（§3.3）；清洗里剥标签、实体表、首尾去换行三步只有 G4 写了；`0xf3ca90` 谁父谁子。
4. `0xe145a0` 的 mode 字节（`[[0x1163a28]+0x23f1]`）的产品含义（裁决 3）。
5. 今天：epoch / base 的值、缓存失效逻辑、`[coll+0x118]` 的默认值；G 包 `<0 → 1` 那一支（裁决 6）。
6. 自动推迟写 `+0x4c5` 的对象（全局 `0x12be400`）与读的对象是否同一个（裁决 8）。
7. `[coll+0x109]` 的含义、`[coll+0x4d0]` 的写入点。
8. 执行器排序方向：已定，从队尾往前推（第八轮，§5.5）。
9. `0xb7edb0` 在保护判断前改了什么。
10. 「other」类 etype 的确切集合（参考实现按 G：非 1 且非 0/2/4）。
11. `+0x31`、`+0x22` 的含义；`+0x35` 是不是 TotalPostpones（裁决 5、12）。
12. 放回当天名单的位置（`0x97b0a0`）；DayBurden `0xd5db60` 的确切返回值；游标挪动对本次收集下界是否生效；比游标更早的逾期元素有无别的入口。
13. newDate > 0xFFFF 的处理；status ≠ 1 时 `0xd8edd0` 怎么改日期。
14. 随机数本体 `0x40a350` 与种子。
15. AF 写回 Real48 时的精度损失对后续计算的影响（参考实现按 double 不截精度）。
16. §7 全部 M 包单方内容。
17. 新建 topic 的 AF：已定（见补查裁决 Q4，§3.2）。仍 ❓：间隔 1 / `Auto interval1` 那一步的代码路径（G4 说 `0xd73420 → 0xd8aff0`，未核）；`0xbc5949`、`0xf0a509` 两个调用者没核。
18–21. 推迟对话框：已定（见补查裁决 Q1/Q2，§5.1、§5.6）。控件 → 偏移已对上；Skip items / Skip topics 勾上 = 整类不推迟（出厂 item 整类不推）；topic 保护是 AF ≤ 阈值（旧稿写反，§8 第 21 条）；按 FI / 按 AF 两个勾存 +0x45 / +0x46、执行器不读，按优先级调没接线、sqrt 无条件。「出厂 +0x05 = 0、item 整类不推」只是对话框显示，自动推迟运行时不是这样（§8 第 24 条）。
22. 已定 🧪（第六轮调试器）：25 个逾期的元素一个都没被自动推迟，原因是自动推迟运行时用的是 Skip top N、N = 50，逾期不到 50 篇第一篇就停（§5.1、§5.5）。前面各道门（开关、盖章、10 天门、门 A、游标、收集器、门 B）运行时全过。早先「Skip top N 已排除」是看了对话框的灰色单选，看错了对象。每篇推几天：第八轮已逐篇验证，见 §5.6。
23. 复习 topic 后在优先级队列里往后挪：已定（见补查裁决 Q3，§4.4、优先级定稿 §4.9）。推迟路径 `0xd66670`（div3 = 1）是哪个操作 ❓（§5.7）。
24. 新建 topic 的 AF 随正文长度变：已定（见补查裁决 Q4）。T1 的 1.297（L ≈ 2991）当时正文来源 ❓；新 item 实测 AF 3.920、间隔 4（G4 单方说是首次默认打分 5 按 0.6/0.4 混合，未核）❓。
