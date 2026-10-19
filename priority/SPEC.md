# SuperMemo 20 优先级算法 — 复刻规格

> **注**：文中引用的 `逆向证据/`、调试器报告等原始记录未随本仓库公开，结论已并入正文。

> 用途：照此规格可独立实现与 SM20 行为一致的优先级系统（语言无关；附 Python 参考实现）。
> 证据来源：`逆向证据/SM20_Priority_Algorithm.md`（逆向全记录，prio1–6、verify_* 同目录）与 `逆向证据/旧版规格_Grok审计批注.md` §12（外部审计）。本定稿以包内最新规格为底本，按三方核过反汇编的定案修订。
> 参考实现：同目录 `priority.py`（标准库 only）；断言测试：同目录 `test_vectors.py`（`python3 -I test_vectors.py`，失败即非 0 退出）。
> 约定：✅ = 原版实测行为，必须照做；⚠️ = 原版未定/有边界，规格给出处理方式；「未确认」汇总在文末 §13。

---

> **界面实测（2026-10-19，`../measurements/实测报告_第一轮.md`）**：§4.1 优先级 = 位置等距、§4.3 改成 50 后的落位、§4.7 新元素进队首附近、§5 摘录插在父元素后一位（`enqueue_first`）、§8.3 排序滑杆默认值，在 11 个元素的新集合上与参考实现逐位吻合。第二轮在 26 个元素上手动改 15 次优先级，落位全部吻合，含遇 .5 取偶（`实测报告_第二轮.md`）。打分后微调（§9）和 Ctrl+Shift+Up/Down 还没测到。复习 topic 后按间隔挪位（§4.9）经补查裁决（`../schedule/逆向证据/补查_2026-10-19/裁决.md` Q3）定稿，第二轮 5 天数据回放全部复现（向量 T17）。

## 1. 设计核心（先立模型，再写代码）

1. **优先级不存数值，只存顺序。** 系统维护一条全局有序队列 `PQueue`，存元素 id，队首 = 最高优先级。元素的优先级百分位是读时由位置算出的派生量。
2. 数值语义：`P ∈ [0.0, 100.0]`，float（IEEE754 double）。**0 = 最高，100 = 最低**，全规格一致，不要反转。
3. 一切"改优先级"最终都收敛到一个原语：`set_priority(el, P)` = 把 el 从队列删掉、按 P 换算出的新位置插回去。其他元素因此被挤位、百分位读数随之漂移——这是原版行为，不是 bug。
4. 全局设置（默认值）：`defaultPriority = 5.0`；`itemFactor = 8.0`；`topicFactor = 12.0`；`proportionTopics = 5.0`（%）。

## 2. 数值约定 ✅

| 约定 | 定义 |
|------|------|
| `Round(x)` | 四舍六入五成双（round-half-to-even）✅ **已实测**（2026-10-18 复核）：0x40c5d0 函数体只有一条 `cvtsd2si rax,xmm0`，把其机器码在默认 MXCSR 下实际执行：4.5→4、5.5→6、2.5→2、−2.5→−2、4.4→4、4.6→5。**必须用 half-even**；用 half-up（如 `int(x+0.5)`）会在恰 .5 时与原版差 1 位（见测试向量 T13）。Python 内置 `round()` 正是此语义 |
| `trunc(x)` | 向零取整 |
| `clamp(x, lo, hi)` | 小于 lo 取 lo，大于 hi 取 hi |
| `rand01()` | [0, 1) 均匀随机。原版 PRNG 本体未解析，任何标准均匀源行为等价。实现时应可注入（便于测试） |
| 浮点 | 全部运算用 double，不要用 float32 中转 |

## 3. 数据结构

```
PriorityQueue:
    items: List[ElementId]        # items[0] = 队首 = 最高优先级；位置 pos = 下标+1（1-based）

Element:                          # 元素本体只需要 id；不需要 priority 字段
    id: int
```
可选优化：另维护 `id → 下标` 索引加速 locate（原版是线性查找，行为无区别）。

持久化：把 `items` 数组顺序存盘即可（原版存为 collection 的 PQueue 流，文件 `\info\priority.sub`，字节格式未扒——用你自己的格式）。

## 4. 基本操作（逐个给规格）

### 4.1 pos_to_priority(pos, count) ✅ `0xc9a680`

```
if pos < 2: return 0.0
return (pos - 1) / (count - 1) * 100.0
```

