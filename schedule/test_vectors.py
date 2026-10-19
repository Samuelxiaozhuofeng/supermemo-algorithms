# -*- coding: utf-8 -*-
"""SM20 排期 + 自动推迟：断言向量。跑法：python3 -I test_vectors.py（退出码 0 = 全过）。

每条向量的第一个参数注明来源：「公式推演」= 按 SPEC 公式手算 / 代入；「原版实测」= 在原版进程里量到。
原版实测的是补查 Q4 的新 topic AF、第八轮调试器的逐篇推迟（R8）、第九轮调试器的新间隔与 AF 调整（R9）；其余是公式推演（见 SPEC §9）。向量里的编号 #N 对应 SPEC「裁决 N」。
"""
import math
import struct
import sys
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from schedule import (  # noqa: E402
    R, logical_today, real48_to_float, Element, Collection, new_element,
    new_topic_af, length_af, new_extract_af, extract_afs, disperse, adjust_af,
    topic_next_interval, commit_topic_repetition, PostponeSettings,
    delay_text_to_word, delay_word_to_mult, postpone_protected, postpone_extra,
    commit_new_date, write_postponed_date, run_postpone, AutoState, auto_postpone,
)

推演, 实测 = "公式推演", "原版实测"
N = 0
BY_KIND = {推演: 0, 实测: 0}


def v(kind, name, got, want, tol=None):
    global N
    assert kind in (推演, 实测), name
    ok = (got is not None and abs(got - want) <= tol) if tol is not None else got == want
    assert ok, "%s [%s]: got %r, want %r" % (name, kind, got, want)
    N += 1
    BY_KIND[kind] += 1


def seq(*xs):
    it = iter(xs)
    return lambda: next(it)


ZERO = lambda: 0.0      # 两次都抽 0 → m = 0，disperse 原样返回 x


def mk(etype=1, status=1, last=90, iv=10, af=2.0, **kw):
    return Element(etype=etype, status=status, last_day=last, interval=iv, af=af, **kw)


def coll_with(today, els):
    c = Collection(today=today)
    for i, e in els.items():
        c.elements[i] = e
        c.rep_dates[i] = e.last_day + e.interval
    return c


# ---- 取整 / 今天（#6）
v(推演, "R 2.5→2", R(2.5), 2)
v(推演, "R 3.5→4", R(3.5), 4)
v(推演, "R -2.5→-2", R(-2.5), -2)
v(推演, "#6 today 含日切偏移", logical_today(45000.2, 6, 44000.9, 10), 990)
v(推演, "#6 today 无偏移", logical_today(45000.2, 0, 44000.9, 10), 991)
v(推演, "#6 today 0→1", logical_today(45000.1, 6, 44000.0, 1000), 1)

# ---- 新元素（#1）
v(推演, "#1 double 位模式", struct.unpack("<d", struct.pack("<Q", 0x3FF3333333334000))[0],
  1.2000000000007276)
v(推演, "#1 Real48 82..60 = 3.5", real48_to_float(bytes((0x82, 0, 0, 0, 0, 0x60))), 3.5)
e = new_element(1, 0, 50)
v(推演, "#1 类型1 AF=3.5", e.af, 3.5)
v(推演, "#1 类型1 间隔0", e.interval, 0)
v(推演, "#1 109≤0 不写 LastRep", e.last_day, 0)
e = new_element(0, 1, 50)
v(推演, "#1 其他类型 AF 位模式", struct.pack("<d", e.af), struct.pack("<Q", 0x3FF3333333334000))
assert e.af != 1.2
v(推演, "#1 109>0 写 LastRep=today", e.last_day, 50)

# ---- 新 topic 按正文长度重写 AF（补查 Q4）
v(实测, "Q4 新 topic L=100 → 1.75（9 篇）", new_topic_af(100), 1.75)
v(推演, "Q4 新 topic L=0 → 2.0", new_topic_af(0), 2.0)
v(实测, "Q4 新 topic L=726 → 1.412", round(new_topic_af(726), 3), 1.412)

