# SuperMemo 20 algorithms, reverse-engineered

[简体中文](README.md) | English

A clean-room re-description of three algorithms in **SuperMemo 20** for incremental reading:

1. **Priority queue**: how priorities are stored, defaults, extract priority, batch changes, the post-review shift, and daily queue sorting.
2. **Topic scheduling** for articles and extracts: initial A-Factor and interval, extract A-Factor, and the new interval and A-Factor after a topic review.
3. **Auto-postpone**: trigger, gates, protections, days postponed per element, and write-back.

Target binary: SuperMemo 20, Build 20.00.34. Two copies of `sm20.exe` were used:

| Used for | SHA-256 |
|---|---|
| Static disassembly (all addresses in the specs refer to this one) | `c58f89df51b6cf118ed8ca76a52017e2e7a82aa20ce3656d6e23d5801f0ccf68` |
| Runtime measurements on Windows | `D01F16976E10F68FDD2E0503E87BEAF74D65481BB8456E69FB1CD5DAF9AAD7C0` |

The two files differ. The functions we use contain the same instructions but sit at shifted addresses, so addresses from one file do not work in the other. Both files have ASLR enabled.

This is an **unofficial** project with no connection to SuperMemo World. It contains **no SuperMemo code or binaries**.

## Contents

| Path | What |
|---|---|
| `priority/SPEC.md` | Priority algorithm spec (Chinese) |
| `priority/priority.py` | Reference implementation |
| `priority/test_vectors.py` | Assertion tests |
| `schedule/SPEC.md` | Topic scheduling + auto-postpone spec (Chinese) |
| `schedule/schedule.py` | Reference implementation (imports `../priority/priority.py`) |
| `schedule/test_vectors.py` | Assertion tests (245 vectors, 93 of them use measured data from the original) |
| `measurements/` | UI measurement scripts (`实测提示词_*.md`), raw readings (`results_*.jsonl`), and reports (`实测报告_*.md`) for rounds 1–3 |

The specs are written in Chinese. The pseudocode, addresses and tables can be read without the prose.

## How it was reverse-engineered

1. **Static disassembly.** `sm20.exe` is a 64-bit Delphi PE. Small scripts built on `capstone` and `pefile` handled disassembly, finding callers, and matching functions between the two exe copies. Several AI reverse-engineering agents each wrote a spec independently. For scheduling, two full spec packages (called "M" and "G" in the spec) were compared. Wherever they disagreed, four more agents each checked the point against the disassembly ("裁决 N" in the spec), and key instructions were spot-checked by hand. The priority spec went through the same kind of cross-audit. Rejected claims are listed in `schedule/SPEC.md` §8.
2. **UI measurements (rounds 1–3).** A small test collection was run on Windows in the original program. An AI agent used computer use to follow a fixed script and copy the on-screen numbers exactly as shown. A human changed the system date between sessions. The scripts, raw readings and reports are in `measurements/`. Where these readings did not match the spec, the code was disassembled again to resolve the mismatch ("补查裁决" in the spec).
3. **Debugger tracing (rounds 4–9).** Logging breakpoints that record values without pausing were attached to the running SuperMemo process. Round 4 used x64dbg and was interrupted. Later rounds used a Python/ctypes debugger script. These rounds recorded auto-postpone from trigger to write-back, and the computation of the new interval and A-Factor after a review. They also recorded intermediate values and the raw random numbers, so formulas could be checked digit by digit. The debugger logs and analysis notes are not published here. Their conclusions are part of the specs.

Before this, headless runs under Wine could not open a collection (`schedule/SPEC.md` §9). All runtime evidence comes from real Windows.

## Usage

The code needs Python 3 and the standard library only (`math`, `struct`, `dataclasses`, `pathlib`, `unittest.mock`). It was tested on Python 3.14.

```bash
python3 -I priority/test_vectors.py   # prints "all vectors passed" with the measured count (5)
python3 -I schedule/test_vectors.py   # prints "ALL PASSED: 245 条" with 93 measured / 152 formula-derived
```

Exit code 0 means every vector passed. Any failure exits non-zero. Both suites run on GitHub Actions on every push.

### Main entry points

