# SuperMemo 20 算法逆向复刻

[English](README.md) | 简体中文

本仓库用自己的话重新描述了 **SuperMemo 20** 里服务 incremental reading 的三个算法：

1. **优先级队列**：优先级怎么存、默认值、摘录提权、批量改、复习后挪位、每日队列排序。
2. **文章 / 摘录（topic）排期**：新元素的初始 A-Factor 和间隔、摘录的 A-Factor、topic 复习后的新间隔与 A-Factor 调整。
3. **自动推迟**：触发条件、门、保护、每篇推几天、写回。

对象：SuperMemo 20，Build 20.00.34。用到了两份 `sm20.exe`：

| 用途 | SHA-256 |
|---|---|
| 静态反汇编（规格里的地址都指这份） | `c58f89df51b6cf118ed8ca76a52017e2e7a82aa20ce3656d6e23d5801f0ccf68` |
| Windows 上的运行实测 | `D01F16976E10F68FDD2E0503E87BEAF74D65481BB8456E69FB1CD5DAF9AAD7C0` |

两份文件不一样。我们用到的函数指令相同，但地址整体平移了，所以一份里的地址不能拿到另一份里用。两份都开着 ASLR。

本项目是**非官方**的，与 SuperMemo World 没有任何关系，**不含任何 SuperMemo 代码或二进制**。

## 目录

| 位置 | 内容 |
|---|---|
| `priority/SPEC.md` | 优先级算法规格 |
| `priority/priority.py` | 参考实现 |
| `priority/test_vectors.py` | 断言测试 |
| `schedule/SPEC.md` | 排期与自动推迟规格 |
| `schedule/schedule.py` | 参考实现（会引用 `../priority/priority.py`） |
| `schedule/test_vectors.py` | 断言测试（245 条向量） |
| `measurements/` | 第一到三轮界面实测：剧本 `实测提示词_*.md`、原始读数 `results_*.jsonl`、报告 `实测报告_*.md` |

## 怎么逆向出来的

1. **静态反汇编。** `sm20.exe` 是 64 位 Delphi PE。我们用基于 `capstone`、`pefile` 的小脚本做反汇编、找调用者、在两份 exe 之间匹配函数。几个 AI 逆向代理各自独立写出规格。排期部分有两份完整的规格包（规格里叫 M 包、G 包），逐条比对。两包有分歧的地方，再派四路代理各自对着反汇编裁决（规格里的「裁决 N」），关键指令由人工抽查。优先级规格也经过了同样的交叉审计。被推翻的旧说法集中列在 `schedule/SPEC.md` §8。
2. **界面实测（第一到三轮）。** 在 Windows 上用原版跑一个小测试集合。由 AI 代理用 computer use 照固定剧本操作，把界面上的数字原样抄下来。两次操作之间的系统日期由人来改。剧本、原始读数和报告都在 `measurements/`。读数和规格对不上的地方，会回到反汇编重新核查（规格里的「补查裁决」）。
3. **调试器取证（第四到九轮）。** 在正在运行的原版进程上挂「只记录、不暂停」的断点。第四轮用 x64dbg，中途中断了；之后几轮改用 Python + ctypes 写的调试脚本。这几轮记录了自动推迟从触发到写回的全过程，以及复习后新间隔和 A-Factor 的计算。中间值和原始随机数也都记了下来，所以公式能逐位回代核对。调试器日志和分析记录没有放进本仓库，它们的结论已经写进规格。

在此之前试过用 Wine 无头运行，但打不开集合（`schedule/SPEC.md` §9）。所有运行时证据都来自真实的 Windows。

## 怎么用

代码只需要 Python 3 和标准库（`math`、`struct`、`dataclasses`、`pathlib`、`unittest.mock`），在 Python 3.14 上测过。

```bash
python3 -I priority/test_vectors.py   # 输出 all vectors passed
python3 -I schedule/test_vectors.py   # 输出 ALL PASSED: 245 条
```

退出码为 0 表示全部通过，有任何一条失败都会以非 0 退出。

