# Live comparison after I1 (Phase 4.5) — FICTIONAL TEST DATA

Fictional benchmark data only (Option A registry: internal labels may read "(real, customer)"; that wording is
inaccurate). Development split only; no held-out data was read, run or scored.

## Conditions

| | CP-0 (baseline, unchanged) | Post-I1 |
|---|---|---|
| Run | `20261109T192917Z` | `20261109T204743Z_post_i1` |
| Code | `8823cc3` | `2819ecd` (I1) + run-cap option in the benchmark harness only |
| Scenarios | DEV-P2, T1, C1, L1, E1, M2, once each | same |
| Models and parameters | gpt-6.1-terra drafter, gpt-6-luna agent, low effort, 4,000 / 600 output tokens, `store=False` | same |
| News, clock, history seed | fixture news, 2026-11-09 09:00 UTC, seeded approved meetings | same |
| Calls / tokens | 22 calls; 78,444 in, 7,573 out | 21 calls; 75,345 in, 6,861 out |
| Cost | $0.0601 | **$0.0573** (owner cap for this run: $1.00) |

Both runs scored with scorer 1.1; the CP-0 records were re-scored, not rerun. One run per condition: there is no
measure of run-to-run variation, so single-scenario changes may be noise.

## Automated metrics (scorer 1.1, passed / applicable)

| Metric | CP-0 | Post-I1 | Reading |
|---|---|---|---|
| R1 must-reach evidence | 22/31 | 24/31 | agent search variation (customer request retrieved in P2 and L1 by the agent's own queries) |
| **R2 meetings and tasks with current status** | 8/16 | **16/16** | **I1 (deterministic input change)** |
| O1 number consistency (partial) | 32/33 | 35/35 | |
| O2a must-cite cited | 19/23 | 21/23 | |
| O2b non-distractor citations | 51/51 | 48/49 | C1 cited a quote page |
| O3b formal contradiction disclosure | 0/4 | 0/4 | unchanged: never disclosed formally |
| O3b_text contradiction stated in text | 3/4 | 2/4 | P2 lost its count conflict (variation; see below) |
| O3c undated marked | 3/6 | 3/6 | |
| O5a official wording preferred | 5/6 | 6/6 | |
| O5b quote pages out of Recent developments | 6/6 | 5/6 | C1 regression |
| **O6a required open items** | 5/12 | **7/12** | I1 plus scorer misses (dates without year) |
| O7a customer-grounded recommendations | 4/6 | 6/6 | partly variation (E1 has no history) |
| O7b no unsupported product/competitor advice | 13/14 | 14/17 | more conditional competitor mentions |
| O8 safety (partial) | 20/20 | 22/22 | |

## Manual comparison (Claude Code; not the owner's M2 audit)

**Open items (12; dates normalised by hand):** CP-0 4 present, 3 partial, 5 absent → post-I1 **9 present, 2 partial,
1 absent**. New after I1, each drawn from a task line that CP-0 never received: P2 in-progress sizing questionnaire
with due date; C1 import-template task and the 36-month term of the revised quote; L1 open retention-periods task;
T1 revised quote shown as open and the migration checklist correctly as completed. Still absent: C1 customer's
requested term (its correspondence passage was not retrieved in either run). Partial: T1 and L1 latest contact
(request shown, date missing). Scorer 1.1 counts 7 because "due 16 November" without a year is not matched.

**Recommendations:** more specific to the meeting record (confirm the total user count before the revised quote;
review the completed checklist; confirm retention periods); P2 now uses the list price, the proposal price and the
discount-approval thresholds as negotiation reference points (all three verified against their passages).

**Factual grounding:** every factual item checked against its cited passage was supported (O1 35/35; new figures
$52 list price, 60 additional users, 3 TB checked by hand). One quality regression: P2 states "four factories" as
established although a conflicting aggregator figure (five) reached the drafter — a contested figure presented as
settled.

**Disclosures:** unchanged and honest (new leads: no prior relationship records). Conflicts are still never formally
disclosed.

## Attribution

| Change | Classification | Evidence |
|---|---|---|
| R2 8 → 16/16; new open tasks, statuses and due dates in briefings | **Application improvement (I1)** | the task lines were absent from CP-0's drafting input and present now; same history seed |
| O6a 0 → 5/12 for CP-0 | **Scorer correction (1.1)** | same records, re-scored |
| R1 +2, O7a +2, O5a +1 | **Likely model/agent variability** | agent queries differ between runs; E1 has no meeting history |
| P2 count conflict not stated; C1 quote page in Recent developments; more conditional competitor mentions | **Regressions, most likely variability** | I1 changed only meeting-record text; one run each, so not attributable |

## Remaining weaknesses

1. Customer correspondence retrieval (requested terms, latest-contact dates).
2. Conflicts: never formally disclosed; narrative statement unstable between runs; a contested figure was presented
   as established; decision-versus-state chronology never reasoned about; undated history not marked.
3. Quote and data pages still reach the drafter and can appear as news.
4. Generic competitor battlecard advice appears conditionally in scenarios with no competitor evidence.
5. I1 deviation from the plan: meeting records are still **included** by semantic top-3 search (not by SQLite status
   and date) and passed as complete text lines rather than structured fields. No effect with one meeting per company;
   it can drop records for companies with more than three meetings.
