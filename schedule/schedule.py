# -*- coding: utf-8 -*-
"""SM20 文章 / 摘录排期 + 自动推迟：参考实现（只用标准库）。

规格与证据等级见同目录 SPEC.md，函数名后的地址即 SPEC 里的小节锚点。
约定：
  * 日期一律是整数「日号」（单位：天）；today 由调用方注入。
  * rng 是无参 callable，每次返回 [0,1) 的 double（原版 Delphi Random，32 位整数 × 2^-32）。
  * 优先级 prio ∈ [0,100]（0 最高），由调用方按优先级定稿 §4.2 get_priority 算好传入。
"""

import math
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "priority"))
from priority import adjust_priority_by_interval  # noqa: E402

MAX_INTERVAL = 44530          # 0xADF2


# ---------------------------------------------------------------- 取整 / 日期
def R(x):
    """0x40c5d0 cvtsd2si：四舍六入五成双。Python round() 对 float 即此语义。"""
    return int(round(x))


def logical_today(now, shift_hours, base, word_118):
    """0xd749b0 → 0xd739e0。now/base 是 TDateTime（天），shift_hours 单位是小时。"""
    t = math.trunc(now - shift_hours / 24.0) - math.trunc(base) - word_118 + 1
    return 1 if t == 0 else t


def real48_to_float(raw):
    """0x410400：6 字节 Real48 → double。首字节 0 → 0.0。"""
    b0, b1, b2, b3, b4, b5 = raw
    if b0 == 0:
        return 0.0
    sign = (b5 & 0x80) << 56
    exp = (b0 + 0x37E) << 52
    man = (((b5 & 0x7F) << 32) | (b4 << 24) | (b3 << 16) | (b2 << 8) | b1) << 13
    return struct.unpack("<d", struct.pack("<Q", sign | exp | man))[0]


# ---------------------------------------------------------------- 元素与集合
@dataclass
class Element:
    """0xd71680 读出的 0x76 字节记录里与排期有关的字段（偏移见 SPEC §2.2）。"""
    etype: int = 0            # +0x00
    status: int = 0           # +0x01  1 = 已进入复习（memorized）, 3 = 已删除
    reps: int = 0             # +0x0c
    interval: int = 0         # +0x10  word
    last_day: int = 0         # +0x12  word，有符号读
    af: float = 0.0           # +0x1c  Real48
    real_22: float = 0.0      # +0x22  Real48，名字未确认
    fi: int = 0               # +0x30
    counter_31: int = 0       # +0x31  名字未确认
    counter_35: int = 0       # +0x35  推迟计数（M 称 TotalPostpones）


@dataclass
class Collection:
    today: int
    elements: dict = field(default_factory=dict)   # id → Element
    rep_dates: dict = field(default_factory=dict)  # [coll+0xe5] RepDates：id → 下次复习日
    outstanding: list = field(default_factory=list)  # [coll+0xed] 当天名单（元素 id）
    cursor_11a: int = 1       # [app+0x11a] 收集下界
    default_fi: int = 0       # [coll+0x11c]

    def fi_of(self, el):
        """0xd748e0：记录 FI 非 0 用它，否则用集合缺省。"""
        return el.fi if el.fi != 0 else self.default_fi

    def remove_repetition(self, el_id):
        """0xd5e0d0：从当天名单（及 item/topic 子名单）删掉。"""
        if el_id in self.outstanding:
            self.outstanding.remove(el_id)

    def schedule_repetition(self, el_id, new_day):
        """0xd8aff0：写 RepDates；new_day ≤ today 才放回当天名单。
        放回的位置（0x97b0a0）未确认，这里放队首。"""
        self.rep_dates[el_id] = new_day
        if new_day <= self.today:
            self.remove_repetition(el_id)
            self.outstanding.insert(0, el_id)
        if new_day < self.cursor_11a:          # 0xd8b26a
            self.cursor_11a = new_day

    def day_burden(self, day):
        """0xd5db60：某日到期元素数（语义按 M sched1，未逐指令核）。"""
        return sum(1 for d in self.rep_dates.values() if d == day)

    def advance_cursor(self):
        """0xd87310 逾期游标：空日跳过，碰到非空日或今天停。"""
        while self.day_burden(self.cursor_11a) < 1 and self.cursor_11a < self.today:
            self.cursor_11a += 1

    def collect(self, lo, hi):
        """0xd87380：收 lo ≤ 日期 ≤ hi（两端含），日期 ≠ last+interval 的跳过。
        返回 items + topics 合并后的 id 列表（0xe24270）。不改任何日期。
        先调 0xd87310 推进游标；推进是否影响本次下界未确认，这里本次仍用传入的 lo。"""
        self.advance_cursor()
        items, topics = [], []
        for el_id in sorted(self.rep_dates):
            d = self.rep_dates[el_id]
            if d < lo or d > hi:
                continue
            el = self.elements[el_id]
            if el.last_day + el.interval != d:
                continue
            (items if el.etype == 1 else topics).append(el_id)
        return items + topics

    def build_outstanding(self):
        """0xd5e970 重建分支：收 [cursor, today]，逾期也收。"""
        self.outstanding = self.collect(self.cursor_11a, self.today)
        return self.outstanding