# ---- 摘录 AF（#2）
v(推演, "#2 f(0)=2", length_af(0), 2.0)
v(推演, "#2 f(100)=1.75", length_af(100), 1.75)
v(推演, "#2 新元素 AF(2.0,100)", new_extract_af(2.0, 100), 1.8009765625, 1e-12)
v(推演, "#2 x<1.01 时 t 钳 0", new_extract_af(0.5, 0), 0.6499999999999999, 1e-15)
child, parent = extract_afs(2.0, 100)
v(推演, "#2 父 AF ×0.95", parent, 1.9505, 1e-12)
v(推演, "#2 子用父调整前的 x", child, new_extract_af(2.0, 100))

# ---- disperse（#4）
v(推演, "#4 ln 版本 +", disperse(20.0, 10.0, seq(0.5, 0.3)), 21.48337610227076, 1e-9)
v(推演, "#4 第二抽 >0.5 取负", disperse(20.0, 10.0, seq(0.5, 0.9)), 18.51662389772924, 1e-9)
v(推演, "#4 第二抽 =0.5 不翻", disperse(20.0, 10.0, seq(0.5, 0.5)), 21.48337610227076, 1e-9)
v(推演, "#4 d<4 抬到 4", disperse(20.0, 1.0, seq(0.5, 0.3)),
  20.0 + (21.48337610227076 - 20.0) * 0.4, 1e-9)
v(推演, "#4 d 上限 x+4", disperse(2.0, 50.0, seq(0.5, 0.3)),
  2.0 + (21.48337610227076 - 20.0) * 0.6, 1e-9)
v(推演, "#4 结果下限 1", disperse(2.0, 100.0, seq(0.99, 0.9)), 1.0)

# ---- AF 调整（#5）
v(推演, "#5 变长 AF 增", adjust_af(2.0, 10, 20, False), 2.1164705882352943, 1e-12)
v(推演, "#5 变短 AF 减", adjust_af(2.0, 20, 10, False), 1.883529411764706, 1e-12)
v(推演, "#5 hard k=80", adjust_af(2.0, 10, 20, True), 2.0241463414634144, 1e-12)
v(推演, "#5 相等不变", adjust_af(2.0, 10, 10, False), 2.0)
v(推演, "#5 0 当 1", adjust_af(2.0, 0, 1, False), 2.0)
v(推演, "#5 0.001 下限 增", adjust_af(1.015, 10, 20, False), 1.016, 1e-12)
v(推演, "#5 0.001 下限 减", adjust_af(1.015, 20, 10, False), 1.014, 1e-12)
v(推演, "#5 上限 6.0", adjust_af(5.99, 1, 100, False), 6.0)
v(推演, "#5 下限 1.01", adjust_af(1.0105, 20, 10, False), 1.01)

# ---- topic 间隔（#3）
v(推演, "#3 首次 AF³", topic_next_interval(0, 2.0, 0, ZERO), 8)
v(推演, "#3 首次 AF 钳 3.0 → 27", topic_next_interval(0, 4.0, 0, ZERO), 27)
v(推演, "#3 旧×AF", topic_next_interval(10, 2.0, 0, ZERO), 20)
v(推演, "#3 >旧 修正", topic_next_interval(10, 1.01, 0, ZERO), 11)
v(推演, "#3 带扰动 d=x-旧", topic_next_interval(10, 2.0, 0, seq(0.5, 0.3)), 21)
v(推演, "#3 上限 44530", topic_next_interval(40000, 3.0, 0, ZERO), 44530)
v(推演, "#3 mode5 减半后修正", topic_next_interval(100, 2.0, 5, ZERO), 101)
import schedule  # noqa: E402
for _mode in (5, 6):
    with mock.patch.object(schedule, "disperse", return_value=1.0) as _m:
        topic_next_interval(100, 2.0, _mode, ZERO)
    v(推演, "#3 mode%d 传给 disperse (x,d)" % _mode, _m.call_args[0][:2], (50, 25))
v(推演, "#3 mode6 旧=0 → x=1", topic_next_interval(0, 2.0, 6, ZERO), 1)
v(推演, "#3 mode7 走 AF 分支", topic_next_interval(10, 2.0, 7, ZERO), 20)

