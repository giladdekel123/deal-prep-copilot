# Run authorization: fresh evaluation (eight scenarios)

**STATUS: UNSIGNED AND INACTIVE.** Prepared by Claude Code for the project owner. It authorizes nothing as it stands: the line
that activates it below reads `NO`, and the owner's signature block is empty. The runner (`scripts/fresh_evaluation_run.py --live`)
refuses to start unless the activation line below reads YES (exact wording in the runner) and the freeze identifier below matches the
current `FREEZE.sha256`.

## 1. What would be authorized

| Item | Value |
|---|---|
| Implementation commit (accepted by the owner and ChatGPT) | `3d65bb0` |
| Freeze package | the commit that adds `FREEZE.sha256`, `FREEZE_MANIFEST.json`, `FREEZE_SCORING_FORMS.sha256`, `FREEZE_REPORT.md`, this file, `scripts/fresh_evaluation_freeze.py` and its test, and one updated expectation in `tests/test_fresh_evaluation_ready.py` (it cannot name its own hash; `config.json` of the run records the exact `HEAD`). `python scripts/fresh_evaluation_freeze.py --verify` must print `N of N OK` and `PASS`. |
| Freeze manifest identifier | the SHA-256 of `eval/fresh_evaluation/FREEZE.sha256`, in the line below |
| Information cutoff | 2026-11-15 10:00 UTC (nothing published later is used; news fixtures are empty) |
| Models and limits | draft model `gpt-6.1-terra`, 4000 output tokens; agent model `gpt-6-luna`, 600 output tokens; low reasoning effort; no SDK retries (see `FREEZE_MANIFEST.json`) |
| Spending ceilings | **USD 0.05 per briefing** (production `SpendGuard` refuses a call that would exceed it) and **USD 0.40 in total** (a scenario starts only if the ledger plus 0.05 stays within it) |
| Scenarios (eight, in the recorded draw order) | AAL-A, AAL-B, DBS-A, DBS-B, TGT-A, TGT-B, TOY-A, TOY-B |

Scenario assignments (from `selection/DRAW_RESULT.json`): AAL-A Anglo American introduction (public only); AAL-B Anglo American
negotiation (with fictional history); DBS-A DBS general (public only); DBS-B DBS product_demo (with history); TGT-A Target
Corporation introduction (public only); TGT-B Target Corporation follow_up (with history); TOY-A Toyota introduction (public only);
TOY-B Toyota introduction (with history).

## 2. One attempt and stopping conditions

- **One attempt per scenario.** The attempt is recorded (flushed) before the scenario starts; there is no retry, resume or second
  live run. A second attempt or a second live run is refused by the runner.
- **Stop the whole run** on: a refused model call; an isolation or integrity failure between scenarios (freeze, authorization,
  clean tree, commit, protected data); a blocked connection; the ceiling that would be exceeded; any unexpected exception.
- **Record and continue** only when the pipeline itself reports an ordinary failure for a scenario (that scenario is recorded as
  failed and is not retried).
- No other paid service (the news key is removed); the answer key and scoring forms are unreadable while a scenario executes.
- Nothing is graded by Claude Code; the owner and ChatGPT assess later against the frozen forms.

## 3. Known limitations accepted with this authorization

- **Source dates.** Publication dates are ISO only where the source prints its own; unknown for DBS-S2 and TOY-S4 (briefings, event
  date 2026-11-05 kept apart), DBS-S4, and the withheld TGT-S4, TGT-S5, TGT-S6. DBS-S5 and TOY-S5 carry the cover date 2026-11-05
  (TOY-S5's file was created 12 November 2026). All sources were retrieved on 19 November 2026, after the cutoff, and are admitted on
  the documented basis recorded in `run_materials/SOURCE_DATES.json`. **AAL-S1, TGT-S1 and DBS-S1** rest on the page's own printed
  date alone (no independent server or archive date); the protocol accepts that, and a page could in principle have been edited
  after the cutoff without a trace.
- **Fragmentation.** Passages over 50 words are split verbatim into 260 segments; flattened tables lose column headings across
  segments (TOY-13, TOY-14, AAL-05, DBS-18, TGT-12; see `run_materials/FRAGMENTATION.md`). Not tested by retrieval before the freeze.
- **Target Australia.** TGT-21, TGT-22 and TGT-24 are excluded from the run corpus; TGT-A C1 and TGT-B M3 were clarified before the
  freeze (`scoring_forms/REQUIREMENTS_SUMMARY.md` section 6).
- The live path has been tested only with a fake scenario runner and mocks; it has never driven the real model client.
- The assessors took part in development (protocol sections 4a and 8a); the evaluation is internal and not blind.

## 4. Owner authorization (to be completed by the project owner only)

To authorize: replace `NO` with `YES` on the activation line, fill in the signature block, and commit this file (the runner also
requires a clean working tree). Do not alter the freeze line.

FREEZE SHA-256: 4899d1d726e665a5e6904a9aaff9e68a49610b3c66b11353433b697710310d93

RUN AUTHORIZED BY OWNER: YES

Owner signature: none handwritten. Typed record: authorization given by the project owner in writing in the Claude Code conversation (message "Final Evaluation Execution Authorization", freeze package commit 04d86d0, implementation baseline 3d65bb0). Claude Code, not the owner, edited this file and committed it on the owner's explicit instruction.  Date: 2026-11-20

Owner statement (as relayed in that message): the owner has explicitly accepted the freeze and authorized execution of the eight final evaluation scenarios, limited to exactly one execution attempt per scenario, at most USD 0.05 per briefing and USD 0.40 in total, in the frozen order (AAL-A, AAL-B, DBS-A, DBS-B, TGT-A, TGT-B, TOY-A, TOY-B), with the frozen evidence corpus, application, runner, models and configuration. No additional runs, retries, re-seeding, prompt changes, evidence changes or tuning are authorized.