### 4.2 get_priority(el) ✅ `0xc99450`

```
count = len(queue)
if count < 2: return 0.0               # ✅ 复核（0xc994a1 jl）：count<2 时不查位置、不修复，直接 0.0。
                                       # 后果：队列只有 1 个元素时，连它自己读出来也是 0.0（"假 0"），不是 100
pos = locate(el)                       # 1-based；不在队列 = 0
if pos == 0:
    if is_deleted(el):                 # IsDeleted 0xd51690：id==0 或状态字节==3
        return 0.0                     # 已删除：跳过修复
    set_priority(el, 0.0)              # 否则自修复置顶（原版先弹框提示）
    return 0.0
return pos_to_priority(pos, count)
```
参考实现参数为 `is_deleted`（旧版 `is_valid` 改名并取反）。
补充（✅ 复核）：set_priority 对 count<2 的队列**没有**短路，照常删除+插入（count=0 时 newPos=1 追加），所以缺席元素的实际"修复"靠写路径，不靠读路径。

### 4.3 set_priority(el, P) ✅ `0xc9b210`

```
if not 0xd624c0(el): 弹框; return      # 元素无效：原版弹框，不做任何改动
P = clamp(P, 0.0, 100.0)
remove el from queue if present        # 必须先删
if P == 100.0:
    append el at tail                  # 直接追加
else:
    count' = len(queue)                # 删除后的个数
    newPos = Round_half_even(P / 100.0 * count') + 1   # 1-based
    if newPos > count': append el at tail              # 0xe24a50 → 0xe239b0
    else: insert el at position newPos # 其后元素全部后移一位
```

参考实现：`PriorityQueue(items, is_valid=lambda el: True)` 注入 `0xd624c0` 判定，判无效时 set_priority 直接 return、队列不变（向量 T3b）。

读和写的换算互为反函数：读是 `P = (pos-1)/(count-1)*100`，写是 `pos = P/100*count' + 1`，而 `count' = 放回后总数 − 1`，两式代入即互逆。set 完立刻 get 读回值和写入值对不上（T3），只是写路径取整到整数位置造成的。

### 4.4 priority_to_index(P, count) ✅ `0xc99880`（排序/档位用）

```
return Round(P / 100.0 * (count - 1)) + 1      # 注意这里是 count-1，与 4.3 不同
```

### 4.5 priority_to_bucket20(P) ✅ `0xc99380`

```
if P < 0.0001: return 1
return clamp(Round(20.0 * (P / 100.0) ** 0.25), 1, 20)
```
用途：AutoPostponeSort 的 20 桶分布、FI-vs-Priority 统计。普通业务可不实现。

### 4.6 change_priority_by(el, delta) ✅ `0xd71320`

```
if abs(delta) < 1e-5: return           # 微量忽略（守卫）
set_priority(el, clamp(get_priority(el) + delta, 0.0, 100.0))
```
注：实际位移受队列粒度限制——P 变化不足以跨过一个位置时，元素不动、读回值不变（向量 T5）。

### 4.7 add_new_element(el) ✅ `0xd7e9b0`

```
set_priority(el, defaultPriority)      # 默认 5.0；item/topic/extract 相同
```
覆盖面（✅ 2026-10-18 复核，23 个直接调用者已枚举）：普通新建、extract/cloze、**复制（Duplicate）**、**导入**（Import / Import All / Q&A-XML 三条链逐跳验证）全部经过本函数——不存在绕过它、且已证实的创建路径。两个例外注记：① **UndeleteElement（`0xd64ba0`）**不走这里：它重建元素记录后直接 `set_priority(el, 33.0)` 入队；② 两处**未确认**：ImportFromExcel 的创建机制（静态调用图未命中，可能走虚调用）；`0xd22940` 有一条直接建记录的分支，静态扫描未见其调 set_priority，若成立则该元素会在队列缺席、靠 §4.2 自修复补入。首次入队机制全二进制只有 set_priority 一种。

### 4.8 first() / pop() ✅ `0xe233e0` / `0xe23390`

```
first() = items[0]                     # peek 队首
pop()   = remove and return items[0]   # 取下一个待学元素用
```

### 4.9 adjust_priority_by_interval(el, old_iv, new_iv, div3) ✅ + 🧪 `0xc99b30`

