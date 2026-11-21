# I1 results and scorer 1.1 (Phase 4.5) — FICTIONAL TEST DATA

Development split only. No held-out data was read, run or scored; no paid call was made in I1.
The original measurements stay as recorded: `BASELINE_B0.md` (B0-offline) and `BASELINE_CP0.md` (B0-live), both
scorer 1.0.

## 1. Scorer 1.1 (benchmark only; `scripts/benchmark_score.py`, `SCORER_CHANGES`)

| Change | Why | Not weakened because |
|---|---|---|
| O6a: a required date also matches in the other standard order ("14 November 2026" = "November 14, 2026") | the live model writes US-order dates; 1.0 missed correct open items | same date, same evidence, same item rule; a different date never matches (tested) |
| O1: a cited news item's publication date, written as a whole date, is supported by its provenance label | the date the drafter was given is metadata, not passage text | only the whole date is credited, never its parts (a bare "11" still fails; tested) |
| O3b unchanged; new **O3b_text**: genuine contradictions **not** formally disclosed that are stated in one item citing both sides with disagreement wording | the live model states conflicts inside items | reported separately, never merged into O3b; O3b still requires a formal disclosure |
| O2b: one side of an expected contradiction is not a distractor when **every** item citing it also cites the other side | citing the aggregator to document the disagreement is correct | cited anywhere on its own, it is still a distractor (tested) |

Scorer 1.0 stays selectable (`score_scenario(..., version="1.0")`) and reproduces both original baselines exactly.
Saved records are re-scored with `scripts/benchmark_rescore.py`, which never modifies them and refuses held-out data.

## 2. Same records, both scorer versions (scoring corrections only, no application change)

| Metric | B0-offline 1.0 → 1.1 (fixture / off) | B0-live 1.0 → 1.1 |
|---|---|---|
| O1 | 100/100 → 100/100 · 82/82 → 82/82 | 30/33 → 32/33 |
| O2b | 78/100 → 78/100 · 70/82 → 70/82 | 48/51 → 51/51 |
| O3b (formal) | 0/8 → 0/8 | 0/4 → 0/4 |
| O3b_text (new) | — → 0/8 | — → 3/4 |
| O6a | 9/18 → 9/18 | 0/12 → 5/12 |

All other metrics are identical between versions. The offline template is unaffected by the corrections.

## 3. I1: structured meeting history (application change, CP-1)

**Cause of the loss:** every evidence item given to the briefing writer, including an approved meeting record, was
cut to its first 60 words (`evidence._short`). A meeting record lists header, participants, concerns, decisions and
commitments first, so the follow-up tasks, their current statuses and due dates were cut off after the first task.
The text also came from the history index copy rather than from SQLite.

**Change (general, company-independent):**
- `src/deal_prep/evidence.py`: approved meeting records (`doc_type` meeting_record, approval_status approved) keep
  every structured line, each capped at 40 words; up to 12 follow-up tasks with status and due date; any further tasks
  are stated ("[n further follow-up tasks not shown]"), never dropped silently. Other evidence keeps the 60-word excerpt.
- `src/deal_prep/history_index.py`: search results are rebuilt from SQLite at query time, so the current task status
  wins over a stale index copy. Approval and company filters are unchanged; drafts never reach the writer.
- `src/deal_prep/demo.py` (offline template only): a meeting item that would exceed the 600-character item limit
  keeps its tasks first and says "Other details of this record are omitted here for length."
- No change to models, prompts, source selection or recommendation logic. Live drafting prompts grow by about
  100–180 characters per customer scenario (free dry run).

**Development benchmark, offline template, scorer 1.1** (run `20261109T201346Z_dev`, deterministic, protected data
unchanged, 0 connections; B0 re-scored with 1.1 for a like-for-like comparison):

| Metric | B0 (fixture / off) | I1 (fixture / off) |
|---|---|---|
| R2 meetings and tasks with current status reach the writer | 16/32 · 16/32 | **32/32 · 32/32** |
| O6a required open items present | 9/18 · 9/18 | **15/18 · 15/18** |
| every other metric | — | identical to B0 |

**I1 completion (closing two deviations from the approved design, found in the post-I1 live comparison):**
- **Eligibility from SQLite:** `history_index.company_history` returns every APPROVED meeting record of the selected
  company straight from SQLite, newest first; drafts and other companies are excluded by the query. The semantic
  top-3 search no longer decides inclusion (the Chroma history index is still kept in sync but not used for
  briefings). Limit: 5 records; meetings with an unresolved task (Open or In Progress) are kept first, so an old
  unresolved commitment is not lost; anything omitted is stated in the newest record ("n older approved meeting
  records are not shown (k of them with open tasks)").
- **Structured fields:** each record also reaches the drafter and the agent as `meeting_record`: meeting ID, date,
  approval status and date, summary, participants, concerns, decisions, commitments and follow-up tasks (description,
  current status, due date), with list, task and word caps and an `omissions` list. The text excerpt is kept for the
  offline template and citation display.
- **Verified without paid calls:** a fake OpenAI client captured the real live drafter's request for DEV-P2, T1, C1
  and L1: each contains the structured record with every task's current status and due date and no draft text;
  prompts grow by about 800 characters.
- **No regression:** the offline development benchmark gives identical counts to the I1 commit (R2 32/32, O6a 15/18).

**Remaining (not addressed by I1):**
- R1: customer correspondence (the request and Nivarque's reply) is still not retrieved; the 3 remaining O6a
  failures are all the customer's requested term (DEV-C1, DEV-P2, DEV-T2).
- O3b / O3b_text 0/8 offline; chronology (decision versus state) not reasoned about; undated statements not marked.
- O7a 0/12 offline; live behaviour after I1 is not measured (no paid run in I1).
