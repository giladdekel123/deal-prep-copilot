# Live baseline B0-live (Phase 4.5, CP-0) — FICTIONAL TEST DATA

Every company, source and record here is fictional (benchmark registry, Option A: internal labels may read
"(real, customer)"; that wording is inaccurate).

## What this is

- **Layer:** the **live** workflow: production retrieval, the gpt-6.1-terra drafter and the gpt-6-luna research
  agent, unchanged (low reasoning effort, output ceilings 4,000 / 600 tokens, `store=False`, production cap
  $0.10 per briefing). Fixture news (0 Tavily calls); seeded meeting history; clock 2026-11-09 09:00 UTC.
- **Scope:** 6 **development** scenarios, one per company, run once each: DEV-P2 (negotiation), DEV-T1 (follow-up),
  DEV-C1 (negotiation), DEV-L1 (follow-up), DEV-E1 (introduction), DEV-M2 (product demo). No held-out data was
  read, run or scored.
- **Run:** `20261109T192917Z`, by `scripts/benchmark_live.py` (owner authorization: at most $10 OpenAI in total).
  Evidence (prompts, outputs, calls, costs, manual review) is kept locally in the gitignored folder
  `runs/benchmark_v1/cp0/`.
- **Cost:** 22 calls (15 agent, 7 drafting incl. 1 controlled retry); 78,444 input tokens (3,831 cached),
  7,573 output tokens (1,519 reasoning); **$0.0601** at the prices verified on 2026-11-09 (Terra $1.00 / $5.00,
  Luna $0.10 / $0.50 per 1M tokens).
- **Comparisons:** later live runs are compared only with this live baseline, never with B0-offline. With 6
  scenarios and one run each, there is no measure of run-to-run variation yet.

## Automated metrics (the I0 scorer; passed / applicable)

| Metric | Coverage | Live, 6 dev scenarios |
|---|---|---|
| R1 must-reach evidence in the drafting input | full | 22 / 31 |
| R2 meetings and tasks with current status in the drafting input | approximation | 8 / 16 |
| R3 stale, look-alike and passing-mention news kept out | full | 15 / 15 |
| O1 number consistency (NOT factual accuracy) | partial | 30 / 33 |
| O2a must-cite evidence cited | full | 19 / 23 |
| O2b cited evidence that is not a distractor | full | 48 / 51 |
| O3a compatible pairs not called contradictions | approximation | 5 / 5 (5 vacuous) |
| O3b genuine contradictions disclosed | approximation | 0 / 4 |
| O3c undated statements omitted or marked | approximation | 3 / 6 (1 vacuous) |
| O4 checkable disclosure statements true | partial | 4 / 4 |
| O5a official verbatim passage preferred | full | 5 / 6 |
| O5b quote and data pages kept out of Recent developments | full | 6 / 6 |
| O6a required open items present | approximation | 0 / 12 |
| O6b existing terms not under Opportunities | full | 4 / 4 |
| O7a at least 2 of 3 recommendations cite customer evidence | approximation | 4 / 6 |
| O7b no product or competitor advice beyond the evidence | approximation | 13 / 14 |
| O8 safety | partial | 20 / 20 |

## Manual judgments (Claude Code's preliminary review; not the owner's M2 audit)

All 54 briefing items were read against the full text of every passage they cite.

- **Factual grounding:** 30 / 30 factual items supported, 0 unsupported, 1 minor imprecision.
- **Contradictions:** 3 / 3 count contradictions stated as unresolved, but inside an overview item, not as a
  disclosure (so O3b scores 0). The decision-before-state contradiction was missed (0 / 1). Undated statements
  were not marked.
- **Open items (12, date formats normalised by hand):** 4 present, 3 partial, 5 absent: 3 because the meeting record
  given to the drafter is cut off after its first task, 2 because the customer's request passage was not
  retrieved. No completed task was presented as open.
- **Recommendations:** grounded and cautious; sometimes generic; no position on requested terms that never reached
  the drafter.
- **Disclosures:** honest (no relationship records for new leads, correct news age, a truncated record flagged).

## Attribution of failures

| Cause | Evidence |
|---|---|
| Evidence preparation | meeting excerpts cut off after the first task (R2 8 / 16; 3 absent open items) |
| Retrieval | customer correspondence not retrieved (9 R1 failures; 2 absent open items) |
| Model reasoning | decision/state chronology not checked; undated statements not marked |
| Disclosure logic | conflicts the model notices are not raised as disclosures |
| Scorer (benchmark) | O6a accepts one date format only; O3b sees disclosures only; O1 does not credit news dates from metadata; O2b counts an aggregator cited to state a disagreement as a distractor |

## Limitations

- 6 scenarios, one run each: no variation measure; intervals are wide.
- Development scenarios only: the authors of the benchmark know them; held-out live runs need their own policy.
- Manual judgments are by Claude Code, not the owner; they are not the M2 audit.
- Fixture news stands in for Tavily; the app's live mode without Tavily switches news off.
- Not measured: relevance and usefulness to a real meeting, PDF output.