# ---- CommitTopicRepetition（#3 #5）
c = coll_with(100, {1: mk(etype=0, reps=3, last=90, iv=10, af=2.0, counter_35=7)})
c.outstanding = [1]
v(推演, "#3 提交 下次日", commit_topic_repetition(c, 1, -1, 0, 0, ZERO), 120)
el = c.elements[1]
v(推演, "#3 提交 间隔", el.interval, 20)
v(推演, "#5 提交 AF 增", el.af, 2.1164705882352943, 1e-12)
v(推演, "#5 flag=0 清零计数", el.counter_35, 0)
v(推演, "提交 +0x22 = 新/旧", el.real_22, 2.0)
v(推演, "提交后移出当天名单", c.outstanding, [])
c = coll_with(100, {1: mk(etype=0, reps=5, last=10, iv=30, af=2.0, counter_35=9)})
v(推演, "r8d=0 → 间隔1 下次=today", commit_topic_repetition(c, 1, 0, 0, 1, ZERO), 100)
v(推演, "#5 hard 变短", c.elements[1].af, 1.73, 1e-9)
v(推演, "#5 flag≠0 不清零", c.elements[1].counter_35, 9)
v(推演, "下次=today 回到当天名单", c.outstanding, [1])
c = coll_with(10, {1: mk(etype=0, reps=2, last=0, iv=10, af=2.0)})
commit_topic_repetition(c, 1, 99999, 0, 0, ZERO)
v(推演, "#5 AF 用未截断新间隔", c.elements[1].af, 2.0 + 0.99 * 99999 / 10 / (99999 / 10 + 15), 1e-12)
v(推演, "#3 间隔截 44530", c.elements[1].interval, 44530)
sys.path.insert(0, str(Path(__file__).parent.parent / "priority"))
from priority import PriorityQueue  # noqa: E402
c = coll_with(100, {6: mk(etype=0, reps=3, last=90, iv=10, af=2.0)})
pq = PriorityQueue(range(1, 12))
commit_topic_repetition(c, 6, -1, 0, 0, ZERO, pqueue=pq)     # 10 → 20：P 50 / 0.6 → 83.3 → 第 9 位
v(推演, "Q3 提交后按间隔挪优先级", pq.locate(6), 9)

# ---- ItemDelay 存法（#11）
v(推演, "#11 1.01 → word 1", delay_text_to_word("1.01", False, 7), 1)
v(推演, "#11 item 上限 5.0", delay_text_to_word("9", False, 7), 400)
v(推演, "#11 topic 上限 20.0", delay_text_to_word("30", True, 7), 1900)
v(推演, "#11 下限 1.01", delay_text_to_word("1.0", True, 7), 1)
v(推演, "#11 解析失败不变", delay_text_to_word("x", True, 7), 7)
v(推演, "#11 显示 1+w/100", delay_word_to_mult(1), 1.01)

# ---- 逐元素推迟天数（#10）
S = PostponeSettings(item_delay_word=50, topic_delay_word=50, simulate=1)
c = coll_with(100, {1: mk(etype=1, last=90, iv=10)})
v(推演, "#10 extra 减 base（prio 100）", postpone_extra(c, c.elements[1], 100.0, S, None), (10, 2.0))
v(推演, "#10 sqrt 项（prio 25）", postpone_extra(c, c.elements[1], 25.0, S, None)[0], 5)
c = coll_with(100, {1: mk(etype=1, last=50, iv=10)})
v(推演, "#10 base=today-last 50", postpone_extra(c, c.elements[1], 100.0, S, None), (50, 2.0))
c = coll_with(100, {1: mk(etype=1, last=100, iv=0)})
v(推演, "#10 base 至少 1（LastRep=today, iv=0）", postpone_extra(c, c.elements[1], 100.0, S, None), (2, 3.0))
v(推演, "#12 edi=0 写回 → today+1 而非 today+extra", write_postponed_date(c, 1, 3.0), 101)
c = coll_with(100, {1: mk(etype=3, last=0, iv=100)})
S2 = PostponeSettings(topic_max=1, topic_prio_th=50.0, simulate=1)
v(推演, "#10 其他 etype 1.01 不钳不保护", postpone_extra(c, c.elements[1], 100.0, S2, None)[0], 2)
c = coll_with(100, {1: mk(etype=1, last=90, iv=10)})
S3 = PostponeSettings(item_delay_word=50, item_min=30, simulate=1)
v(推演, "#10 钳到 item 下限", postpone_extra(c, c.elements[1], 100.0, S3, None)[0], 30)
S4 = PostponeSettings(item_delay_word=50)
v(推演, "#10 非模拟走 disperse(extra, extra/2)，d=4 会得 11",
  postpone_extra(c, c.elements[1], 100.0, S4, seq(0.8, 0.3))[0], 12)
