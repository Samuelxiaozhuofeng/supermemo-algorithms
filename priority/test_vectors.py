"""SPEC.md §测试向量 的断言版。任何一条失败即非 0 退出。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from priority import *


def close(a, b, eps=1e-4):
    return abs(a - b) < eps


# T1 pos_to_priority
assert pos_to_priority(1, 101) == 0.0
assert pos_to_priority(2, 101) == 1.0
assert pos_to_priority(51, 101) == 50.0
assert pos_to_priority(101, 101) == 100.0
assert pos_to_priority(2, 2) == 100.0
assert close(pos_to_priority(5, 10), 44.4444)

# T2 priority_to_index / bucket20
assert priority_to_index(50.0, 101) == 51
assert priority_to_index(33.3, 10) == 4
assert [priority_to_bucket20(p) for p in (1.0, 6.25, 50.0, 100.0, 0.00005)] == [6, 10, 17, 20, 1]

# T3 set_priority 往返
q = PriorityQueue(range(1, 11))
assert close(q.get_priority(5), 44.4444)
q.set_priority(5, 50.0)
assert q.items == list(range(1, 11)) and close(q.get_priority(5), 44.4444)
q.set_priority(1, 100.0)
assert q.items[-1] == 1
q.set_priority(10, 0.0)
assert q.items[0] == 10 and q.get_priority(10) == 0.0

# T3b 无效元素门：set_priority 直接 return
q = PriorityQueue(range(1, 11), is_valid=lambda el: el != 5)
q.set_priority(5, 0.0)
assert q.items == list(range(1, 11))

# T4 缺失自修复；已删除则不修复（定案 2）；count<2 直接 0.0
q = PriorityQueue([1, 2, 3])
assert q.get_priority(99) == 0.0 and q.items == [99, 1, 2, 3]
q = PriorityQueue([1, 2, 3])
assert q.get_priority(99, is_deleted=lambda el: True) == 0.0 and q.items == [1, 2, 3]
assert q.get_priority(0) == 0.0 and q.items == [1, 2, 3]
q = PriorityQueue([7])
assert q.get_priority(7) == 0.0 and q.get_priority(99) == 0.0 and q.items == [7]

# T5 change_priority_by
q = PriorityQueue(range(1, 102))
q.change_priority_by(51, -0.1)
assert q.locate(51) == 51
q = PriorityQueue([1, 2, 3])                  # 微量守卫：对缺席元素测，守卫失效会自修复把 99 入队
q.change_priority_by(99, 1e-6)
assert q.items == [1, 2, 3]

# T6 默认值入队
q = PriorityQueue(range(1, 102))
q.add_new_element(999)
assert q.locate(999) == 6 and close(q.get_priority(999), 4.9505)

# T7 spread（len=100, rand=0.5）
for p, want in ((5, 5.2347), (31, 23.6065), (50, 36.5396), (100, 70.3841), (0, 0.0)):
    assert close(spread_priority(p, 100, lambda: 0.5), want), p

# T8 create_extract：[1..101]，父 51，len=100，rand=0.5。两种时序在这一组上碰巧结果相同
for order in ('enqueue_first', 'parent_first'):
    q = PriorityQueue(range(1, 102))
    create_extract(q, 51, 999, 100, lambda: 0.5, True, order)
    assert close(q.get_priority(51), 50.4950) and q.locate(999) == 38, order
    assert close(q.get_priority(999), 36.6337), order

# T9 interleave
out = interleave([f"I{i}" for i in range(1, 21)], [f"T{i}" for i in range(1, 21)], 5.0)
assert all(x.startswith('I') for x in out[:19]) and out[19] == 'T1'

# T10 randomized_draw
seq = iter([0.9, 0.1, 0.5, 0.5, 0.9, 0.9, 0.2, 0.2, 0.9, 0.9, 0.9, 0.9])
assert randomized_draw(list('ABCDE'), 8.0, lambda: next(seq)) == list('ACBDE')

# T11 trackbar_to_factor
for pos, want in ((0, 0.001), (1, 0.6), (25, 1.0), (50, 8.8701), (75, 14.9090), (100, 1000.0)):
    assert close(trackbar_to_factor(pos), want), pos

# T12 batch 单值
assert batch_modify_priority(2.0, 'increase', 50, 1, 50) == 1.0
assert batch_modify_priority(2.0, 'increase', 150, 1, 50) == 2.0
assert batch_modify_priority(2.0, 'decrease', 150, 1, 50) == 3.0
assert batch_modify_priority(0, 'spread_linear', min_pct=1, k=5, step=2) == 9.0
assert batch_modify_priority(30.0, 'spread_proportional', min_pct=1, max_pct=50,
                             old_min=10, old_max=50) == 25.5

# T13 取整 .5 与批量顺序
q = PriorityQueue(range(1, 11))
q.set_priority(5, 50.0)
assert q.locate(5) == 5
assert (Round(4.5), Round(5.5), Round(2.5), Round(-2.5)) == (4, 6, 2, -2)
assert batch_modify_priority(80.0, 'decrease', 150, 1, 50) == 50.0

# T13b 批量驱动：状态字节、已删除跳过、step 公式（新语义：状态 2 占 k 不写，已删除不占 k；本条期望值不变）
q = PriorityQueue(range(1, 101))
batch_apply(q, [10, 20, 30], 'spread_linear', min_pct=0.0, max_pct=60.0,
            status_of=lambda el: 2 if el == 20 else 0)
assert q.locate(20) == 20                     # 状态字节 2 → 占 k 不写
assert q.locate(10) == 1                      # k=1 → 0.0
assert q.locate(30) == 60                     # k=3, step=max(60/2, 100/100)=30 → P=60 → Round(60/100*99)+1=60
# 已删除不占 k：[a, 已删除, b] 线性铺开，b 拿第 2 个序号的值（step=max(60/2,1)=30 → P=30 → 第 31 位）
q = PriorityQueue(range(1, 101))
batch_apply(q, [10, 20, 30], 'spread_linear', min_pct=0.0, max_pct=60.0,
            status_of=lambda el: 3 if el == 20 else 0)
assert q.locate(30) == 31 and q.locate(20) == 20
# 状态 2 占 k：b 拿第 3 个序号的值，状态 2 那张不动
q = PriorityQueue(range(1, 101))
batch_apply(q, [10, 70, 30], 'spread_linear', min_pct=0.0, max_pct=60.0,
            status_of=lambda el: 2 if el == 70 else 0)
assert q.locate(30) == 60 and q.locate(70) == 70
q = PriorityQueue(range(1, 101))
batch_apply(q, [50], 'decrease', 150, 1, 50, is_deleted=lambda el: True)
assert q.locate(50) == 50
# step 下限：max(1/2, 100/100)=1 → #20 写 P=1 到第 2 位，#30 也写 P=1 插到第 2 位把它挤到第 3 位
q = PriorityQueue(range(1, 101))
batch_apply(q, [10, 20, 30], 'spread_linear', min_pct=0.0, max_pct=1.0)
assert q.locate(20) == 3
# oldP 现读：#81 先挪到第 41 位，#59 被挤到第 60 位，现读 P=59 → 29.5 → 第 31 位（预读 58 会给 30）
q = PriorityQueue(range(1, 102))
batch_apply(q, [81, 59], 'increase', 50, 0.0, 100.0)
assert q.locate(59) == 31
# 比例铺开：区分「oldMin/oldMax 预扫后固定」与「每次现读」。#11、#91 先被挪走后，
# 现读极值会变成 20/60，#51 算出 50 留在第 51 位；预扫固定 10/90 → P=40 → 第 41 位
q = PriorityQueue(range(1, 102))
assert batch_apply(q, [11, 91, 51], 'spread_proportional', min_pct=20.0, max_pct=60.0)
assert [q.locate(e) for e in (11, 91, 51)] == [21, 61, 41]
# 比例铺开容量不足：minPos=maxPos=1，3 个元素容不下 → 中止、整批不动
q = PriorityQueue(range(1, 101))
assert batch_apply(q, [10, 20, 30], 'spread_proportional', min_pct=0.0, max_pct=0.0001) is False
assert q.items == list(range(1, 101))
# 参数规范化：min>max 交换成 20/60，oldP=50 原地不动（不交换会被尾部压到 20）
q = PriorityQueue(range(1, 102))
batch_apply(q, [51], 'increase', 100, 60.0, 20.0)
assert q.locate(51) == 51
# change 钳到 1000：#11（P=1）×10 → P=10 → 第 101 位（不钳会 ×20 → 第 201 位）
q = PriorityQueue(range(1, 1002))
batch_apply(q, [11], 'decrease', 2000, 0.0, 100.0)
assert q.locate(11) == 101
# min 钳到 99：P=50 → 下钳 99 → 第 100 位（不钳 99.5 → Round(99.5)=100 → 追加到第 101 位）
q = PriorityQueue(range(1, 102))
batch_apply(q, [51], 'decrease', 100, 99.5, 100.0)
assert q.locate(51) == 100
# 先钳后换：min=150→99，再与 max=50 交换成 [50,99]；P=50×10 → 上钳 99 → 第 100 位
# （先换后钳会得 [50,100] → P=100 → 追加到第 101 位）
q = PriorityQueue(range(1, 102))
batch_apply(q, [51], 'decrease', 1000, 150.0, 50.0)
assert q.locate(51) == 100
# max 钳到 [0.0001,100] 无可观测向量：>100 会被 set_priority 再钳一次；0 与 0.0001 要队列 ≥50 万才差一位

# T14 两种摘录时序：10 元素，父在第 1 位，len=0，rand=0.5 → 父与新元素位置对调
q = PriorityQueue(range(1, 11))
create_extract(q, 1, 999, 0, lambda: 0.5, True, 'enqueue_first')
assert q.items[:2] == [1, 999]
q = PriorityQueue(range(1, 11))
create_extract(q, 1, 999, 0, lambda: 0.5, True, 'parent_first')
assert q.items[:2] == [999, 1]
# 不 spread：父照样 ×0.995，新元素停在默认 5.0
q = PriorityQueue(range(1, 102))
create_extract(q, 51, 999, 100, lambda: 0.5, False)
assert q.locate(999) == 6 and q.locate(51) == 52

# T15 排序键用 Round 不用 trunc
p = 50.00004
assert int((100.0 - p) * 10000.0) != repetition_sort_key(p, 1)
assert repetition_sort_key(p, 1) == 500000
assert repetition_sort_key(3.0, 0) == 0 and repetition_sort_key(3.0, 5, lambda el: True) == 0

# T16 复习打分后自动调优先级
for grade, want in ((3, 5006), (4, 5016), (5, 5031)):   # 每次全新队列，分别测三个系数
    q = PriorityQueue(range(1, 10002))
    on_item_graded(q, 5001, grade)
    assert q.locate(5001) == want, grade
before = list(q.items)
on_item_graded(q, 5001, 2)
on_item_graded(q, 5001, 5, window_mode=7)
on_item_graded(q, 5001, 5, afactor=0.0)
on_item_graded(q, 5001, 5, alarm_cancelled=True)      # 间隔过短警报被取消 → 整单取消
assert q.items == before
q = PriorityQueue(range(1, 102))
on_item_graded(q, 51, 3)                      # 小队列 +0.05 挪不动
assert q.locate(51) == 51

# T17 复习后按间隔挪优先级 0xc99b30（原版实测：2026-10-19 第二轮界面实测，回放见
# schedule/逆向证据/补查_2026-10-19/q3_复习后挪位_回放.py；该脚本未随本仓库公开，结论见 SPEC.md §4.9）
def replay(start, revs):
    q = PriorityQueue(start)
    for el, o, nw in revs:
        adjust_priority_by_interval(q, el, o, nw)
    return q.items

# 原版实测：单篇
assert replay([7, 11, 5, 10, 1, 9, 8, 4, 3, 6, 2], [(8, 3, 7)]) == [7, 11, 5, 10, 1, 9, 4, 3, 6, 2, 8]   # 10-23
assert replay([7, 11, 5, 10, 1, 9, 4, 3, 6, 2, 8], [(9, 4, 7)]) == [7, 11, 5, 10, 1, 4, 3, 6, 9, 2, 8]   # 10-24
# 原版实测：10-28 按复习前队列顺序依次复习
D28 = {7: (3, 4), 10: (4, 6), 11: (3, 5), 5: (5, 7), 6: (3, 4), 2: (3, 5), 4: (3, 7)}
assert replay([7, 11, 5, 10, 1, 4, 3, 6, 9, 2, 8], [(e,) + D28[e] for e in [7, 11, 5, 10, 4, 6, 2]]) \
    == [7, 11, 5, 10, 1, 3, 9, 6, 4, 8, 2]
# 原版实测：10-20 全部第 2 次复习（旧间隔都是 1），回放在 363 万种顺序里找到 45 种能复现，这是其中一种
D20 = {7: (1, 2), 8: (1, 3), 10: (1, 2), 11: (1, 2), 9: (1, 4), 4: (1, 2), 2: (1, 2), 6: (1, 2), 5: (1, 5), 3: (1, 2)}
assert replay([7, 11, 10, 9, 8, 5, 6, 4, 3, 2, 1], [(e,) + D20[e] for e in [7, 11, 6, 8, 9, 10, 5, 2, 3, 4]]) \
    == [7, 11, 10, 5, 1, 4, 9, 3, 2, 8, 6]
# 原版实测：10-22 回放找到的一种复习顺序
D22 = {7: (2, 3), 10: (2, 4), 11: (2, 3), 4: (2, 3), 2: (2, 3), 6: (2, 3), 3: (2, 7)}
assert replay([7, 11, 10, 5, 1, 4, 9, 3, 2, 8, 6], [(e,) + D22[e] for e in [7, 10, 11, 3, 6, 2, 4]]) \
    == [7, 11, 5, 10, 1, 9, 8, 4, 3, 6, 2]
# 公式推演：间隔变短往前挪（第 6 位 P=50，10→5：f=0.6 → P=30 → 第 4 位）
assert replay(range(1, 12), [(6, 10, 5)]) == [1, 2, 3, 6, 4, 5, 7, 8, 9, 10, 11]
# 公式推演：第 1 位间隔变长，P 仍为 0，保底挪到第 2 位
assert replay(range(1, 12), [(1, 2, 3)])[:2] == [2, 1]
# 公式推演：新 == 旧不动；旧 0 按 1 算（0→1 不动）
assert replay(range(1, 12), [(6, 5, 5), (6, 0, 1)]) == list(range(1, 12))

print("all vectors passed")
