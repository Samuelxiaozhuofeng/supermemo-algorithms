"""
SuperMemo 20 优先级算法 — 参考实现（Python 3，标准库 only）。规格见同目录 SPEC.md。
约定：P 为 double，0.0 = 最高，100.0 = 最低；Round = 四舍六入五成双（Python round()）；
trunc = 向零取整（int()）；rand01 一律以参数注入。
"""

import math

DEFAULT_PRIORITY = 5.0     # 新元素默认优先级
ITEM_FACTOR = 8.0          # 单元初始化 0xb28b8b 写入
TOPIC_FACTOR = 12.0
PROPORTION_TOPICS = 5.0    # %

GRADE_DELTA = {3: 0.05, 4: 0.15, 5: 0.3}   # 0xc9a6f0：其他分数 → 0
SKIP_GRADE_WINDOW_MODES = (0, 7, 8)


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def Round(x):
    """round-half-to-even，返回 int（0x40c5d0 cvtsd2si）。"""
    return round(x)


# ---------------------------------------------------------------- 换算函数

def pos_to_priority(pos, count):
    """0xc9a680：1-based 位置 → 百分位。pos<2 返回 0.0。"""
    if pos < 2:
        return 0.0
    return (pos - 1) / (count - 1) * 100.0


def priority_to_index(p, count):
    """0xc99880：P → 1-based 索引（分母 count-1）。"""
    return Round(p / 100.0 * (count - 1)) + 1


def priority_to_bucket20(p):
    """0xc99380：P → 1..20 档。"""
    if p < 0.0001:
        return 1
    return clamp(Round(20.0 * (p / 100.0) ** 0.25), 1, 20)


# ---------------------------------------------------------------- 优先级队列

class PriorityQueue:
    """唯一真身：元素 id 有序列表，items[0] = 队首 = 最高优先级。"""

    def __init__(self, items=(), is_valid=lambda el: True):
        self.items = list(items)
        self.is_valid = is_valid    # 0xd624c0 元素有效性判定，可注入

    def __len__(self):
        return len(self.items)

    def locate(self, el):
        """0xe23450：1-based 位置；不在队列返回 0。"""
        try:
            return self.items.index(el) + 1
        except ValueError:
            return 0

    def get_priority(self, el, is_deleted=lambda el: False):
        """0xc99450。count<2 → 0.0。不在队列：已删除（0xd51690：id==0 或状态==3）→ 0.0；
        否则 set_priority(el, 0.0) 自修复后返回 0.0（原版另弹框）。"""
        count = len(self.items)
        if count < 2:
            return 0.0
        pos = self.locate(el)
        if pos == 0:
            if not (el == 0 or is_deleted(el)):
                self.set_priority(el, 0.0)
            return 0.0
        return pos_to_priority(pos, count)

    def set_priority(self, el, p):
        """0xc9b210：钳制 → 先删 → newPos = Round(P/100*count')+1，越界追加（0xe24a50 → 0xe239b0）。
        0xd624c0 判无效时原版弹框不改动：此处直接 return。"""
        if not self.is_valid(el):
            return
        p = clamp(p, 0.0, 100.0)
        if el in self.items:
            self.items.remove(el)
        if p == 100.0:
            self.items.append(el)
            return
        count_after = len(self.items)
        new_pos = Round(p / 100.0 * count_after) + 1
        if new_pos > count_after:
            self.items.append(el)
        else:
            self.items.insert(new_pos - 1, el)

    def change_priority_by(self, el, delta):
        """0xd71320：-1e-5 < delta < 1e-5 无操作；否则 clamp 后 set。"""
        if abs(delta) < 1e-5:
            return
        self.set_priority(el, clamp(self.get_priority(el) + delta, 0.0, 100.0))

    def add_new_element(self, el, default=DEFAULT_PRIORITY):
        """0xd7e9b0：新元素按默认值入队。"""
        self.set_priority(el, default)

    def first(self):
        return self.items[0] if self.items else None

    def pop(self):
        return self.items.pop(0) if self.items else None


# ---------------------------------------------------------------- 复习打分后自动调优先级

def on_item_graded(queue, el, grade, afactor=1.0, is_deleted=lambda el: False, window_mode=1,
                   alarm_cancelled=False):
    """0xf4beb0 → 0xd8b6c0 → 0xd6f5c0 → 0xd71320，protect 恒 0。
    跳过：AFactor<1e-5、已删除、学习窗口 mode∈{0,7,8}。
    alarm_cancelled：门 0xceb1c0 的间隔过短警报被取消（0xcebe00 返回 0），整单取消。"""
    if alarm_cancelled:
        return
    if afactor < 1e-5 or el == 0 or is_deleted(el) or window_mode in SKIP_GRADE_WINDOW_MODES:
        return
    queue.change_priority_by(el, GRADE_DELTA.get(grade, 0.0))