el = c.elements[1]
v(推演, "#10 item 阈值 > prio 跳过", postpone_protected(c, el, 10, 4.9, PostponeSettings(item_prio_th=5.0)), True)
v(推演, "#10 阈值 = prio 不跳过", postpone_protected(c, el, 10, 5.0, PostponeSettings(item_prio_th=5.0)), False)
v(推演, "#10 prio NaN 不受保护", postpone_protected(c, el, 10, math.nan, PostponeSettings(item_prio_th=5.0)), False)
# 按 2026-10-19 补查裁决改：topic 保护方向是 AF ≤ 阈值（原两条期望按「AF > 阈值」写）
t = mk(etype=0, af=2.0)
v(推演, "#10 topic AF = 阈值 跳过", postpone_protected(c, t, 10, 50.0, PostponeSettings(topic_skip_af=2.0)), True)
t.af = 2.0001
v(推演, "#10 topic AF > 阈值 不跳过", postpone_protected(c, t, 10, 50.0, PostponeSettings(topic_skip_af=2.0)), False)
FD = PostponeSettings.factory_defaults()
v(推演, "Q2 出厂 AF 阈值 1.01：AF 1.01 受保护", postpone_protected(c, mk(etype=0, af=1.01), 10, 50.0, FD), True)
v(推演, "Q2 出厂 AF 阈值 1.01：AF 1.3 不受保护", postpone_protected(c, mk(etype=0, af=1.3), 10, 50.0, FD), False)
v(推演, "Q2 topic AF NaN 不受保护", postpone_protected(c, mk(etype=0, af=math.nan), 10, 50.0, PostponeSettings(topic_skip_af=1.01)), False)
v(推演, "Q2 出厂 item 整类跳过", postpone_protected(c, mk(etype=1, fi=10), 10, 50.0, FD), True)
v(推演, "Q2 出厂 Delay 1.2 → word 20", delay_text_to_word("1.2", False, 0), FD.item_delay_word)
v(推演, "Q2 出厂 word 20 → 倍率 1.2", delay_word_to_mult(FD.item_delay_word), 1.2)
# 保护边界（base ≥、计数 ≥、FI <、整类跳过）
P = PostponeSettings
for _k, _e in (("item", 1), ("topic", 0)):
    _el = mk(etype=_e, counter_35=5)
    for _b, _w in ((9, False), (10, True), (11, True)):
        v(推演, "%s base %d vs 阈值10" % (_k, _b), postpone_protected(c, _el, _b, 50.0, P(**{_k + "_skip_base": 10})), _w)
    for _n, _w in ((6, False), (5, True), (4, True)):
        v(推演, "%s 计数5 vs 阈值%d" % (_k, _n), postpone_protected(c, _el, 10, 50.0, P(**{_k + "_skip_count": _n})), _w)
    v(推演, "%s 整类跳过" % _k, postpone_protected(c, _el, 10, 50.0, P(**{"skip_%ss" % _k: 1})), True)
v(推演, "默认计数阈值 254 不保护", postpone_protected(c, mk(counter_35=254), 10, 50.0, P()), False)
v(推演, "默认计数阈值 255 保护", postpone_protected(c, mk(counter_35=255), 10, 50.0, P()), True)
v(推演, "topic 默认计数 255 保护", postpone_protected(c, mk(etype=0, counter_35=255), 10, 50.0, P()), True)
for _fi, _w in ((4, True), (5, False), (6, False)):
    v(推演, "item FI %d vs 阈值5（严格小于）" % _fi, postpone_protected(c, mk(fi=_fi), 10, 50.0, P(item_skip_fi=5)), _w)
c.default_fi = 4
v(推演, "FI=0 回退集合默认 4 → 保护", postpone_protected(c, mk(fi=0), 10, 50.0, P(item_skip_fi=5)), True)
c.default_fi = 6
v(推演, "FI=0 回退集合默认 6 → 不保护", postpone_protected(c, mk(fi=0), 10, 50.0, P(item_skip_fi=5)), False)
c.default_fi = 0
SP = PostponeSettings(spread=1, item_min=10, item_max=110, item_prio_th=5.0, simulate=1)
v(推演, "#10 铺开分支 不保护", postpone_extra(c, c.elements[1], 1.0, SP, None), (11, 2.1))
v(推演, "#10 铺开分支 min+R((max-min)p)", postpone_extra(c, c.elements[1], 50.0, SP, None), (60, 7.0))

