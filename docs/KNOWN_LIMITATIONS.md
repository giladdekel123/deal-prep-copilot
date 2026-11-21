# Deal-Prep Copilot — Known Limitations

Reviewed 21 November 2026. The original list (items 1–24, written 6–9 November 2026) has been re-sorted so that a reader can tell
what still applies. **Item numbers are unchanged**, so older references still work. Items 25–33 were added after the final
evaluation, and item 34 describes this public portfolio version.

**How each item was re-checked (this review):** by reading the current code, the development notes and the evaluation records.
Only the offline test suite and rehearsal were rerun (see "Verification" in `README.md`). **No live AI call was made.** Where an
item says "not re-verified", nothing in this review proves it either way. Files cited from the private development archive
(for example `eval/real_companies_v2/`) are not included in this repository.

The final frozen evaluation (20 November 2026) **did not meet its acceptance criteria**: see `docs/FINAL_EVALUATION_SUMMARY.md`.

## A. Known unresolved problems

| # | Problem | Status |
|---|---|---|
| 15 | Intermittent Chroma 1.1.1 error "Error creating hnsw segment reader: Nothing found on disk". Seen on 6 and 8 November 2026 in `tests/test_history.py`, and on 21 November 2026 as 56 test errors in `tests/test_offline_briefing_readability.py` (one run, in a fresh environment; the same module passed 72/72 when rerun alone). The failing operation is the knowledge-base vector query right after an approved meeting is written to the history collection in the same Chroma folder. | **Unresolved, cause unconfirmed** (possibly timing in Chroma's local storage or Windows file access). A briefing request could fail until the app is restarted; the knowledge-base search has no retry (the history search retries once). No network is involved. |
| 23 | In Live AI drafting mode (news off), if the agent tries its optional news search, its step history records "failed: live news is not enabled" instead of "skipped" (`src/deal_prep/agent.py`). | **Unresolved** (the code still has no "skipped" path). Not shown in the interface; may overstate a failure in run records and in the live agent's next input. Not changed because it alters live-model input. |
| 9 | A drafting retry's reason is not kept in the live run record. | **Unresolved**, not re-verified. The trace records both drafting calls. |
| 16 | If `chroma_db/` is deleted, approved meeting history is not re-indexed automatically. | **Unresolved.** SQLite keeps the records; run the reconcile command in `README.md` (Troubleshooting). |
| 13 | An approved meeting record cannot be re-edited in the interface (the backend supports re-approval). Dates are typed as YYYY-MM-DD. | **Unresolved** (interface limitation). |
| 11 | In the Hebrew PDF, section content stays in English; the "-" marker of English gap lines appears at the left end of the line. | **Unresolved**, cosmetic, stated on the page. Not re-checked after the PDF redesign of 20 November 2026. |
| 25–33 | Final-evaluation findings, including a runner stopping-rule defect. | See section D. |

## B. Still applicable: scope, specification deviations and environment

| # | Limitation | Notes |
|---|---|---|
| 1 | The knowledge base has 19 documents (8 public, 11 synthetic); the specification asks for about 30–50 (FR-03). In this public portfolio version the public documents hold project-written summaries, not quotations (`README.md`, `THIRD_PARTY_NOTICES.md`). | Deviation. All five formats and all provenance rules are covered. |
| 2 | Meeting notes are structured by a rule-based extractor, not by AI (FR-13). | Deviation. It only copies sentences, so it cannot invent anything; it is labelled "no AI model". |
| 3 | Live AI drafting with approved meeting history (FR-14), the prompt-injection test against the real model (AT-11, AC-31) and the measured fixed-workflow versus agent comparison (AT-16) were **not verified live** as of 9 November 2026. | Not re-verified. Later live development and evaluation runs drafted from fictional customer histories, but this review cannot confirm they exercised the same path, so these stay open. Paid calls need owner authorization; the project's provider credits were exhausted on 20 November 2026. |
| 7 | Offline mode cannot brief a company outside the registry; it truthfully reports "no briefing". | News is off offline and such companies have no internal records. Live mode was verified for Skanska on 6 November 2026. |
| 17 | Verified on Windows 11 only. The Hebrew PDF needs Arial (`C:\Windows\Fonts`, or `DEAL_PREP_FONT_DIR`). | |
| 18 | A fresh installation was verified on 8 November 2026 (new Conda environment, empty caches: 427 tests, at that time) and on 21 November 2026 (new virtual environment from `requirements.txt`, `pip check` clean, offline start, 1156 passed plus the 56 errors in item 15). Another machine, macOS and Linux were not tested. Only direct dependencies are pinned. | |
| 19 | The embedding model (all-MiniLM-L6-v2) is English-centric and the corpus is English only. | Hebrew affects only the PDF output language. |
| 20 | News publication dates can be provider estimates. | Labelled as such; publication and retrieval dates are kept separate. |
| 21 | Costs are estimated from a configured price table, not provider invoices. Caps are enforced in this application only. | The provider account's own limits are separate. |
| 22 | A company outside the registry is identified by name only; a domain typed by the user is not verified. | Ambiguous names stop and ask; look-alikes are excluded. |
| 34 | **Public portfolio version:** the public-source statements of company websites and filings (NVQ-PUB-001 to 007) are project-written summaries, not the "short verbatim excerpt" that spec v1.2 §6B and AT-24 describe; only Wikipedia (NVQ-PUB-008) keeps verbatim quotations. | Deviation introduced on 21 November 2026 to avoid redistributing third-party wording (`THIRD_PARTY_NOTICES.md`). The corpus format and the citation checks are unchanged, and the pipeline cannot check a summary against the live page (it never fetched the pages). Where the app would show a summary in quotation marks as the source's words, the text is prefixed "Summary:". The 9 November 2026 acceptance results (AT-24 PASS) were obtained with the earlier, quoting version. |

**Not production-ready by design.**
- Local, single-user demonstration: no authentication or roles, no deployment; local SQLite and Chroma.
- API keys are read from a local, gitignored `.env` file in plain text.
- Offline demonstration briefings are template-assembled, not AI-written; AI output exists only as recorded live runs.
- The MIT license covers only the project's own material (see `LICENSE` and `THIRD_PARTY_NOTICES.md`), and the third-party evaluation sources are not included in this repository.
- Out of scope by specification: document upload, CRM or SharePoint integration, OCR, multiple agents, automatic email, calendar or
  reminders, autonomous actions.

## C. Resolved or substantially addressed during development

| # | Original limitation | What changed | How certain |
|---|---|---|---|
| 24 | Meeting records were cut to 60 words before drafting, so follow-up tasks and their status were lost (found in the owner's walkthrough, 9 November 2026). | Phase 4.5 I1 passes meeting records as structured lines and up to 12 follow-up tasks with status and due date, and states any further tasks instead of dropping them (`eval/benchmark_v1/I1_RESULTS.md`). Other evidence still keeps the 60-word excerpt (`evidence.EXCERPT_WORDS`). | Documented fix; covered by the benchmark and tests that pass; **not re-demonstrated in the interface**. |
| 10 | Offline briefings copied source wording, did not rank items by relevance, and gave general recommendations. | Phase 4.5 I3 (purpose-aware selection), I5 (business analysis, actionable recommendations) and I6 (organization, conciseness, PDF readability) addressed relevance and recommendations (`eval/benchmark_v1/I3_RESULTS.md`, `I5_RESULTS.md`, `I6_RESULTS.md`). Template briefings still reuse cited passages rather than rewording them. | Substantially addressed; wording reuse remains. |
| 8 | Weak public sources could qualify as evidence (a search provider's own company-profile page; a delayed stock-quote page as the only "recent development"). | Phase 4.5 I2 added evidence profiling, and `evidence_profile.py` now detects stock-quote and market-data pages so they are not treated as news. | **Partly**: quote pages are handled; a weak but honestly labelled secondary source can still qualify. |
| 12 | The recorded Arup PDFs predated a wording change. | Moot: those PDFs are not part of this repository, and the PDF layout was redesigned on 20 November 2026 (about 10 pt body text, natural pagination). | Resolved by supersession. |

## D. Historical evaluation findings

These describe what was measured at a date and are not claims about the current code.

| # | Finding |
|---|---|
| 6 | Live latency on 6 November 2026 was 17.6–32.7 seconds per briefing (Arup 22.1 and 25.9 s; Shikun & Binui 32.7 s; Ashtrom Group 17.6 s; Skanska 26.8 s). "Within seconds" is a measured objective, not met in live mode. Offline briefings take under a second after the first index build. In the final evaluation the four completed briefings took roughly 26–58 seconds each including per-scenario setup (from the recorded attempt start times; approximate). |
| 14 | Claim-to-source support was reviewed manually on five briefings (42 items, all supported) by Claude Code and approved with comments by the owner on 9 November 2026. It is not a statistical groundedness score, and citation support is not proof of good reasoning. It reviewed the earlier version of the saved demonstration, which quoted its sources. |

### Final evaluation findings (20 November 2026)

**The final frozen evaluation did not meet its acceptance criteria.** See `docs/FINAL_EVALUATION_SUMMARY.md`.

| # | Finding | Severity |
|---|---|---|
| 25 | Only 4 of 8 planned scenarios produced a briefing. TGT-A, TGT-B, TOY-A and TOY-B failed because the provider's credits were exhausted (HTTP 429). With one attempt per scenario they were not retried; the evaluation cannot be completed under its authorization. Live mode cannot run until the account is topped up. | environment |
| 26 | Three Critical requirements failed among the four completed briefings (AAL-A, AAL-B, DBS-A, DBS-B). | quality |
| 27 | Average assessed usefulness was 3.0 out of 5. | quality |
| 28 | Public-company research coverage was inadequate in AAL-A and DBS-A; the DBS-B PDF also shows an empty company overview. A briefing can only report that the knowledge it was given is thin. | quality |
| 29 | Citation audit: 34 of 34 citation-bearing items in the completed briefings were supported or appropriately qualified. This shows citations are honest, not that the briefings are useful. | information |
| 30 | The evaluation runner's stopping rule has a defect: a provider error that the application had already caught and reported as a normal error status was classified as an ordinary scenario failure, so the run continued after the first credit failure instead of stopping. No extra spend and no retry occurred. Not repaired because the runner is frozen (and not included in this repository). | defect (evaluation tooling) |
| 31 | The usefulness ratings were produced by ChatGPT and adopted by the project owner; they are not an independent second assessment. The assessors took part in development and the evaluation is not blind. Four briefings are a small sample. The written ratings and Critical-failure details are not stored in the repository. | evidence limit |
| 32 | Accepted before the run: some source dates rest on a page's own printed date (AAL-S1, TGT-S1, DBS-S1); long passages were split into 50-word segments and flattened tables lose column headings across segments; Target Australia passages (TGT-21, -22, -24) were withheld from the corpus. | evaluation limit |
| 33 | The live path of the evaluation runner had been tested only with mocks before its first real use. | evaluation limit |