# ---------------------------------------------------------------- 新元素 / 摘录 AF
AF_ITEM_RAW = bytes((0x82, 0x00, 0x00, 0x00, 0x00, 0x60))   # 3.5
AF_OTHER_RAW = bytes((0x81, 0x9A, 0x99, 0x99, 0x99, 0x19))  # double 0x3ff3333333334000


def new_element(type_byte, field_109, today):
    """0xd72c40 模板 + 0xd72070：AF 按类型字节，间隔 0，
    仅 coll+0x109 > 0 时 LastRep = today。不写 RepDates。"""
    af = real48_to_float(AF_ITEM_RAW if type_byte == 1 else AF_OTHER_RAW)
    return Element(etype=type_byte, af=af, interval=0,
                   last_day=today if field_109 > 0 else 0)


def length_af(n):
    """0xcf73f0 = 1.25 + 150/(n+200)，n=0 → 2.0。摘录与新 topic 共用这一份。"""
    if n == 0:
        return 2.0
    t = 10000.0 / n
    return 1.25 + 0.75 * t / (50.0 + t)


def new_topic_af(text_len):
    """新 topic 建好后按正文长度重写 AF（0xbaa5ee / 0xf2e055 → 0xcf73f0(L)）。
    L = 0xf28d40 取到的正文字符串长度前缀（UTF-16 单位）。"""
    return length_af(text_len)


def new_extract_af(x, n):
    """0xcf6130(x, n)：x 是父元素调整前的 AF。"""
    f = length_af(n)
    t = max(x - 1.01, 0.0)
    w = 0.9 - 0.9 * t / (0.29 + t)
    return x * w + f * (1.0 - w)


def extract_afs(parent_af, n):
    """0xf3a640 / 0xf25ab0：返回 (新元素 AF, 父元素新 AF)。父的下次复习日不变。"""
    return new_extract_af(parent_af, n), (parent_af - 1.01) * 0.95 + 1.01


# ---------------------------------------------------------------- 扰动 / AF 调整 / topic 间隔
def disperse(x, d, rng):
    """0xcf9e20：恰好抽 2 次随机数，返回 double，由调用方取整。"""
    d = max(d, 4.0)
    d = min(d, x + 4.0)
    d = min(max(d, 0.0), 100.0)
    m = -10.857763300760043 * math.log(1.0 - 1.979793637145314 * rng() / 2.0)
    if rng() > 0.5:
        m = -m
    return max(1.0, x + m / 50.0 * d)


def adjust_af(af, old, new, hard):
    """0xcf7800。"""
    a = old if old != 0 else 1
    b = new if new != 0 else 1
    if a == b:
        return af
    ratio = max(a, b) / min(a, b)
    f = ratio / (ratio + (80.0 if hard else 15.0))
    delta = max((af - 1.01) * f, 0.001)
    af = af + delta if b > a else af - delta
    return min(max(af, 1.01), 6.0)