# ---- 写回日期（#12 #7）
c = coll_with(100, {1: mk(etype=1, last=90, iv=10, real_22=1.5, counter_31=4, counter_35=2, af=2.5)})
c.outstanding = [1]
v(推演, "#12 新日期 = last + R(edi·ratio)", write_postponed_date(c, 1, 2.0), 110)
el = c.elements[1]
v(推演, "#12 间隔 = 新-last", el.interval, 20)
v(推演, "#12 +0x35 计数 +1", el.counter_35, 3)
v(推演, "#12 +0x31 计数 +1", el.counter_31, 5)
v(推演, "#12 +0x22 按新/旧缩放", el.real_22, 3.0)
v(推演, "#12 不动 AF", el.af, 2.5)
v(推演, "#7 推到今天之后 → 移出当天名单", c.outstanding, [])
v(推演, "#12 RepDates 已写", c.rep_dates[1], 110)
c = coll_with(100, {1: mk(etype=0, last=50, iv=10)})
v(推演, "#12 topic 也推迟，edi 取逾期天数", write_postponed_date(c, 1, 1.5), 125)
c = coll_with(100, {1: mk(etype=1, status=0, last=90, iv=10)})
v(推演, "#12 status≠1 不写", write_postponed_date(c, 1, 2.0), None)
c = coll_with(100, {1: mk(etype=1, last=90, iv=10)})
v(推演, "#12 iv≤edi → edi+1", write_postponed_date(c, 1, 1.0), 101)
c = coll_with(10, {1: mk(etype=1, last=0, iv=40000)})
v(推演, "#12 上限 44530", write_postponed_date(c, 1, 2.0), 44530)
c = coll_with(44530, {1: mk(etype=1, last=0, iv=40000)})
v(推演, "#12 碰上限 → 新日期=today，不是明天",
  run_postpone(c, [1], PostponeSettings(item_delay_word=50), lambda i: 100.0, lambda i: i, ZERO), [1])
v(推演, "#12 碰上限 RepDates", c.rep_dates[1], 44530)
v(推演, "#12 碰上限 仍在当天名单", c.outstanding, [1])
c = coll_with(100, {1: mk(etype=1, last=80, iv=30, counter_35=0)})
commit_new_date(c, 1, 100)
v(推演, "#7 新日期 ≤ today 加回名单", c.outstanding, [1])
v(推演, "#12 变短不加计数", c.elements[1].counter_35, 0)
c = coll_with(100, {1: mk(etype=1, last=80, iv=30)})
commit_new_date(c, 1, 70)
v(推演, "#12 新日期 ≤ last → 间隔1 last=新-1", (c.elements[1].interval, c.elements[1].last_day, c.elements[1].real_22), (1, 69, 1.0))

# ---- 当天名单（#7）
c = coll_with(100, {1: mk(etype=0, last=85, iv=10), 2: mk(etype=1, last=90, iv=10),
                    3: mk(etype=1, last=91, iv=10), 4: mk(etype=1, last=40, iv=9)})
c.rep_dates[4] = 50                             # 与 last+iv 对不上
v(推演, "#7 收 [cursor,today]，逾期也收，items 在前", c.build_outstanding(), [2, 1])
v(推演, "#7 自动推迟窗口 today-1", c.collect(1, 99), [1])
c = Collection(today=10, rep_dates={1: 5, 2: 8}, cursor_11a=1)
c.advance_cursor()
v(推演, "#7 逾期游标跳过空日", c.cursor_11a, 5)
c = coll_with(100, {1: mk(last=80, iv=10)})
c.cursor_11a = 1
v(推演, "#7 收集入口推进游标（本次下界仍用传入值）", (c.build_outstanding(), c.cursor_11a), ([1], 90))
c = Collection(today=10, cursor_11a=1)
c.advance_cursor()
v(推演, "#7 游标不超过 today", c.cursor_11a, 10)
c = coll_with(100, {})
c.cursor_11a = 50
c.elements[9] = mk(last=30, iv=10)
c.schedule_repetition(9, 40)
v(推演, "#7 写到更早日期时下调 cursor", c.cursor_11a, 40)