```
old_iv = max(1, old_iv)
if new_iv == old_iv: return                       # 不写
N = len(queue);  P = get_priority(el);  pos = priority_to_index(P, N)
r = min(old_iv, new_iv) / max(old_iv, new_iv)
d = 80 * (1 − r);  if div3: d = d / 3
f = (100 − d) / 100
P' = (new_iv < old_iv) ? P·f : min(100, P / f)    # 间隔变短往队首挪，变长往队尾挪
if priority_to_index(P', N) == pos:               # 落位没变：朝该方向保底挪 1 格
    pos = (new_iv < old_iv) ? max(1, pos − 1) : min(N, pos + 1)
    P' = pos_to_priority(pos, N)
set_priority(el, P')
```

调用点：
- topic 复习提交 `0xd7ca60`（`0xd7cf1c`）：div3 = 0，旧间隔与未截断的新间隔，在调 AF 之后（排期复刻指南 §4.4）。
- `0xd66670`（`0xd66a35`）：div3 = 1。G4 称它为推迟单元素，sched1 记为 ForceTopicRepetition；它不在推迟写回链 `0xd5c9c0 → 0xd82aa0` 上，对应哪个界面操作 ❓（排期复刻指南 §5.7）。
- `0xf0e660` 也调它，没展开 ❓。

第 1 位的元素间隔变长：P 仍是 0、落位不变，保底挪到第 2 位；同一天下一篇从第 1 位复习时又会把它换回第 1 位，所以界面上看像「一直停在第 1 位」。
🧪 第二轮实测 5 天（回放 `../schedule/逆向证据/补查_2026-10-19/q3_复习后挪位_回放.py`）：单篇的两天逐位吻合；多篇的天按某种复习顺序都能逐位复现（向量 T17）。

## 5. Extract 创建时的优先级 ✅

两种时序，参考实现 `create_extract(..., order=)` 取 `'enqueue_first'` 或 `'parent_first'`。

**enqueue_first**：ExtractSelection `0xf3a640`、WebExtract `0xf3ca90`，即菜单里的各种摘录。

```
add_new_element(new_el)                          # 先入队，默认 5.0
P = get_priority(parent)                         # 在新元素入队之后读（父位置可能已被挤动）
set_priority(parent, P * 0.995)
if spread:  set_priority(new_el, spread(P * 0.995, text_len, rand01))
```

**parent_first**：GenerateExtractChild `0xf25670`（自动生成的子摘录，对应用户的哪个操作「未确认」）、GeneratePictureExtractChild `0xf25bd0`（图片摘录定时器）。

```
P = get_priority(parent)
set_priority(parent, P * 0.995)
add_new_element(new_el)
set_priority(new_el, spread(P * 0.995, text_len, rand01))   # 经 FinishGeneratedExtractChild 0xf25ab0，无条件 spread
```

菜单参数表（经分发器 `0xf48c90` 传入的硬编码常量，不是用户选项）：

| 菜单 | mode | spread | dialog | arg5 |
|---|---|---|---|---|
| MIRememberExtract | 0 | 1 | 0 | 0 |
| MIQueueExtraction | 0 | 0 | 0 | 0 |
| MIScheduleExtract | 0 | 1 | 1 | 0 |
| MIExtractTask | 2 | 0 | 0 | 0 |
| MIExplainExtract | 0 | 1 | 0 | 1 |

- dialog=1 时，spread 之后弹出优先级对话框让用户手动定（只有 Schedule extract 这样）。
- arg5 的含义「未确认」。快捷键（DFM ShortCut，已核）：**Alt+X = MIRememberExtract**（0x8058，即普通「摘录」，走 enqueue_first + spread、不弹窗；用户实操也确认 Alt+X = 摘录），Alt+Shift+X = MIScheduleExtract（0xA058）。
- 不做 spread 时，父元素照样乘 0.995，新元素停在默认 5.0。
- 跳过对话框时，原版会对新元素连写两次同一个值，这是冗余操作（参考实现照写，结果与写一次相同）。
- 摘录路径里那段 `(x-1.01)*0.95+1.01` 是 A-factor 的调整，不是优先级，不在本规格范围内。

两种时序的差别见向量 T14（父在队首时父与新元素位置对调）；T8 上两种时序碰巧结果相同。

### spread(P, len, rand01) ✅ `0xc99a00`