def topic_next_interval(old, af, mode, rng):
    """0xe145a0：只看旧间隔与 AF，逾期天数不参与。"""
    if mode <= 7 and (1 << mode) & 0x60:          # mode ∈ {5, 6}
        x = float(max(1, old >> 1))
        d = max(1.0, x / 2.0)
    else:
        a = min(max(af, 1.01), 3.0)               # 只在计算时钳
        base = a ** 3 if old == 0 else old * a
        x = float(R(min(base, 44530.0)))
        d = x - old
    r = R(disperse(x, d, rng))
    return old + 1 if r <= old else r


def commit_topic_repetition(coll, el_id, r8d, mode, flag, rng, pqueue=None):
    """0xd7ca60：topic 复习提交。r8d ≥ 0 直接作间隔，否则调 0xe145a0。
    传了 pqueue 才在 adjust_af 之后按间隔挪优先级（0xd7cf1c → 0xc99b30，div3=0）。
    历史记录、intact/drill 队列不建模。返回下次复习日。"""
    today = max(coll.today, 1)
    el = coll.elements[el_id]
    old_iv, old_af = el.interval, el.af
    if el.reps > 0:
        coll.remove_repetition(el_id)
    el.reps += 1
    new = r8d if r8d >= 0 else topic_next_interval(old_iv, old_af, mode, rng)
    last = today
    if new < 1:
        new, last = 1, today - 1
    el.last_day, el.status = last, 1
    el.af = adjust_af(old_af, old_iv, new, flag != 0)   # 0xd7cee5：未截断的新间隔
    if pqueue is not None:                              # 0xd7cf1c：旧间隔、未截断的新间隔
        adjust_priority_by_interval(pqueue, el_id, old_iv, new, div3=False)
    ratio = float(new) if (el.reps == 1 or old_iv == 0) else new / old_iv
    el.real_22 = max(ratio, 1.0)
    new = min(new, MAX_INTERVAL)
    el.interval = new
    if flag == 0:
        el.counter_35 = 0
    coll.schedule_repetition(el_id, last + new)
    return last + new


# ---------------------------------------------------------------- 推迟设置
@dataclass
class PostponeSettings:
    """71 字节设置块，偏移以代码为准。默认值 = 除计数保护阈值 255 外不保护、不限条数（不是原版出厂值）；
    出厂值用 factory_defaults()。"""
    scope: int = 0               # +0x05 非 0：按 PQueue 位置排序 + 留 N 条 + 第二遍
    spread: int = 0              # +0x06 执行器内部置位：优先级铺开分支
    sub_branch: int = 0          # +0x0f ≠1 时先调 0xb7edb0（未拆，参考实现不模拟）
    keep_n: int = 0              # +0x10 word
    due_check_off: int = 0       # +0x12 0 = 要求已到期（自动路径强制 0）
    simulate: int = 0            # +0x13 非 0：不扰动、不写日期
    item_delay_word: int = 0     # +0x14 倍率 1 + w/100
    topic_delay_word: int = 0    # +0x16
    item_max: int = 0xFFFF       # +0x18
    topic_max: int = 0xFFFF      # +0x1a
    item_min: int = 1            # +0x1c
    topic_min: int = 1           # +0x1e
    skip_items: int = 0          # +0x20 对话框 Skip items：勾上 = item 整类不推迟
    skip_topics: int = 0         # +0x21 对话框 Skip topics：勾上 = topic 整类不推迟
    item_skip_base: int = 0x7FFFFFFF   # +0x22 dword，base ≥ 它保护
    topic_skip_base: int = 0x7FFFFFFF  # +0x26
    item_skip_fi: int = 0        # +0x2a FI < 它保护
    topic_skip_af: float = -math.inf  # +0x2b AF ≤ 它保护（0xb81520 ucomisd/jb）；-inf = 不保护
    item_skip_count: int = 255   # +0x33 counter_35 ≥ 它保护（默认计数保护阈值 255）
    topic_skip_count: int = 255  # +0x34
    item_prio_th: float = -1.0   # +0x35 阈值 > prio 保护
    topic_prio_th: float = -1.0  # +0x3d
    item_modify_by_fi: int = 0   # +0x45 对话框「按 FI 调 item」，执行器不读
    topic_modify_by_af: int = 0  # +0x46 对话框「按 AF 调 topic」，执行器不读
    # 「按优先级调」的勾没接线、不存进块：sqrt(prio) 那一步无条件执行

    @classmethod
    def factory_defaults(cls):
        """实测出厂值（实测报告_第一轮 §2 C/D、补查 Q2_设置块.md）。
        「–」= 该类没有这道保护：FI 阈值只有 item（+0x2a），AF 阈值只有 topic（+0x2b）。
        +0x0f（Sub-branch）出厂下标未对上 ❓，这里保持 0。"""
        return cls(scope=0, keep_n=50, item_delay_word=20, topic_delay_word=50,
                   item_max=50, topic_max=100, item_min=1, topic_min=6,
                   skip_items=1, skip_topics=0, item_skip_base=500, topic_skip_base=800,
                   item_skip_fi=6, topic_skip_af=1.01, item_skip_count=50, topic_skip_count=100,
                   item_prio_th=6.0, topic_prio_th=3.0, item_modify_by_fi=1, topic_modify_by_af=1)

    @classmethod
    def auto_runtime(cls):
        """自动推迟进执行器时实际传入的块（第六轮调试器在 T8 转储，集合里没有 postpone.ini）。
        和对话框显示的出厂值有两处不同：方法 = Skip top N（+0x05=1），Skip items 不勾（+0x20=0）。"""
        s = cls.factory_defaults()
        s.scope, s.skip_items, s.sub_branch = 1, 0, 1
        return s