# ---- 执行器（#9）
def five(prios):
    c = coll_with(100, {i: mk(etype=1, last=90, iv=10) for i in range(1, 6)})
    return c, (lambda i: prios[i]), (lambda i: i)


S = PostponeSettings(scope=1, keep_n=2, item_delay_word=50, simulate=0)
c, pr, pos = five({i: 100.0 for i in range(1, 6)})
v(实测, "#9 从队尾往前推，留队首 N 个（第八轮）", run_postpone(c, [5, 3, 1, 2, 4], S, pr, pos, ZERO), [5, 4, 3])
v(实测, "#9 队首未动", (c.rep_dates[1], c.rep_dates[2]), (100, 100))
c, pr, pos = five({i: 100.0 for i in range(1, 6)})
v(推演, "#9 排序方向可切", run_postpone(c, [1, 2, 3, 4, 5], S, pr, pos, ZERO, reverse=False), [1, 2, 3])
S = PostponeSettings(scope=1, keep_n=1, item_delay_word=50, item_prio_th=5.0)
c, pr, pos = five({1: 1.0, 2: 1.0, 3: 50.0, 4: 50.0, 5: 50.0})
v(推演, "#9 剩余仍 > N 跑第二遍（铺开）", run_postpone(c, [1, 2, 3, 4, 5], S, pr, pos, ZERO), [5, 4, 3, 2])
S = PostponeSettings(scope=0, keep_n=1, item_delay_word=50, item_prio_th=5.0)
c, pr, pos = five({1: 1.0, 2: 1.0, 3: 50.0, 4: 50.0, 5: 50.0})
v(推演, "#9 scope=0 无配额无第二遍", run_postpone(c, [1, 2, 3, 4, 5], S, pr, pos, ZERO), [3, 4, 5])
c, pr, pos = five({i: 100.0 for i in range(1, 6)})
c.elements[2].status = 3
c.elements[3].last_day = 95                    # 未到期
v(推演, "#9 删除 / 未到期跳过", run_postpone(c, [1, 2, 3], PostponeSettings(simulate=1), pr, pos, ZERO), [1])
v(推演, "#9 模拟不写日期", c.rep_dates[1], 100)

# ---- 第八轮原版逐篇实测（11-07，auto_runtime，N 强制 5）：(元素, 优先级, base, r1, r2, 抖动返回, 最终天数)
R8 = [(26, 100.0, 10, 0.18150554783642292, 0.7736642903182656, 9.784961203640165, 10),
      (2, 96.42857142857143, 10, 0.7167122694663703, 0.8044051395263523, 8.657923396008547, 9),
      (8, 92.85714285714286, 15, 0.661042564548552, 0.06463607889600098, 14.499543482891074, 14),
      (4, 89.28571428571429, 10, 0.08234067494049668, 0.4080741673242301, 9.083084291436707, 9),
      (25, 85.71428571428571, 10, 0.6654211431741714, 0.5586883577052504, 7.949522773328624, 8),
      (6, 82.14285714285714, 10, 0.6233599348925054, 0.01676448411308229, 9.937995660160716, 10),
      (9, 78.57142857142857, 14, 0.9758662497624755, 0.19099869136698544, 16.405990356013646, 16),
      (24, 75.0, 10, 0.9109215443022549, 0.7125519241672009, 6.732979321696387, 7),
      (3, 71.42857142857143, 16, 0.8843488525599241, 0.579380905488506, 10.834023937505382, 11),
      (23, 64.28571428571429, 10, 0.5738895530812442, 0.08873134641908109, 8.72924333229862, 9),
      (10, 60.71428571428571, 10, 0.35221629310399294, 0.25493694213218987, 8.372395312577417, 8),
      (5, 57.14285714285714, 10, 0.639599843416363, 0.891113021178171, 7.128973624324893, 7),
      (11, 53.57142857142857, 10, 0.9041742198169231, 0.5694665277842432, 5.041982040458596, 5),
      (22, 50.0, 10, 0.2584084696136415, 0.5782643293496221, 6.743372506389428, 7),
      (7, 46.42857142857143, 10, 0.11699508409947157, 0.5765096538234502, 6.893084238998251, 7),
      (21, 42.857142857142854, 10, 0.2964040604420006, 0.22257177415303886, 7.301675482183718, 7),
      (20, 39.285714285714285, 10, 0.8123281989246607, 0.4328968694899231, 7.416077017661412, 7),
      (19, 35.714285714285715, 10, 0.5306592839770019, 0.42399830534122884, 6.6471816785551185, 7),
      (12, 32.142857142857146, 10, 0.31298635993152857, 0.11768238735385239, 6.3220924508692455, 6)]
