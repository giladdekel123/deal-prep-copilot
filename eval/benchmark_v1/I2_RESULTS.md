# I2 results: evidence quality and source authority (Phase 4.5) — FICTIONAL TEST DATA

Development split only; no held-out data read, run or scored; no paid call. Scorer 1.1 throughout (unchanged in
I2, so every difference below is an application change, not a scoring change).

## Root causes

1. **Quote and data pages were treated as news.** `web_research` kept any result that named the company. A delayed
   stock-quote page dated today counted as "last 48 hours" news, appeared under Recent developments and, worse,
   stopped the 30-day fallback, so genuine 30-day news never reached the drafter (DEV-L1/L2).
2. **No evidence profile.** The drafters saw no distinction between an official verbatim statement, the official
   claims summary, an aggregator copy and a header passage. The offline template took the first five company-profile
   passages in retrieval order, so it often cited the claims summary or an aggregator instead of official wording.
3. **Disagreements depended on retrieval luck.** Retrieval often returned only the header passage of a secondary
   source, never its figure statement, so a contested figure (official 4 versus aggregator 5) could not be seen. In
   CP-0 the live model saw it only when its own agent search happened to fetch it; otherwise a single figure was
   presented as settled.

## Changes (company-independent)

- **New `src/deal_prep/evidence_profile.py`** (pure rules over the evidence the drafters already receive):
  - `is_data_page`: a price-change figure, two market-data terms, or a quote URL plus one such term. Ordinary news
    mentioning a share price once is still news (tested).
  - `profile`: `source_class` (official_company_source, secondary_profile, news, internal_record, meeting_record,
    unknown), `statement_form` (verbatim_excerpt, claims_summary, document_header, passage), `date_status`
    (stated, provider estimate, unknown; nothing is inferred), and figure relations across documents: the same
    statement with different figures is **contested on both sides**; with the same figures, a non-official source
    **restates** the official one. Passages of one document are never compared.
- **`web_research`:** quote and data pages are excluded from news (counted in `excluded["data_page"]`), so they
  neither appear as news nor block the 30-day search.
- **`orchestrator.add_comparison_sources`:** when a retrieved public passage (or claims summary) states a figure,
  every public document already retrieved for the company contributes its own verbatim statement of the same
  figure, fetched by document ID (no new search). This makes disagreements and copies visible and makes the official
  verbatim passage available instead of only its summary.
- **Offline template (`demo.overview_selection`, `contested_text`):** official and verbatim first; a claims summary is
  skipped when the same document's verbatim excerpt is present; a secondary copy of an official figure is skipped;
  contested figures become one item quoting and attributing both sides: "Sources differ: …. The figure is
  unresolved."
- Not changed: models, prompts, recommendation logic, I1 meeting history, held-out data, saved demonstrations.

## Development benchmark, offline template (I1 commit → I2; fixture news / news off)

| Metric | I1 | I2 |
|---|---|---|
| O5a official verbatim preferred | 6/10 · 6/10 | **12/12 · 12/12** |
| O5b quote pages out of Recent developments | 2/12 · n/m | **12/12** · n/m |
| O2b cited evidence not a distractor | 78/100 · 70/82 | **90/98 · 80/88** |
| O2a must-cite evidence cited | 32/46 · 24/36 | 38/46 · 28/36 |
| O3b_text contradictions stated in text | 0/8 · 0/8 | **6/8 · 6/8** |
| R1 must-reach evidence | 40/62 · 32/52 | 44/62 · 34/52 |
| R2, R3, O4, O6a, O8 | unchanged | unchanged (R2 32/32, R3 30/30, O6a 15/18, O8 50/50) |
| O1 number consistency | 100/100 · 82/82 | 92/92 · 82/82 (fewer, all supported facts) |

Deterministic across two repeats, protected local data unchanged, 0 outbound connections.

## Verification and one benchmark-rule correction

- **Full suite:** 599 of 600 passed. The one failure was `test_one_scenario_runs_isolated_offline_and_deterministically_in_both_news_modes`:
  the walkthrough app left running on port 8504 appended connection-reset errors to its own
  `streamlit_8504_r2_err.log` during the test, which changed the protected-data fingerprint. No protected data changed.
  With the app stopped, the test passes.
- **Fingerprint rule (owner-approved):** `benchmark_run.fingerprint` now skips only `*.log` files directly in
  `runs/demo_walkthrough_20261108/`. A new test proves that a change to that log is ignored, while changes to a log in a
  subfolder, the walkthrough history database, the index, the saved demonstration, the spend ledger and the history
  database are still detected.
- **After the correction**, run one after another with memory monitored (2.4 to 3.3 GB free): benchmark and I2 tests
  77/77, development benchmark identical to the earlier I2 run, rehearsal 35/35, consistency check 36/36, held-out freeze
  valid (1 of 3 executions used), live spend unchanged at $0.1174.

## Remaining limitations

- **O3b (formal disclosure) 0/8:** contested figures are stated in the briefing text but not raised as formal
  disclosures; the 2 remaining O3b_text failures are decision-versus-state chronology (I4).
- **O3c undated history** is still not marked (I4). **O7a** offline 0/12 (I5). **R1:** customer correspondence
  retrieval remains incomplete (I3).
- `source_class` uses the corpus `verification` field: "primary" is read as the company's own source. A primary
  third-party document (for example a regulator filing) would also be classed as official.
- Event dates are not yet separated from publication dates: news carries only the provider's publication estimate
  and its own wording; extracting event dates from text is part of I4.
- The live model has not been measured with I2 (no paid run).

## Live-model effect and CP-2

**Already in effect for the live drafter (selection and content, no new field types):**
1. Quote and data pages are no longer sent as news.
2. Other public documents' statements of the same figure (comparison sources) are added to the company-profile
   evidence.

**Proposed for CP-2, NOT applied:** add the profile to each evidence entry the live drafter and agent receive, as
`"profile": {"source_class", "statement_form", "date_status", "contested_with", "restates"}` (in
`briefing.build_messages` and `agent.agent_context`, via `evidence_profile.profile`). Expected cost: about
60–100 extra input characters per evidence entry (roughly 2,000–3,500 characters, under $0.002 per briefing). No
prompt text change is needed for the fields to be visible; telling the model how to use them would be a prompt
change (CP-3 / I6). A paid live comparison (about $0.06 for the six scenarios) is recommended after CP-2, to measure
O5a, O2b and contested-figure handling live.
