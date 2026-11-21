# Benchmark baseline B0-offline (Phase 4.5, I0-c) — FICTIONAL TEST DATA

**FICTIONAL TEST DATA — fictional benchmark companies, sources and records. Internal 'real' classification and production labels such as '(real, customer)' are an artefact of the isolated benchmark registry (Option A) and are not accurate: no benchmark entity is real.**

## What this is

- **Layer:** retrieval and the OFFLINE TEMPLATE drafter of the current code. It is **not** a measurement of the live AI model; live behaviour is measured only at CP-0 (separately authorized) and judged only against that live baseline.
- **Code:** production code (`src/`, `app/`) as at commit `df9b5dc`, unchanged. The runner differed only by the benchmark-only aggregate-reporting change committed with this report.
- **Runs:** development `20261109T180023Z_dev` and held-out `20261109T180244Z_heldout`; both news modes, 2 repeats each; clock fixed at 2026-11-09 09:00 UTC.
- **Determinism:** identical across repeats (dev: yes; held-out: yes). **Isolation:** protected local data unchanged (dev: yes; held-out: yes); outbound connections: dev 0, held-out 0.
- **Held-out executions: 1 of 3 used** (this baseline). Every execution is counted, including failed ones.
- **Held-out results are aggregate counts only** (owner decision). Failure details are kept for the owner in the gitignored folder `runs/benchmark_v1/heldout_private/` and are not reproduced here.

## How to read the counts

- Each cell is passed / applicable. With 12 scenarios per split, a difference of one or two is not meaningful.
- **Coverage:** full = the rule decides the property exactly; approximation = a proxy that can miss cases; partial = checks one part only, so a full count is **not** a 100% result for the property.
- **Vacuous** passes succeeded only because the thing tested was absent; they are not capability.
- **O1 is a number-consistency check only, not factual accuracy.** Factual support is measured only by the manual claim-support audit (M2), not part of this baseline.
- "not measured": 0 applicable units in that mode (news expectations are dropped, not passed, when news is off).

## Retrieval layer (what reaches the drafter)

| Metric | Coverage | Dev, fixture news | Dev, news off | Held-out, fixture news | Held-out, news off |
|---|---|---|---|---|---|
| R1 must-reach evidence present in the drafting input | full | 40 / 62 | 32 / 52 | 38 / 58 | 34 / 52 |
| R2 approved meetings and tasks (with current status) present in the drafting input; drafts absent | approximation | 16 / 32 | 16 / 32 | 22 / 32 | 22 / 32 |
| R3 out-of-window, look-alike and passing-mention news kept out of the drafting input | full | 30 / 30 | not measured | 34 / 34 | not measured |

## Offline-template output layer (the briefing)

| Metric | Coverage | Dev, fixture news | Dev, news off | Held-out, fixture news | Held-out, news off |
|---|---|---|---|---|---|
| O1 number consistency only: every number in a fact occurs in its cited passages; no citation-validation failure (NOT a factual-accuracy score) | partial | 100 / 100 | 82 / 82 | 98 / 98 | 84 / 84 |
| O2a must-cite evidence cited in the briefing | full | 32 / 46 | 24 / 36 | 26 / 42 | 22 / 36 |
| O2b distinct cited evidence that is not a listed distractor | full | 78 / 100 | 70 / 82 | 72 / 100 | 68 / 86 |
| O3a compatible statement pairs not disclosed as contradictions | approximation | 10 / 10 (10 vacuous) | 10 / 10 (10 vacuous) | 8 / 8 (8 vacuous) | 8 / 8 (8 vacuous) |
| O3b genuine contradictions disclosed as contradictions | approximation | 0 / 8 | 0 / 8 | 0 / 16 | 0 / 16 |
| O3c undated historical statements omitted or marked as undated | approximation | 2 / 12 (2 vacuous) | 2 / 12 (2 vacuous) | 4 / 12 (4 vacuous) | 4 / 12 (4 vacuous) |
| O4 checkable disclosure statements that are true | partial | 8 / 8 | 32 / 32 | 8 / 8 | 32 / 32 |
| O5a official, verbatim passage cited instead of a weaker copy or paraphrase | full | 6 / 10 | 6 / 10 | 2 / 6 | 2 / 6 |
| O5b data or quote pages kept out of Recent developments | full | 2 / 12 | not measured | 2 / 12 | not measured |
| O6a required open items present (follow-up and negotiation) | approximation | 9 / 18 | 9 / 18 | 10 / 15 | 10 / 15 |
| O6b existing terms not presented under Opportunities | full | 2 / 8 (2 vacuous) | 2 / 8 (2 vacuous) | 2 / 8 (2 vacuous) | 2 / 8 (2 vacuous) |
| O7a scenarios where at least 2 of 3 recommendations cite customer-specific evidence | approximation | 0 / 12 | 0 / 12 | 0 / 12 | 0 / 12 |
| O7b recommendations without product or competitor advice outside the scenario's evidence | approximation | 24 / 36 | 36 / 48 | 26 / 38 | 36 / 48 |
| O8 safety: synthetic relationship items labelled synthetic; no draft content; no error status | partial | 50 / 50 | 50 / 50 | 50 / 50 | 50 / 50 |

## Development failures by metric (fixture news / news off)

The full list, with scenario and evidence IDs, is in the local run summary `runs/benchmark_v1/20261109T180023Z_dev/summary.md`.

- **R1** (22 / 20): mostly customer-correspondence passages (the customer's request and Nivarque's reply) do not reach the drafter; also some main-news and official-profile passages.
- **R2** (16 / 16): every task check fails: the task's current status is not in the drafting input (meeting text truncated); meetings themselves pass.
- **O2a** (14 / 12): must-cite evidence (customer correspondence, official profile passages) not cited.
- **O2b** (22 / 12): distractors cited: the generic price-list row, aggregator copies and news items that should not be cited.
- **O3b** (8 / 8): no genuine contradiction is ever disclosed.
- **O3c** (10 / 10): undated historical statements shown without a date note.
- **O5a** (4 / 4): a weaker copy or claims summary cited instead of the official verbatim passage.
- **O5b** (10 / 0): data or quote pages shown under Recent developments.
- **O6a** (9 / 9): open tasks and the customer's requested term missing.
- **O6b** (6 / 6): existing proposal terms presented under Opportunities.
- **O7a** (12 / 12): no scenario has recommendations that cite customer-specific evidence.
- **O7b** (12 / 12): the generic competitor battlecard recommended where no competitor is in the scenario's evidence.

## Not measured

- overall factual accuracy (M2 is a separate manual audit);
- relevance, usefulness and quality of reasoning;
- live AI behaviour.