def delay_text_to_word(text, is_topic, old_word):
    """编辑框 → 设置：钳到 item [1.01,5.0] / topic [1.01,20.0]，word = R((v-1)*100)。"""
    try:
        v = float(text)
    except ValueError:
        return old_word
    v = min(max(v, 1.01), 20.0 if is_topic else 5.0)
    return R((v - 1.0) * 100.0)


def delay_word_to_mult(word):
    return 1.0 + word / 100.0


TOPIC_ETYPES = (0, 2, 4)        # G 包：这些 etype 走 topic 的保护 / 倍率 / 钳制


def _kind(etype):
    return "item" if etype == 1 else ("topic" if etype in TOPIC_ETYPES else "other")


# ---------------------------------------------------------------- 逐元素推迟天数
def postpone_protected(coll, el, base, prio, s):
    """0xb81280 普通分支的跳过条件。prio 为 NaN 时「阈值 > prio」不成立，不受保护。
    topic 的 AF 比较是 AF ≤ 阈值保护（ucomisd 阈值,AF / jb 不保护）；AF 或阈值为 NaN 时
    无序比较置 CF=1 → jb 跳走 → 不保护，Python 的 <= 对 NaN 也是 False，一致。"""
    kind = _kind(el.etype)
    if kind == "item":
        return bool(s.skip_items or base >= s.item_skip_base or coll.fi_of(el) < s.item_skip_fi
                    or el.counter_35 >= s.item_skip_count or s.item_prio_th > prio)
    if kind == "topic":
        return bool(s.skip_topics or base >= s.topic_skip_base or el.af <= s.topic_skip_af
                    or el.counter_35 >= s.topic_skip_count or s.topic_prio_th > prio)
    return False


def postpone_extra(coll, el, prio, s, rng):
    """0xb81280：返回 (extra, ratio)；受保护返回 None。"""
    base = max(coll.today - el.last_day, el.interval, 1)
    kind = _kind(el.etype)
    if kind == "item":
        lo, hi = s.item_min, s.item_max
    else:
        lo, hi = s.topic_min, s.topic_max
    if s.spread:                                   # 0xb81140：不做保护检查，无随机
        extra = lo + R((hi - lo) * prio / 100.0)
        return extra, (base + extra) / base
    if postpone_protected(coll, el, base, prio, s):
        return None
    if kind == "item":
        mult = delay_word_to_mult(s.item_delay_word)
    elif kind == "topic":
        mult = delay_word_to_mult(s.topic_delay_word)
    else:
        mult = 1.01                                # 0xb8141e 立即数
    extra = R(base * mult) - base                  # 减的是 base
    extra = R(2 * extra * math.sqrt(prio / 100.0))  # 无条件
    extra = max(extra, 1)
    if kind != "other":
        extra = min(max(extra, lo), hi)
    # extra > 200 时原版只弹警告
    if not s.simulate:
        extra = max(R(disperse(float(extra), extra * 0.5, rng)), 1)
    return extra, (base + extra) / base