```
t  = exp(1.7 * P ** 0.2)  if P > 0  else 0.0         # 自然指数 e；P**0.2 即 exp(0.2*ln P)
lo = P * 0.7
hi = t
# 原版另有 lo > t 时 lo=t, hi=t*1.3 的分支与 hi 的 [0,100] 钳制，
# 在合法 P∈[0,100] 下永不触发（交点 ≈118.5），可省略；参考实现保留以求忠实
result = lo + (hi - lo) * (len / (len + 100.0)) * rand01()
return clamp(result, 0.0, 100.0)
```
区间速查：P=5 → [3.5, 10.44]；P=31 → [21.7, 29.33]；P=50 → [35, 41.16]；P=100 → [70, 71.54]。
注意 P 小时上界 > P：高优先级父文章的 extract 可能比父更不重要，原版如此。

## 6. 批量改优先级（子集操作）✅ worker `0xd45e30`

参数：`change`（%）、`minPct`、`maxPct`，对话框默认值 min=1、max=50；Increase 的 change 默认 50、Decrease 默认 150。参数层钳制：change∈[0,1000]、min∈[0,99]、max∈[0.0001,100]、min>max 则交换；"不限制"时 min=0、max=100。参考实现在 `batch_apply` 入口做这一步规范化（向量 T13b）。

**状态字节**（`0xd71680` 读出的第 2 个字节，推定 0 待学 / 1 已记忆 / 2 已撤销 / 3 已删除，与 IsPending / IsMemorized / IsDismissed / IsDeleted 方法表对得上）：
- ==3（已删除）：整张跳过，**不占序号 k**（`0xd6d284` 在 `0xd6d2a1` 的 k+1 之前就跳走）；
- 0 或 1：写入新优先级；
- 其他（2）：占一个序号，但优先级不动（入口门 `0xd45e48`，掩码 `0x03`）。

参考实现 `batch_apply(..., status_of=..., is_deleted=...)`：`status_of(el)==3` 或 `is_deleted(el)` 任一为真即按已删除处理。

**执行顺序**：乘系数 → /100 → 上钳到 Max% → 下钳到 Min% → 防反向回退 → 尾部再上钳一次 Max% → set_priority。

```
increase(oldP):  t = oldP * change; t = t / 100
                 t = min(t, maxPct); t = max(t, minPct)
                 if t > oldP: t = oldP                      # 回退（0xd45ee9）
                 newP = min(t, maxPct)                      # 尾部再钳（0xd46013）
decrease(oldP):  同上，回退条件为 t < oldP（0xd45f4c）
spread_linear(k):          newP = min(minPct + (k - 1) * step, maxPct)
spread_proportional(oldP): newP = minPct                                       若 oldMax == oldMin
                           newP = minPct + (maxPct-minPct)*(oldP-oldMin)/(oldMax-oldMin)   否则
                           之后同样吃尾部上钳
```
算例：decrease，oldP=80、change=150、maxPct=50 → 120 → 上钳 50 → 50<80 回退到 80 → **尾部压到 50**（T13）。increase 回退后若 oldP < minPct，尾部不会把它抬回（尾部无下钳）。

**step**（`0xd461f0`）：`step = max((Max − Min) / (子集个数 − 1), 100 / 全队列个数)`，单位百分点；子集只有 1 个时 step=0。对话框里 StepEdit 填的是"位置数"，只用于反推 Max%（`Max% = pos_to_priority(minPos + (子集个数−1)×stepEdit)`，钳 ≤100）。

**取值时机**：oldP 每次现读（`0xd45e61` 调 get_priority），前面元素被挪动会影响后面的 oldP；oldMin/oldMax 在处理开始前预扫描一次定下（`0xd46360`：init min=100.0/max=0.0）。spread_proportional 在子集元素数 > (maxPos−minPos+1) 时弹警告中止：在写入任何元素之前检查，容不下则整批不动，参考实现 `batch_apply` 返回 False（正常完成返回 True）。minPos/maxPos 用 `priority_to_index(pct, 全队列个数)` 换算——这个换算函数是推定的，未确认（§13 #12）。

**处理序号 k**：从 1 起对每个未删除的被遍历元素递增，状态 2 的元素也占号（在 mode 分发之前 +1）；已删除的不占号（见上）。