AR = PostponeSettings.auto_runtime()
for el_id, p, base, r1, r2, raw, days in R8:
    c = coll_with(20, {el_id: mk(etype=0, last=20 - base, iv=1, af=1.5)})
    x = R(2 * (R(base * 1.5) - base) * math.sqrt(p / 100.0))
    v(实测, "#10 第八轮 #%d 抖动返回" % el_id, disperse(float(min(max(x, 6), 100)), min(max(x, 6), 100) * 0.5, seq(r1, r2)), raw, tol=1e-12)
    v(实测, "#10 第八轮 #%d 推几天" % el_id, postpone_extra(c, c.elements[el_id], p, AR, seq(r1, r2)), (days, (base + days) / base))
v(实测, "#9 第八轮：处理顺序按优先级从大到小", [r[1] for r in R8] == sorted([r[1] for r in R8], reverse=True), True)

# ---- 第九轮原版逐次实测（11-07，Learn 点 5 篇，mode=1）：(旧, AF, x, d, r1, r2, 抖动返回, 新间隔)，x、d 是日志 [N3] 原值
R9 = [(1, 1.4118122977342864, 1.0, 0.0, 0.37749489839188755, 0.8341190367937088, 1.0, 2),
      (1, 1.4118122977342864, 1.0, 0.0, 0.32264901720918715, 0.6080191894434392, 1.0, 2),
      (1, 1.4118122977342864, 1.0, 0.0, 0.5768405420240015, 0.022645465098321438, 1.7351381295228463, 2),
      (1, 1.75, 2.0, 1.0, 0.9693893969524652, 0.0878482167609036, 4.787243100210739, 5),
      (1, 1.75, 2.0, 1.0, 0.8345510091166943, 0.7436728905886412, 1.0, 2),
      (1, 1.75, 2.0, 1.0, 0.43514416203834116, 0.21092116786167026, 2.489408683861026, 2),
      (1, 1.4118122977342864, 1.0, 0.0, 0.8774660804774612, 0.3762732641771436, 2.7628802442995433, 3),
      (1, 1.4118122977342864, 1.0, 0.0, 0.08963830140419304, 0.9476891593076289, 1.0, 2),
      (1, 1.4118122977342864, 1.0, 0.0, 0.9169721982907504, 0.5230330936610699, 1.0, 2),
      (1, 1.4118122977342864, 1.0, 0.0, 0.42407583841122687, 0.8955297297798097, 1.0, 2),
      (1, 1.4118122977342864, 1.0, 0.0, 0.3967441653367132, 0.4362619398161769, 1.4332606349152104, 2),
      (1, 1.4118122977342864, 1.0, 0.0, 0.6196823113132268, 0.3089592424221337, 1.825555224527318, 2),
      (1, 1.4118122977342864, 1.0, 0.0, 0.08130715670995414, 0.1483024749904871, 1.0728857142332626, 2),
      (1, 1.4118122977342864, 1.0, 0.0, 0.6367550662253052, 0.7323843496851623, 1.0, 2),
      (1, 1.4118122977342864, 1.0, 0.0, 0.15729404403828084, 0.6653171041980386, 1.0, 2)]
for i, (old, af, x, d, r1, r2, raw, new) in enumerate(R9, 1):
    with mock.patch('schedule.disperse', wraps=disperse) as spy:   # 抓 topic_next_interval 实际传给 disperse 的 x、d
        got = topic_next_interval(old, af, 1, seq(r1, r2))
    v(实测, "#3 第九轮 %d 传给抖动的 x、d" % i, spy.call_args.args[:2], (x, d))
    v(实测, "#3 第九轮 %d 抖动返回" % i, disperse(x, d, seq(r1, r2)), raw)
    v(实测, "#3 第九轮 %d 新间隔" % i, got, new)