| Module | Function | Spec |
|---|---|---|
| `priority.py` | `PriorityQueue` (`get_priority`, `set_priority`, `add_new_element`, `change_priority_by`) | §3–§4 |
| `priority.py` | `create_extract`, `spread_priority` | §5 |
| `priority.py` | `adjust_priority_by_interval` (post-review shift) | §4.9 |
| `priority.py` | `batch_apply` | §6 |
| `priority.py` | `build_daily_queue` (`randomized_draw`, `interleave`) | §8 |
| `schedule.py` | `new_element`, `new_topic_af`, `extract_afs` | §3 |
| `schedule.py` | `topic_next_interval`, `adjust_af`, `commit_topic_repetition` | §4 |
| `schedule.py` | `PostponeSettings.auto_runtime()`, `postpone_extra`, `run_postpone`, `auto_postpone` | §5 |

A minimal example, run from the repo root with `PYTHONPATH=priority:schedule python3 example.py`:

```python
import random
from priority import PriorityQueue
from schedule import extract_afs, topic_next_interval, adjust_af

q = PriorityQueue(range(1, 11))       # 10 elements, element 1 at the head
q.add_new_element(99)                 # new element at default priority 5.0
print(q.locate(99), q.get_priority(99))          # -> 1 0.0  (small queue: lands at the head)

print(extract_afs(1.5, 200))          # (child AF, parent AF) -> (1.583173076923077, 1.4755)

rng = random.Random(0).random         # any [0,1) source; SuperMemo uses Delphi Random
new_iv = topic_next_interval(old=3, af=1.8, mode=0, rng=rng)
print(new_iv, adjust_af(1.8, 3, new_iv, hard=False))   # -> 4 1.8644897959183675
```

Randomness is always injected (`rand01` / `rng`), and so is "today". Nothing reads the wall clock.

### Evidence marks in the specs

| Mark | Meaning |
|---|---|
| ✅ | Closed statically: there is an address and an instruction sequence you can check yourself |
| 🧪 | Measured in the original program (UI readings or debugger trace) |
| ❓ | Not determined; the text says where it got stuck |

### Two kinds of test vectors

- **原版实测 (measured on the original)**: these numbers came from SuperMemo itself. Do **not** change them to make an implementation pass.
- **公式推演 (formula-derived)**: these were computed from the disassembled instructions. They can be updated if a ruling changes.

## How far to trust this

In short: **consistent and runnable at the engineering and math level; the evidence chain is not yet closed.** It is fine to use as a strong behavioral hypothesis plus a runnable model. To treat it as a confirmed spec of the original, three things are still missing: raw evidence others can check (debugger logs, screenshots), the exe itself (not distributed here, hashes only), and independent third-party reproduction.