**处理顺序与范围**：
- 菜单「线性 Spread」MISpreadPriorityClick（`0xc70a10`）用操作号 0x0A，名单由范围字节 `0x121d6a5` 决定：
  - 值为 2：用浏览器当前名单，即屏幕上从上到下的显示顺序。处理的是**浏览器里的整份名单**，与选中哪几张、点选顺序无关。点列排序会就地重排这份队列（`0xb778c0 → 0xca4610 → 0xe235b0`）。
  - 值为 0 或 1：从当前元素开始，沿记录里的「下一个」链接（目录 / 知识树顺序）走出一串，当前元素排第一。
- 浏览器上的 Spread 按钮（`0xb71610`）先把范围设成 2，再用操作号 0x0B（按原优先级比例重算，不按行号）。

参考实现：`batch_apply(queue, els, mode, ...)` 吃一个队列和一组元素，自己按上述规则循环；单值函数 `batch_modify_priority` 保留供测试用。

## 7. 手动改单个（UI 层换算）✅

- **对话框（TPriorityDlg）**：内部值就是 Double P。
  - Position 模式：用户输入位置 N → `P = pos_to_priority(N, 当前队列总数)`。
  - Percentile 模式：直接输入 P（显示最多四位小数）。
- **学习窗口 Increase/Decrease**：`change_priority_by(el, -0.1)` / `change_priority_by(el, +0.1)`（固定百分点，非百分比）。快捷键：**Ctrl+Shift+Up = 提高优先级（delta −0.1）**，**Ctrl+Shift+Down = 降低（delta +0.1）**。依据：DFM 里 TElWind 的 ShortCut 值 `0x6026` / `0x6028`。
- **浏览器 Increase/Decrease**：走 §6 的 increase/decrease（乘法），不要与上一条混用。

## 8. 每日复习队列的生成 ✅ 主体 `0xb28180`

输入：当天的 outstanding items 与 topics（各自带当前 P），设置 itemFactor/topicFactor/proportion。

### 8.1 排序键（只有 priority 一个键）

```
key(el) = Round_half_even((100.0 - P(el)) * 10000.0)   # 0xb283b2 调 0x40c5d0（cvtsd2si），不是 trunc
特例: el.id == 0 或 el 已删除（IsDeleted 0xd51690）→ P 按 100 计（key=0，排最后）
按 key 降序排列（⟺ P 升序，高优先级在前）；降序已用堆排序方向核实
⚠️ 原版用堆排序、不稳定：同 key 元素相对次序不保证。复刻用稳定排序可接受，差异仅在同 key 元素间
```
trunc 与 Round 在 `(100−P)×10000` 小数部分 ≥ .5 时差 1（向量 T15）。

### 8.2 随机化抽取 randomized_draw(sorted_list, factor, rand01) ✅

已核实，保持原样。下标用 trunc（`cvttsd2si`）。

```
handles = copy(sorted_list);  n0 = len(handles);  out = []
for i in 1..n0:
    ratio = (i - 1) / n0                       # 定长 n0，全程不变
    t1 = ratio ** (1.0 / factor)               # ratio=0 时 t1=0
    r1 = rand01()
    if t1 > r1:
        r2 = rand01();  r3 = rand01()
        idx = trunc( (r2 ** (1.0 / factor)) * len(handles) * r3 ) + 1   # len 为递减的剩余数；idx 为 1-based
    else:
        idx = 1
    out.append(handles[idx]);  remove handles[idx]
return out
```
要点：i=1 时 t1=0 恒不扰动——**最高优先级元素必第一个出**；r2/r3 只在扰动分支抽取（决定随机流的消耗顺序，复刻若要逐位对齐随机序列必须照此）。

### 8.3 因子来源 ✅

默认值 itemFactor=8.0、topicFactor=12.0、proportion=5.0 已确认，来自单元初始化 `0xb28b8b`；对话框打开时会反算成滑杆位置 47 / 62 / 5。滑杆（0–100 整数）换算 `trackbar_to_factor(pos)` `0xb27280`，公式已逐条指令核实：

```
pos == 100 → 1000.0;  pos == 0 → 0.001
x = sqrt(pos / 100.0)
x <= 0.5 → x + 0.5;   x > 0.5 → (x - 0.5) * 38.0 + 1.0
```
这三个值的持久化方式「未确认」。

### 8.4 穿插 interleave(items, topics, proportion) ✅