### 主要入口

| 模块 | 函数 | 规格 |
|---|---|---|
| `priority.py` | `PriorityQueue`（`get_priority`、`set_priority`、`add_new_element`、`change_priority_by`） | §3–§4 |
| `priority.py` | `create_extract`、`spread_priority` | §5 |
| `priority.py` | `adjust_priority_by_interval`（复习后挪位） | §4.9 |
| `priority.py` | `batch_apply` | §6 |
| `priority.py` | `build_daily_queue`（`randomized_draw`、`interleave`） | §8 |
| `schedule.py` | `new_element`、`new_topic_af`、`extract_afs` | §3 |
| `schedule.py` | `topic_next_interval`、`adjust_af`、`commit_topic_repetition` | §4 |
| `schedule.py` | `PostponeSettings.auto_runtime()`、`postpone_extra`、`run_postpone`、`auto_postpone` | §5 |

最小用例。在仓库根目录用 `PYTHONPATH=priority:schedule python3 example.py` 运行：

```python
import random
from priority import PriorityQueue
from schedule import extract_afs, topic_next_interval, adjust_af

q = PriorityQueue(range(1, 11))       # 10 个元素，元素 1 在队首
q.add_new_element(99)                 # 新元素按默认优先级 5.0 入队
print(q.locate(99), q.get_priority(99))          # -> 1 0.0（队列小，落到队首）

print(extract_afs(1.5, 200))          # (新摘录 AF, 父元素 AF) -> (1.583173076923077, 1.4755)

rng = random.Random(0).random         # 任何 [0,1) 随机源都行；原版用 Delphi Random
new_iv = topic_next_interval(old=3, af=1.8, mode=0, rng=rng)
print(new_iv, adjust_af(1.8, 3, new_iv, hard=False))   # -> 4 1.8644897959183675
```

随机数（`rand01` / `rng`）和「今天」一律由参数传入，代码不读系统时钟。

### 规格里的标记

| 标记 | 含义 |
|---|---|
| ✅ | 静态闭环：给出了地址和指令，可以自己复核 |
| 🧪 | 在原版里实测过（界面读数或调试器记录） |
| ❓ | 没定下来，正文写明卡在哪 |

### 两类测试向量

- **原版实测**：数字是 SuperMemo 自己跑出来的。**不许**为了让实现通过去改它。
- **公式推演**：数字是按反汇编出的指令算出来的，裁决变了可以跟着更新。

## 哪些已经和原版对上

| 算法 | 结论 | 证据 |
|---|---|---|
| 优先级 | 优先级 = 队列位置等距；新元素进队首附近；摘录插在父元素后一位；改成 50 后的落位；排序滑杆默认值 | 第一轮，11 个元素的集合，与参考实现逐位吻合 |
| 优先级 | 手动改优先级：先移出，再按 `R(P/100·count')+1` 放回，遇 .5 取偶 | 第二轮，26 个元素的队列，改了 15 次，15/15 吻合，含 .5 的情况 |
| 优先级 | 复习后按间隔挪位（§4.9） | 第二轮 5 天数据回放。只复习一篇的那几天逐位吻合；复习多篇的那几天能在某种复习顺序下复现（当时没记录顺序） |
| 排期 | 摘录后父元素 A-Factor 的衰减 | 1.377 → 1.341 → 1.325 → 1.309，逐位吻合 |
| 排期 | 新摘录的 A-Factor | 4 个摘录，三位小数内吻合 |
| 排期 | topic 复习后调整 A-Factor | 第二轮界面读数 26/26；第九轮调试器 5/5 逐位吻合 |
| 排期 | topic 复习后的新间隔（公式、输入、两个随机数、结果） | 第九轮调试器，15/15 次调用逐位吻合 |
| 排期 | 逾期天数不参与新间隔的计算 | 第二轮界面实测（故意晚复习） |
| 排期 | 新 topic 的 A-Factor 按建立时的正文长度定 | 第二轮：100 字 → 1.75，9/9 篇；第三轮：300 字 → 1.550，正好吻合 |
| 自动推迟 | 运行时实际用的设置（与对话框里显示的不同）以及各道门 | 第六轮调试器转储了 71 字节的设置块 |
| 自动推迟 | 每篇推几天（优先级、倍率、钳制、两个随机数、抖动、结果） | 第八轮调试器，19/19 篇逐位回代一致，抖动结果的 double 误差为 0 |