v(实测, "#5 第九轮 AF 调整 1.41", adjust_af(1.4118122977342864, 1, 2, False), 1.4590843327618495)
v(实测, "#5 第九轮 AF 调整 1.75", adjust_af(1.75, 1, 2, False), 1.8370588235294119)


# ---- 自动推迟触发（#8）
def scene(n_today, n_over):
    els = {}
    for i in range(1, n_today + 1):
        els[i] = mk(etype=1, last=90, iv=10)        # 今天到期
    for i in range(n_today + 1, n_today + n_over + 1):
        els[i] = mk(etype=0, last=80, iv=10)        # 逾期（昨天及以前）
    c = coll_with(100, els)
    c.build_outstanding()
    return c


SA = PostponeSettings(item_delay_word=50, topic_delay_word=50)
PR, POS = (lambda i: 100.0), (lambda i: i)
c = scene(0, 11)
st = AutoState(last_run_day=99)
v(推演, "#8 11/11 → 执行", auto_postpone(c, st, 0, 0.0, SA, PR, POS, ZERO), "ran")
v(推演, "#8 执行后写 4c5", st.last_run_day, 100)
v(推演, "#7 推迟后移出当天名单", c.outstanding, [])
v(推演, "#8 再跑一次 → 今天已跑", auto_postpone(c, st, 0, 0.0, SA, PR, POS, ZERO), "already_ran")
c = scene(0, 11)
c.outstanding = c.outstanding[:10]
st = AutoState()
v(推演, "#8 门 A：名单 ≤10", auto_postpone(c, st, 0, 0.0, SA, PR, POS, ZERO), "gate_a")
v(推演, "#8 门 A 前已写 4c5", st.last_run_day, 100)
c = scene(20, 10)
v(推演, "#8 门 B：逾期集 ≤10（名单 30）", auto_postpone(c, AutoState(), 0, 0.0, SA, PR, POS, ZERO), "gate_b")
v(推演, "#8 门 B 不动日期", c.rep_dates[21], 90)
v(推演, "#8 开关关", auto_postpone(scene(0, 11), AutoState(switch_on=False), 0, 0.0, SA, PR, POS, ZERO), "off")
st = AutoState(field_109=1, last_used=100.0, last_run_day=7)
v(推演, "#8 久未用 → 关开关", auto_postpone(scene(0, 11), st, 0, 110.5, SA, PR, POS, ZERO), "turned_off")
v(推演, "#8 关开关且不写 4c5", (st.switch_on, st.last_run_day), (False, 7))
st = AutoState(field_109=1, last_used=100.0)
v(推演, "#8 dl≠0 不关", auto_postpone(scene(0, 11), st, 1, 110.5, SA, PR, POS, ZERO), "ran")
c = scene(0, 24)
AR = PostponeSettings.auto_runtime()
v(实测, "#8 第六轮：运行时 Skip top 50，逾期 24 篇 → 进执行器", auto_postpone(c, AutoState(), 1, 0.0, AR, PR, POS, ZERO), "ran")
v(实测, "#8 第六轮：24 ≤ 50 第一篇就停，日期不动", (len(c.outstanding), c.rep_dates[1]), (24, 90))
v(实测, "#5.1 第六轮：运行时块 +0x05/+0x10/+0x20/+0x0f", (AR.scope, AR.keep_n, AR.skip_items, AR.sub_branch), (1, 50, 0, 1))
v(推演, "#8 恰 10.0 天不关", auto_postpone(scene(0, 11), AutoState(field_109=1, last_used=100.0), 0, 110.0,
                                     SA, PR, POS, ZERO), "ran")
v(推演, "#8 NaN 不关", auto_postpone(scene(0, 11), AutoState(field_109=1, last_used=math.nan), 0, 110.5,
                                   SA, PR, POS, ZERO), "ran")
v(推演, "#8 109≤0 不关", auto_postpone(scene(0, 11), AutoState(field_109=0, last_used=0.0), 0, 110.5,
                                    SA, PR, POS, ZERO), "ran")

print("ALL PASSED: %d 条（原版实测 %d 条，公式推演 %d 条）" % (N, BY_KIND[实测], BY_KIND[推演]))