```
target = 1.0 - proportion / 100.0              # 默认 proportion=5 → target=0.95
a = b = 0                                      # 已取的 items / topics 数
loop:
    if target > a / (a + b + 1):  取 items 下一个; a++
    else:                         取 topics 下一个; b++
    任一列取完 → 强制取另一列
```
默认参数下第一个 topic 出现在第 20 位（向量 T9）。

### 8.5 流水线

```
daily_queue = interleave(
    randomized_draw(sort_by_key(items),  itemFactor,  rand01),
    randomized_draw(sort_by_key(topics), topicFactor, rand01),
    proportion)
```
Auto-sort 的确切形态（✅ 2026-10-18 复核）：它在学习启动时（`0xd73050 → 0xd65d30`）对 **Outstanding 队列对象本身就地重排**（r9b=1 路径，排完自动落盘 `\info\Outstanding.sub`），三道门控：开关开 && `LastAutoSort ≠ 今天` && 队列非空——**每天只跑一次**。手动 "Sort now" 是同一条排序路径、只是无门控。排序函数内部**不做日期过滤**，队列里有什么就排什么；学习消费从队首实时取（非快照）。两个边界如实标注：Outstanding 队列由谁构建（逾期是否在内、postpone 到今天的元素如何入队）**未确认**（构建者未定位）；当天中途新增元素往哪插**未确认**——确定的只有：中途新增不会触发重排，要重排只能手动 Sort now。另一条 r9b=0 路径（学习窗口对 `review.sub` 的排序）与本节流水线同主体、因子取 1.0。

## 9. 复习打分后自动调优先级 ✅

item 复习打分提交时调 `change_priority_by(el, delta)`（§4.6）：

| 分数 | delta |
|---|---|
| 3 | +0.05 |
| 4 | +0.15 |
| 5 | +0.3 |
| 其他 | 0（被 1e-5 守卫挡掉，不动） |

正数表示优先级略降（往队尾挪）。调用链：`0xf4beb0 → 0xd8b6c0 → 0xd6f5c0 → 0xd71320`；delta 表在 `0xc9a6f0`；protect 参数恒为 0。

跳过条件（任一即不调）：
- 记录里 AFactor（`+0x3a`）< 1e-5；
- 元素已删除；
- 学习窗口 mode 为 0 / 7 / 8；
- 间隔过短警报被取消（门 `0xceb1c0`，见下）：整单取消。

**写入链（✅ 这条路是活的）**：评分按钮 → `0xf174b0` → `0xf328d0(7)` → `0xf26800`。元素是 item（`0xd71680` 读到的种类字节 ==1，IsItem `0xd51810`）时调 `0xef89d0(form, 0xf48ab0 的结果)`；结果为 0 时 `0xef8a1b` 调 `0xd8f3e0`，把分数 `[form+0x229b]` 写进记录 `form+0x229c` 的 `+0x72`（写入指令 `0xd8f498`）。另一个写入者 `0xf2eb00` 在打分链上会被跳过（`0xf13b2a`）；有人据此判断「打分不改优先级」，但漏掉了 `0xef8a1b` 这条路，不成立。

**门 `0xceb1c0`**（只对分数 3、4、5 生效）：
- 全局字节 `0x12beba0` =「强制复习进行中」：ForceAndResume（`0xf170fc`）置 1，DrillNextElement（`0xf32cb9`）在切到下一张卡等操作时清 0。为 1 时跳过最后那道门，提交照常执行。
- `0xcec5a0` 判断要不要发「间隔过短警报」，不需要就直接放行。
- 需要警报时看 `0xcebe00`（对话框之类的虚调用返回值）：返回 0 则这次打分整单取消，分数和优先级都不变。
- 警报门槛来自运行时内存，数值「未确认」。

粒度提醒：队列不到约 1000 个元素时，+0.05 通常一格都挪不动（一格 = 100/(count−1) 个百分点，写路径还要取整）。

参考实现：`on_item_graded(queue, el, grade, afactor=1.0, is_deleted=..., window_mode=1, alarm_cancelled=False)`；`alarm_cancelled=True` 时什么都不做。

## 10. 明确不实现的部分 ❌

| 项 | 依据 |
|----|------|
| 优先级保护开关 | 不存在；"Priority protection" 只是统计图表页签 |
| 随机化优先级值 | 不存在；原版只有随机化浏览器显示序列 |
| GetNextPendingElement 空槽 | 不存在 |
| Postpone 按优先级改延迟 | 已定：推迟天数里 `R(2·extra·sqrt(prio/100))` 无条件执行，对话框「按优先级调」那个勾没接线（补查裁决 Q2）。公式见排期规格 §5.6，本稿不重写。Mercy 仍未证实，参考：perDay=ceil(total/days) |