# ---------------------------------------------------------------- 写回日期
def commit_new_date(coll, el_id, new_day):
    """0xd82aa0 的 status==1 分支 + 0xd8aff0。不动 AF。"""
    el = coll.elements[el_id]
    coll.remove_repetition(el_id)
    old_iv = max(el.interval, 1)
    if new_day > el.last_day:
        new_iv = new_day - el.last_day
        el.real_22 = max(el.real_22 * new_iv / old_iv, 1.0)
    else:
        new_iv, el.real_22, el.last_day = 1, 1.0, new_day - 1
    el.interval = new_iv
    if new_iv > old_iv:
        el.counter_35 += 1
        el.counter_31 += 1
    coll.schedule_repetition(el_id, new_day)


def write_postponed_date(coll, el_id, ratio):
    """0xd5c9c0：status ≠ 1 不写。返回新日期或 None。"""
    el = coll.elements[el_id]
    if el.status != 1:
        return None
    edi = max(coll.today - el.last_day, el.interval)
    iv = R(edi * ratio)
    if iv <= edi:
        iv = edi + 1
    new_day = el.last_day + min(iv, MAX_INTERVAL)
    commit_new_date(coll, el_id, new_day)
    return new_day


# ---------------------------------------------------------------- 执行器
def run_postpone(coll, queue, s, prio_of, pq_pos_of, rng, reverse=True):
    """0xb80c70 → 0xb81980 → 0xb81850。返回已推迟的 id 列表（q2）。
    scope≠0 时先按 PQueue 位置从队尾往前排（第八轮实测：优先级 100 → 32 依次推），推迟排在前面的，
    直到「队列数 − 已推迟数 ≤ keep_n」；仍 > keep_n 则以 spread=1 跑第二遍。"""
    queue = list(queue)
    if s.scope:
        queue.sort(key=pq_pos_of, reverse=reverse)
    done = []

    def one_pass():
        for el_id in queue:
            if s.scope and len(queue) - len(done) <= s.keep_n:
                return
            el = coll.elements[el_id]
            if el.status == 3 or el_id in done:
                continue
            if not s.due_check_off and not (el.status == 1 and el.last_day + el.interval <= coll.today):
                continue
            out = postpone_extra(coll, el, prio_of(el_id), s, rng)
            if out is None:
                continue
            done.append(el_id)
            if not s.simulate:
                write_postponed_date(coll, el_id, out[1])

    s.spread = 0
    one_pass()
    if s.scope and len(queue) - len(done) > s.keep_n:
        s.spread = 1
        one_pass()
    s.spread = 0
    return done


# ---------------------------------------------------------------- 自动推迟触发
@dataclass
class AutoState:
    switch_on: bool = True        # [[0x1166ea8]]
    last_run_day: int = 0         # [coll+0x4c5]
    field_109: int = 0            # dword [coll+0x109]
    last_used: float = 0.0        # double [coll+0x4d0]（TDateTime）
    ask_dialog: bool = False      # byte [[0x1166c60]]


def auto_postpone(coll, st, dl, now, s, prio_of, pq_pos_of, rng):
    """0xd60450。返回动作标签；'ran' 时已对逾期集执行推迟。"""
    if not st.switch_on:
        return "off"
    if st.last_run_day == coll.today:
        return "already_ran"
    if dl == 0 and st.field_109 > 0 and now - st.last_used > 10.0:   # NaN 时不成立
        st.switch_on = False                     # ask_dialog 只决定弹不弹框
        return "turned_off"
    st.last_run_day = coll.today
    if len(coll.outstanding) <= 10:              # 门 A
        return "gate_a"
    overdue = coll.collect(coll.cursor_11a, coll.today - 1)
    if len(overdue) <= 10:                       # 门 B
        return "gate_b"
    s.due_check_off = 0
    run_postpone(coll, overdue, s, prio_of, pq_pos_of, rng)
    return "ran"
