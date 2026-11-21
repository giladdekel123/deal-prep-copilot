# Freeze readiness report: fresh evaluation (prepared for owner and ChatGPT review; NOT authorized)

Prepared offline by Claude Code. No model call, no network access, no briefing, no retrieval trace, no drafting input, no
scoring, no held-out access, no push. Authorization is unsigned and inactive.

## 1. What is frozen for review

`FREEZE.sha256` lists **293 files** (SHA-256 with line endings normalised, as the runner's own `file_sha`): the accepted runner and
conversion builder; the 104-passage evidence inventory and sources; the converted run materials (four company folders, crosswalk,
dates); the four approved fictional histories; the six global vendor documents and the knowledge-base manifest; the application
source (`src/`, `app/`); the frozen v2 runner and benchmark scripts; the runner and freeze tests; the protocol, the draw and the
owner sign-off form; and the scoring forms. `FREEZE_SCORING_FORMS.sha256` lists the 13 scoring-form files again on their own, and
`FREEZE_MANIFEST.json` keeps them in a section apart from the runtime inputs (the runner's read guard refuses them during a scenario).
`FREEZE_MANIFEST.json` also records: implementation commit `3d65bb0` and the `src`/`app` git tree ids; PDF renderer file hash and
settings; runner, v2 runner and builder hashes; the eight scenarios; cutoff 2026-11-15T10:00:00Z; models (`gpt-6.1-terra` draft,
`gpt-6-luna` agent), 4000 / 600 output-token limits, low reasoning effort, prices; ceilings USD 0.05 per briefing and USD 0.40
total, one attempt per scenario; group hashes per input type; Python and package environment (informational).

Freeze identifier (SHA-256 of `FREEZE.sha256`): see `RUN_AUTHORIZATION.md` and `python scripts/fresh_evaluation_freeze.py --verify`.

## 2. Files created and the one file modified

`eval/fresh_evaluation/FREEZE.sha256`, `FREEZE_SCORING_FORMS.sha256`, `FREEZE_MANIFEST.json`, `FREEZE_REPORT.md`,
`RUN_AUTHORIZATION.md`; `scripts/fresh_evaluation_freeze.py` (build and verify; reuses the runner's hashing and required-file list;
about 200 lines, no new framework); `tests/test_fresh_evaluation_freeze.py` (5 tests).

**One existing file was modified:** `tests/test_fresh_evaluation_ready.py`, one test (`test_offline_verification_needs_no_network_no_model_and_no_index`). It hard-coded the pre-freeze state (`--check` exit 0, "NOT READY"). The first full run with the freeze package failed that one test (1296 passed, 1 failed). The expectation now accepts both states: before the freeze exit 0; with the freeze matching and the authorization unsigned, exit 1 with "NOT RECORDED". Still asserts all 11 static checks pass and no network use. The runner, production code, prompts, criteria, sources and records are untouched.

## 3. Verification results (offline)

| Check | Result |
|---|---|
| Working tree before this task | clean at `3d65bb0` (branch master) |
| Only the freeze package differs from `3d65bb0` | yes (`--verify` checks this) |
| Scoring requirements | 43 items = 15 Critical + 28 Major (counted from the eight forms) |
| Eight scenarios vs the recorded draw | identical (AAL-A/B, DBS-A/B, TGT-A/B, TOY-A/B), runner check passes |
| 104-passage inventory | unchanged since `8cb3dfc` (no diff); `build_excerpts.py --check` re-cuts all 104 from the raw sources: no mismatch |
| Run materials | 101 passages in 260 segments, 3 withheld (TGT-21/22/24); run-material verification passes |
| Fictional histories | no change since `0f098e8`; run-material copies verified byte-identical to the approved records |
| Vendor knowledge base and application | no change since `3d65bb0`; global vendor documents match the committed ones and name no evaluation company |
| Isolation, A without histories, B only own history, empty news, dates, registries, answer-key scan | all PASS (runner `--check`) |
| `fresh_evaluation_freeze.py --verify` | **293 of 293 OK, PASS** (no missing, unlisted or changed file) |
| Live command | refuses: authorization line absent, tree not clean before the commit; no `runs/fresh_evaluation` folder exists |
| Tests | the complete offline suite, run alone: **1297 passed** (1292 before + 5 new freeze tests); the 62 fresh-evaluation tests (57 runner + 5 freeze) also pass on their own |

## 4. Discrepancies and blockers

- **No blocker for owner sign-off.**
- Observed behaviour, not changed (the runner is accepted): once an *unsigned* `RUN_AUTHORIZATION.md` exists, `fresh_evaluation_run.py
  --check` prints "PROBLEMS in authorization" and exits 1, because a present file without the YES line counts as a problem in
  `check()`. All eleven static checks still PASS and `--live` refuses as intended. If the owner prefers `--check` to exit 0 with an
  unsigned template, that is a one-line change to the runner and would need a re-freeze; I did not make it.
- The freeze package commit cannot name its own hash; the authorization names the implementation commit `3d65bb0` and the freeze
  SHA-256, and the run records the exact `HEAD` in `config.json`.
- Known limitations carried into the authorization: source-date basis for AAL-S1, TGT-S1, DBS-S1; table fragmentation; Target
  Australia clarification; live path untested against the real client; assessors took part in development.

## 5. To authorize execution later (owner action)

1. Review this package; run `python scripts/fresh_evaluation_freeze.py --verify` (expect `N of N OK`, PASS) and the offline tests.
2. Edit `eval/fresh_evaluation/RUN_AUTHORIZATION.md`: change `RUN AUTHORIZED BY OWNER: NO` to `RUN AUTHORIZED BY OWNER: YES`, sign and
   date the block, leave the `FREEZE SHA-256` line as is.
3. Commit that file (the runner requires a clean tree; this is the only change `--verify` permits after the package).
4. Instruct Claude Code to run `python scripts/fresh_evaluation_run.py --live`. Any change to a frozen file after the freeze
   invalidates it and the runner refuses.