## 11. 测试向量（`test_vectors.py` 全部写成断言）

**T1 pos_to_priority**：count=101：pos1→0.0，pos2→1.0，pos51→50.0，pos101→100.0；count=2：pos2→100.0；count=10：pos5→44.4444…

**T2 priority_to_index / bucket20**：P=50,count=101 → idx 51；P=33.3,count=10 → idx 4；bucket20：P=1→6，P=6.25→10，P=50→17，P=100→20，P<0.0001→1。

**T3 set_priority 往返**：队列 [1..10]，el5 的 P=44.444。对 el5 执行 set_priority(50.0)：删后 count'=9，newPos=Round(4.5)+1=5，队列不变，读回仍 44.444。set_priority(1, 100.0) → 1 到队尾；set_priority(10, 0.0) → 10 到队首且读回 0.0。

**T4 缺失自修复**：队列 [1,2,3]，get_priority(99) → 0.0 且队列变为 [99,1,2,3]。新增（定案 §4.2）：已删除元素 / id==0 → 0.0 且队列不变；count<2 → 0.0 且不修复。

**T3b 无效元素门**：队列 [1..10]，is_valid 判 #5 无效，set_priority(5, 0.0) → 队列不变。

**T5 change_priority_by**：队列 [1,2,3] 对缺席的 99 执行 delta=1e-6 → 队列不变（守卫失效会自修复把 99 入队）；101 元素队列中对 P=50 的元素 delta=-0.1 → 位置不变（粒度效应）。

**T6 默认值入队**：101 元素队列 add_new_element(999) → 位置 6，读回 P=4.9505。

**T7 spread**（len=100，rand01=0.5）：P=5→5.2347；P=31→23.6065；P=50→36.5396；P=100→70.3841；P=0→0.0。

**T8 create_extract 全流程**：队列 [1..101]，父 el51（P=50），len=100，rand01=0.5：父读回 P=50.4950，新 extract 位于第 38 位，读回 P=36.6337。enqueue_first 与 parent_first 在这一组上碰巧结果相同（parent_first 下父先 ×0.995 仍留在第 51 位，新元素入队后被挤到第 52 位，最终位置一致）。

**T9 interleave**：items/topics 各 20，proportion=5 → 前 19 个全是 items，第 20 位是第一个 topic。

**T10 randomized_draw**：输入 [A,B,C,D,E]，factor=8，rand01 序列 [0.9, 0.1, 0.5, 0.5, 0.9, 0.9, 0.2, 0.2, …] → 输出 [A, C, B, D, E]。

**T11 trackbar_to_factor**：pos0→0.001，pos1→0.6，pos25→1.0，pos50→8.8701，pos75→14.9090，pos100→1000.0。

**T12 batch 单值**：increase(old=2, change=50, min=1, max=50) → 1.0；increase(old=2, change=150) → 2.0（回退）；decrease(old=2, change=150) → 3.0；spread_linear(min=1, step=2, k=5) → 9.0；spread_proportional(old=30, oldMin=10, oldMax=50, min=1, max=50) → 25.5。

**T13 取整与批量顺序**：10 元素队列对 #5 执行 set_priority(50.0) → 第 5 位（half-up 会给第 6 位）；decrease(old=80, change=150, min=1, max=50) → **50.0**。
新增批量驱动：100 元素队列，子集 [10,20,30]、spread_linear、min=0、max=60，#20 的种类字节为 2 → #20 不动、#10 到队首、#30（k=3，step=max(60/2,100/100)=30）落第 60 位；已删除元素不动。
step 下限：100 元素，子集 [10,20,30]、spread_linear、min=0、max=1 → step=max(0.5,1)=1，#20 最终第 3 位。
oldP 现读：101 元素，子集 [81,59]、increase、change=50、min=0、max=100 → #59 最终第 31 位（预读会给 30）。
比例铺开（区分 oldMin/oldMax 预扫固定与每次现读）：101 元素，子集 [11,91,51]、min=20、max=60 → #11/#91/#51 落第 21/61/41 位（每次现读极值会让 #51 留在 51）。
容量中止：100 元素，子集 [10,20,30]、spread_proportional、min=0、max=0.0001 → 返回 False，队列不变。
参数规范化：101 元素，#51 increase、change=100、min=60、max=20 → 交换为 20/60，仍在第 51 位。