# ---------------------------------------------------------------- Extract

def spread_priority(p_parent, text_len, rand01):
    """0xc99a00：新 extract 的优先级随机铺开。p_parent 为已 ×0.995 的值。"""
    t = math.exp(1.7 * (p_parent ** 0.2)) if p_parent > 0 else 0.0
    lo = p_parent * 0.7
    hi = t
    if lo > t:              # 合法 P∈[0,100] 下不触发，保留以求忠实
        lo, hi = t, t * 1.3
    hi = clamp(hi, 0.0, 100.0)
    result = lo + (hi - lo) * (text_len / (text_len + 100.0)) * rand01()
    return clamp(result, 0.0, 100.0)


def create_extract(queue, parent_el, new_el, text_len, rand01, spread_enabled=True,
                   order='enqueue_first'):
    """order='enqueue_first'：ExtractSelection 0xf3a640 / WebExtract 0xf3ca90（菜单摘录），
         AddNew(新) → 读父 P → set(父, P*0.995) → 开关开时 set(新, spread)。
       order='parent_first'：GenerateExtractChild 0xf25670 / GeneratePictureExtractChild 0xf25bd0，
         读父 P → set(父, P*0.995) → AddNew(新) → FinishGeneratedExtractChild 0xf25ab0 无条件 spread。
       dialog=1（Schedule extract）时 spread 之后由用户在对话框另定，不在此建模。"""
    if order == 'enqueue_first':
        queue.add_new_element(new_el)
        p = queue.get_priority(parent_el) * 0.995
        queue.set_priority(parent_el, p)
    elif order == 'parent_first':
        p = queue.get_priority(parent_el) * 0.995
        queue.set_priority(parent_el, p)
        queue.add_new_element(new_el)
        spread_enabled = True
    else:
        raise ValueError(order)
    if spread_enabled:
        p_new = spread_priority(p, text_len, rand01)
        queue.set_priority(new_el, p_new)
        queue.set_priority(new_el, p_new)   # 原版跳过对话框时连写两次同值（冗余）


def adjust_priority_by_interval(queue, el, old_iv, new_iv, div3=False):
    """0xc99b30：按间隔变化挪优先级。topic 复习提交 0xd7ca60 传 div3=0；推迟 0xd66670 传 div3=1。
    旧间隔不足 1 按 1 算；新 == 旧不动。变长往队尾挪（P/f，上限 100），变短往队首挪（P·f）；
    落位没变就朝该方向再挪 1 格（夹在 [1, N]）。与 schedule/逆向证据/补查_2026-10-19/q3_复习后挪位_回放.py 逐位一致（该脚本未随本仓库公开，结论见 SPEC.md §4.9）。"""
    old_iv = max(1, old_iv)
    if new_iv == old_iv:
        return
    n = len(queue)
    p = queue.get_priority(el)
    d = 80.0 * (1.0 - min(old_iv, new_iv) / max(old_iv, new_iv))
    if div3:
        d /= 3.0
    f = (100.0 - d) / 100.0
    p2 = p * f if new_iv < old_iv else min(100.0, p / f)
    pos = priority_to_index(p, n)
    if priority_to_index(p2, n) == pos:
        pos = max(1, pos - 1) if new_iv < old_iv else min(n, pos + 1)
        p2 = pos_to_priority(pos, n)
    queue.set_priority(el, p2)


# ---------------------------------------------------------------- 批量改优先级

def batch_modify_priority(old_p, mode, change=100.0, min_pct=1.0, max_pct=50.0,
                          k=None, step=None, old_min=None, old_max=None):
    """0xd45e30 单值计算。increase/decrease：乘系数 → /100 → 上钳 max → 下钳 min →
    防反向回退 → 尾部再上钳 max。k 为 1-based 处理序号。"""
    if mode in ('increase', 'decrease'):
        t = old_p * change
        t = t / 100.0
        t = min(t, max_pct)
        t = max(t, min_pct)
        if mode == 'increase' and t > old_p:
            t = old_p
        if mode == 'decrease' and t < old_p:
            t = old_p
        new_p = t
    elif mode == 'spread_linear':
        new_p = min_pct + (k - 1) * step
    elif mode == 'spread_proportional':
        if old_max == old_min:
            new_p = min_pct
        else:
            new_p = min_pct + (max_pct - min_pct) * (old_p - old_min) / (old_max - old_min)
    else:
        raise ValueError(mode)
    if new_p > max_pct:                 # 公共尾部 0xd46013
        new_p = max_pct
    return new_p