- **"245 passed" does not mean "245 checked against the original".** In the scheduling suite only 93 vectors use numbers produced by SuperMemo itself (debugger rounds 6, 8, 9 and UI rounds 2, 3). The other 152 are formula-derived expectations and only show that the code matches the spec. The priority suite has 5 measured assertions. Both suites print this split at the end.
- **Dates.** UI round 1 ran on the real date, 2026-10-19. Every later date in the reports is simulated by setting the system clock forward so elements fall due.
- **Screenshots and logs are not published.** They stay on the Windows machine used for testing.
- Follow-up work is tracked in issues: [#1 evidence pack](https://github.com/Samuelxiaozhuofeng/supermemo-algorithms/issues/1), [#2 differential test harness](https://github.com/Samuelxiaozhuofeng/supermemo-algorithms/issues/2), [#3 measurement gaps](https://github.com/Samuelxiaozhuofeng/supermemo-algorithms/issues/3).

## What has been verified against the original

| Algorithm | Claim | Evidence |
|---|---|---|
| Priority | Priority = equally spaced queue position; new element goes near the head; extract lands right after its parent; set-to-50 placement; sort slider defaults | Round 1, 11-element collection, matched the reference implementation position by position |
| Priority | Manual priority change: remove, then reinsert at `R(P/100·count')+1` with round-half-to-even | Round 2, 26-element queue, 15/15 changes matched, including .5 ties |
| Priority | Post-review shift by interval (§4.9) | Round 2, 5 days replayed. Single-review days matched exactly. Multi-review days are reproduced under some review order (order not recorded) |
| Scheduling | Parent A-Factor decay after extracting | Chain 1.377 → 1.341 → 1.325 → 1.309 matched digit by digit |
| Scheduling | Extract child A-Factor | 4 extracts within 3 decimals |
| Scheduling | A-Factor adjustment after topic review | 26/26 in round 2 UI readings; 5/5 digit-exact in round 9 debugger trace |
| Scheduling | New interval after topic review (formula, inputs, both random numbers, result) | Round 9 debugger, 15/15 calls digit-exact |
| Scheduling | Overdue days do not affect the new interval | Round 2 UI (late reviews) |
| Scheduling | New topic A-Factor from text length at creation | Round 2: 100 chars → 1.75, 9/9 articles; round 3: 300 chars → 1.550 exactly |
| Auto-postpone | Settings actually used at runtime (differ from the dialog), plus gates | Round 6 debugger dump of the 71-byte settings block |
| Auto-postpone | Days postponed per element (priority, multiplier, clamps, 2 random numbers, dispersion, result) | Round 8 debugger, 19/19 elements back-substituted exactly, dispersion double error 0 |

Exact sources are in each spec's header and in the 🧪 notes under each section.

## Known limitations and gaps

- **New interval only measured with old interval = 1.** The debugger round covered only that branch, where `d` is clamped to 4. Larger intervals rest on static analysis alone.
- **The Delphi `Random` LCG body (`0x40a350`) and seed were not taken apart.** You can match the distribution but not SuperMemo's actual random sequence.
- **Real48 precision loss is not simulated.** SuperMemo stores A-Factors as 6-byte Real48. The reference implementation keeps a full double, so long chains may drift in late digits.
- **Two priority behaviours were never measured**: the small priority nudge after grading an item (§9), and Ctrl+Shift+Up/Down. Both rest on static analysis only.
- **The `mode` byte** in the interval function (`[[0x1163a28]+0x23f1]`) has no known product meaning. The halving branch for modes 5 and 6 is unverified in practice.
- **Auto-postpone settings.** The runtime block was dumped from a collection where nobody had confirmed the Postpone dialog. We don't know whether confirming the dialog switches auto-postpone to the dialog values, or where the runtime block comes from.
- **Daily queue.** We don't know who builds the Outstanding queue, how postponed-to-today elements enter it, or where elements added during the day are inserted.
- **Extract length `n`.** Some text-cleaning steps (tag stripping, entity table, trimming) come from a single source, so `n` may be off by a few characters on HTML-heavy selections.
- **Creating a new topic gives it interval 1 and repetitions 1.** This was observed, but the code path was not traced and is not modelled.
- **Post-review shift on multi-review days.** The review order was not recorded, so these days are only shown to be reproducible, not uniquely confirmed.
- **The test collection was tiny.** It had 11–26 elements, one collection, one build. Large-queue effects such as granularity and the 20-bucket distribution were never exercised at runtime.
- **Unruled single-source content is not implemented**: Reschedule, Ctrl+J, Dismiss, Mercy and others (`schedule/SPEC.md` §7).
- **Out of scope**: the SM-18/20 item memory algorithm.
- The full open list is in `priority/SPEC.md` §13 and `schedule/SPEC.md` §10.

## Contributing

Help is most useful where the evidence is thinnest:

- **Measure on your own collection.** Larger intervals, larger queues, item grading nudges, Ctrl+Shift+Up/Down, and dialog-confirmed postpone settings are all open. The scripts in `measurements/` show the format: a fixed script, numbers copied exactly as displayed, and no computing on the measurer's side.
- **Turn 公式推演 vectors into 原版实测 vectors.** Recapture the values with breakpoints on the original program. `schedule/SPEC.md` §9 lists suggested breakpoints.
- **Close a ❓ item.** Give the address, the instructions, and how you checked them.

For an issue or PR, please include:

1. SuperMemo build and `sm20.exe` SHA-256.
2. Which spec section or ❓ item it concerns.
3. Evidence: raw readings or a trace log, and for static claims, addresses plus the instruction listing.
4. For code changes, `test_vectors.py` passing. Never edit a 原版实测 vector to make code pass.

## Disclaimer

This repository exists for interoperability and research. SuperMemo is a trademark of SuperMemo World. The repository contains no SuperMemo source code or binaries. Everything here is our own description of observed behaviour.

## License

MIT, see [LICENSE](LICENSE).