**T14 两种摘录时序**：10 元素队列，父在第 1 位，len=0，rand01=0.5：enqueue_first → 队首两位 [父, 新]；parent_first → [新, 父]。另：不 spread 时（101 元素、父 51）新元素停在默认 5.0 的第 6 位，父被挤到第 52 位。

**T15 排序键取整**：P=50.00004 → (100−P)×10000 = 499999.6，trunc=499999，Round=500000，断言两者不同、键取 500000。id==0 或已删除 → key 0。

**T17 复习后按间隔挪位**（原版实测 + 公式推演）：第二轮实测 10-23（#8 3→7）、10-24（#9 4→7）单篇逐位吻合；10-28 按复习前队列顺序 [7,11,5,10,4,6,2] 依次复习、10-22 按 [7,10,11,3,6,2,4] 依次复习，得到实测队列。推演：11 元素第 6 位 10→5 → 第 4 位；第 1 位 2→3 → 第 2 位；新 == 旧、旧 0 → 新 1 不动。

**T16 打分调优先级**：每次全新的 10001 元素队列，第 5001 位元素 grade=3/4/5 → 第 5006/5016/5031 位；grade=2、window_mode=7、AFactor=0 → 队列不变；101 元素队列 grade=3 → 不动。

## 12. 实现检查清单

- [ ] 队列是唯一真身：任何地方都不另存一份 P 数值（缓存必须可由位置重算）
- [ ] set_priority 先删后算 count'，分母用 count' 不是 count-1；newPos 越界追加
- [ ] get_priority 的 count<2 短路返回 0.0；已删除元素不自修复
- [ ] 摘录按入口区分 enqueue_first / parent_first
- [ ] spread 用自然指数 e，不是 2 的幂
- [ ] 复习排序键用 Round，不用 trunc
- [ ] randomized_draw 的 ratio 用定长 n0、idx 上限用递减剩余数、r2/r3 只在扰动分支抽
- [ ] interleave 的比较是严格大于（target > a/(a+b+1)）
- [ ] change_priority_by 的 1e-5 守卫
- [ ] 批量的状态字节（已删除不占 k、状态 2 占 k 不写）、执行顺序、防反向回退与尾部上钳（§6）
- [ ] item 打分后按 §9 调优先级
- [ ] topic 复习提交后按 §4.9 挪位（变长往后、变短往前、保底 1 格）
- [ ] 默认优先级 5.0、因子 8.0/12.0、proportion 5.0

## 13. 未确认清单

| # | 位置 | 未确认的点 |
|---|---|---|
| 1 | §5 | GenerateExtractChild `0xf25670` 对应用户的哪个操作 |
| 2 | §5 | 菜单参数 arg5 的含义 |
| 3 | §5 | ~~Alt+X 对应哪个菜单~~ 已结：Alt+X = MIRememberExtract（DFM 0x8058 + 用户实操） |
| 4 | §6 | ~~入口门字节含义~~ 已结：状态字节（0 待学 / 1 已记忆 / 2 已撤销 / 3 已删除） |
| 5 | §6 | ~~批量处理顺序~~ 已结：范围字节 `0x121d6a5` 决定（浏览器显示顺序 / 「下一个」链） |
| 6 | §8.3 | itemFactor / topicFactor / proportion 的持久化方式 |
| 7 | §8.5 | Outstanding 队列由谁构建（逾期是否在内、postpone 到今天的元素如何入队）；当天中途新增元素往哪插 |
| 8 | §9 | 间隔过短警报的门槛数值（来自运行时内存） |
| 9 | §10 | Mercy 是否按优先级分配（Postpone 已定，见排期规格 §5.6） |
| 10 | §4.7 | ImportFromExcel 的创建机制；`0xd22940` 直接建记录分支是否绕过 set_priority |
| 11 | §4.9 | ~~档位步进器 `0xc99b30` 的 UI 对应~~ 已结：topic 复习提交后按间隔挪位。仍 ❓：`0xd66670`、`0xf0e660` 两个调用者对应哪个操作 |
| 12 | §6 | spread_proportional 容量检查里 minPos/maxPos 的换算函数（推定为 `priority_to_index`） |