def batch_apply(queue, els, mode, change=100.0, min_pct=1.0, max_pct=50.0,
                status_of=lambda el: 0, is_deleted=lambda el: False):
    """批量驱动：els 为处理顺序（SPEC §6：浏览器名单显示顺序或「下一个」链）。
    状态字节 status_of：3（或 is_deleted / el==0）= 已删除，跳过且不占 k；
    0/1 写入；其他（2）占 k 但不写入。
    oldP 每次现读；oldMin/oldMax 开始前预扫描一次。
    入口先规范化参数；spread_proportional 容量不足时整批不动、返回 False，否则返回 True。"""
    change = clamp(change, 0.0, 1000.0)
    min_pct = clamp(min_pct, 0.0, 99.0)
    max_pct = clamp(max_pct, 0.0001, 100.0)
    if min_pct > max_pct:
        min_pct, max_pct = max_pct, min_pct
    els = list(els)
    n = len(els)
    step = 0.0 if n <= 1 else max((max_pct - min_pct) / (n - 1), 100.0 / len(queue))

    def deleted(el):
        return el == 0 or status_of(el) == 3 or is_deleted(el)

    def eligible(el):
        return status_of(el) in (0, 1) and not deleted(el)

    old_min, old_max = 100.0, 0.0
    if mode == 'spread_proportional':
        min_pos = priority_to_index(min_pct, len(queue))   # 换算函数推定，未确认（SPEC §13）
        max_pos = priority_to_index(max_pct, len(queue))
        if n > max_pos - min_pos + 1:
            return False                                    # 原版弹警告中止
        for el in els:
            if eligible(el):
                p = queue.get_priority(el, is_deleted)
                old_min, old_max = min(old_min, p), max(old_max, p)
    k = 0
    for el in els:
        if deleted(el):                                     # 0xd6d284 在 k+1（0xd6d2a1）前跳走
            continue
        k += 1
        if not eligible(el):
            continue
        old_p = queue.get_priority(el, is_deleted)
        queue.set_priority(el, batch_modify_priority(old_p, mode, change, min_pct, max_pct,
                                                     k, step, old_min, old_max))
    return True


# ---------------------------------------------------------------- 复习排序

def trackbar_to_factor(pos):
    """0xb27280：滑杆位置（0..100）→ 随机因子。"""
    if pos == 100:
        return 1000.0
    if pos == 0:
        return 0.001
    x = math.sqrt(pos / 100.0)
    return x + 0.5 if x <= 0.5 else (x - 0.5) * 38.0 + 1.0


def repetition_sort_key(p, el_id, is_deleted=lambda el: False):
    """0xb28180：key = Round((100-P)*10000)（0xb283b2 调 0x40c5d0），不是 trunc。
    id==0 或已删除 → P 按 100。按 key 降序排。"""
    if el_id == 0 or is_deleted(el_id):
        p = 100.0
    return Round((100.0 - p) * 10000.0)


def randomized_draw(sorted_items, factor, rand01):
    """随机化抽取。i=1 恒取队首；ratio 用定长 n0，idx 上限用递减剩余数，trunc（cvttsd2si）。"""
    handles = list(sorted_items)
    n0 = len(handles)
    out = []
    for i in range(1, n0 + 1):
        ratio = (i - 1) / n0
        t1 = ratio ** (1.0 / factor) if ratio > 0 else 0.0
        r1 = rand01()
        if t1 > r1:
            r2 = rand01()
            r3 = rand01()
            idx = int((r2 ** (1.0 / factor)) * len(handles) * r3) + 1
        else:
            idx = 1
        out.append(handles.pop(idx - 1))
    return out


def interleave(items, topics, proportion=PROPORTION_TOPICS):
    """0xb287af 穿插：target = 1 - P/100。"""
    target = 1.0 - proportion / 100.0
    a = b = 0
    ia = it = 0
    out = []
    while ia < len(items) or it < len(topics):
        take_a = target > a / (a + b + 1)
        if ia >= len(items):
            take_a = False
        if it >= len(topics):
            take_a = True
        if take_a:
            out.append(items[ia]); ia += 1; a += 1
        else:
            out.append(topics[it]); it += 1; b += 1
    return out


def build_daily_queue(item_priorities, topic_priorities, rand01,
                      item_factor=ITEM_FACTOR, topic_factor=TOPIC_FACTOR,
                      proportion=PROPORTION_TOPICS, is_deleted=lambda el: False):
    """{el_id: P} → 排序 → 随机抽取 → 穿插。"""
    def prep(pairs, factor):
        keyed = sorted(pairs, key=lambda kv: -repetition_sort_key(kv[1], kv[0], is_deleted))
        return randomized_draw([el for el, _ in keyed], factor, rand01)
    return interleave(prep(list(item_priorities.items()), item_factor),
                      prep(list(topic_priorities.items()), topic_factor), proportion)