确切出处见各规格的文首，以及各节里标 🧪 的说明。

## 已知局限与缺陷

- **新间隔只实测过「旧间隔 = 1」这一支。** 这一支里 `d` 被钳到 4。更大的间隔只有静态分析做依据。
- **Delphi `Random` 的 LCG 本体（`0x40a350`）和种子没有拆。** 能对上随机数的分布，但对不上原版实际生成的随机序列。
- **没有模拟 Real48 的精度损失。** 原版的 A-Factor 以 6 字节 Real48 存盘，参考实现全程用 double，长链计算后末几位可能有偏差。
- **优先级有两处没实测过**：item 打分后的优先级微调（§9），以及 Ctrl+Shift+Up/Down。两处都只有静态依据。
- **间隔函数里的 `mode` 字节**（`[[0x1163a28]+0x23f1]`）产品含义不明。mode 5、6 的减半分支没有在实测中走到过。
- **自动推迟的设置。** 运行时设置块是从一个从没在推迟对话框里点过「确定」的集合中转储的。在对话框里点了确定之后，自动推迟会不会改用对话框的值，以及运行时块从哪里初始化，都还不知道。
- **每日队列。** Outstanding 队列由谁构建、被推迟到今天的元素怎么进队、当天中途新增的元素插在哪，都还不知道。
- **摘录长度 `n`。** 清洗步骤里有几步（剥标签、实体表、去首尾换行）只有一个来源，选区里 HTML 多的时候，`n` 可能差几个字符。
- **新建 topic 时会被设成间隔 1、复习次数 1。** 这一点实测看到了，但没有追到代码路径，参考实现也没有模拟。
- **复习后挪位在多篇复习的那几天。** 当时没记录复习顺序，所以只能说明「能复现」，不能说唯一确认。
- **测试集合很小。** 只有 11 到 26 个元素，一个集合、一个版本。大队列下才会出现的效应（挪位粒度、20 档分布等）都没有在运行时验证过。
- **只有单方来源、没经裁决的内容没有实现**：Reschedule、Ctrl+J、Dismiss、Mercy 等（`schedule/SPEC.md` §7）。
- **不在范围内**：item 的 SM-18/20 记忆算法。
- 完整的未定清单见 `priority/SPEC.md` §13 和 `schedule/SPEC.md` §10。

## 欢迎贡献

证据最薄的地方最需要帮忙：

- **拿自己的集合实测。** 大间隔、大队列、item 打分微调、Ctrl+Shift+Up/Down、在对话框点过确定后的推迟设置，都还没定。`measurements/` 里的剧本可以当格式参考：照固定剧本操作，数字原样抄下来，操作的人不做任何推算。
- **把「公式推演」向量换成「原版实测」。** 在原版上用断点重新取一遍数。`schedule/SPEC.md` §9 列了建议的断点位置。
- **补 ❓ 项。** 请给出地址、指令，以及你是怎么核对的。

提 issue 或 PR 时请附上：

1. SuperMemo 的版本号和 `sm20.exe` 的 SHA-256。
2. 涉及规格的哪一节，或哪一条 ❓。
3. 证据：原始读数或断点日志；如果是静态结论，附上地址和指令清单。
4. 改代码的话，`test_vectors.py` 要能通过。不许为了让代码通过去改「原版实测」向量。

## 免责声明

本仓库仅用于互操作与研究。SuperMemo 是 SuperMemo World 的商标。本仓库不含 SuperMemo 的源代码或二进制，所有内容都是我们对观察到的行为所做的描述。

## 许可

MIT，见 [LICENSE](LICENSE)。
