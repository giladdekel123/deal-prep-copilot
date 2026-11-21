# Final evaluation summary (20 November 2026)

**Result: the frozen acceptance criteria were not met. The final evaluation did not pass.**

> Nivarque Document Systems is **fictional**; every customer relationship, proposal and meeting described here is **synthetic**. The real
> companies named have no affiliation with this project and have not reviewed it (see "No affiliation" in `README.md`).

This page records what the final frozen evaluation did and found, and how far the evidence goes. It does not change the
frozen package, the scoring forms or any run output. The package and run output live in the private development archive; this repository holds copies of the key documents in `docs/evaluation_evidence/`.

## 1. What was evaluated

- Eight scenarios, four companies, each with a public-only variant (A) and a variant with a **fictional** Nivarque history (B):
  AAL-A and AAL-B (Anglo American), DBS-A and DBS-B (DBS Group), TGT-A and TGT-B (Target Corporation), TOY-A and TOY-B (Toyota).
- A frozen package: 293 files listed with SHA-256 in `FREEZE.sha256` (archive) (freeze identifier
  `4899d1d7…0d93`, commit `04d86d0`, implementation baseline `3d65bb0`), 43 scoring requirements (15 Critical, 28 Major)
  (summary: `docs/evaluation_evidence/REQUIREMENTS_SUMMARY.md`), an information cutoff of 2026-11-15 10:00 UTC, and empty news fixtures.
- Owner authorization of exactly one attempt per scenario, at most USD 0.05 per briefing and USD 0.40 in total
  (`docs/evaluation_evidence/RUN_AUTHORIZATION.md`, commit `356b93e` in the archive). Models: gpt-6.1-terra (drafting) and gpt-6-luna (agent).
- The assessors took part in development; the evaluation is internal and not blind
  (`RUN_AUTHORIZATION.md` section 3).

## 2. Results

| Measure | Result |
|---|---|
| Scenarios planned | 8 |
| Scenarios that produced a briefing | **4** (AAL-A, AAL-B, DBS-A, DBS-B) |
| Scenarios with no output | **4** (TGT-A, TGT-B, TOY-A, TOY-B): provider credits were exhausted (HTTP 429 "no credits remaining") |
| Critical requirement failures among the four completed briefings | **3** |
| Average assessed usefulness (four briefings) | **3.0 / 5** |
| Citation audit | **34 of 34** citation-bearing items supported or appropriately qualified |
| Frozen acceptance criteria | **Not met** |
| Spend | USD 0.0606 of the USD 0.40 ceiling (per briefing: 0.0134, 0.0201, 0.0098, 0.0173) |

What the completed briefings showed (the owner's and ChatGPT's assessment):

- **Strong:** AAL-B on commercial approvals and customer commitments (its PDF separates a 28% discount request from an
  acknowledgment that was "not approval", and cites the synthetic records).
- **Strong:** DBS-B on contradictory vendor documentation.
- **Weak:** public-company research coverage in AAL-A and DBS-A was inadequate.

## 3. The four missing scenarios

TGT-A, TGT-B, TOY-A and TOY-B each started, reached the model client and received a provider 429 error ("no credits
remaining"). The application reported "The language model could not be reached", no briefing was produced and no cost was
incurred. Because the rule is one attempt per scenario, **none was retried**, and the evaluation cannot be completed
under its authorization. Nothing is known about how the application would have performed on Target or Toyota. These four
scenarios are **not** counted as passes, and they are not scored as failures of the application either: they have no output.

## 4. The runner stopping-rule defect

The authorization (section 2) says the whole run must stop on a refused model call, and continue only when the pipeline
reports an ordinary failure for a scenario. The runner's classifier (`classify()` in the archive's `scripts/fresh_evaluation_run.py`, not included here)
looks for a top-level `error` or a spending-cap refusal. The application had already caught the provider error and turned
it into a normal error status with a message, so the runner saw "an ordinary failure", recorded it as `failed` and went on
to the next scenario. As a result, TGT-A, TGT-B, TOY-A and TOY-B were each started once after the first credit failure.
Effects: no extra spend (each cost zero), no retries and no change to any frozen file; but the run did not stop when it
should have. The defect has not been repaired, because the runner is frozen.

## 5. Limits of the evidence

- **Ratings are adopted, not independent.** The usefulness ratings (average 3.0/5) were produced by ChatGPT and adopted by the
  project owner. They are not a separate second assessment performed by the owner. The written ratings and the Critical
  failure details are not stored in this repository; the figures here come from the owner's instructions.
- Four briefings is a small sample, and the two assessors helped build the system. Treat the results as indicative.
- Source-date and fragmentation limitations accepted before the run are listed in `RUN_AUTHORIZATION.md` section 3
  (for example AAL-S1, TGT-S1 and DBS-S1 rest on the page's own printed date; tables lose column headings when split).
- The live path had been tested only with mocks before the run; this was its first use against the real model client.
- The PDF headers show "Created: 15 Nov 2026 10:00 UTC", the evaluation's fixed information cutoff, not the date of the run.

## 6. Lessons learned

1. **Plan for the provider failing.** A prepaid credit balance was a single point of failure. A balance check before the
   run, or a rule that a first provider error stops the run, would have preserved the other four scenarios.
2. **Test the stopping rules on the real error path.** The rule was tested with a fake scenario runner; the real client's error
   was wrapped by the pipeline in a way the test did not cover.
3. **Retrieval coverage limits quality.** Where the knowledge for a public company was thin (AAL-A, DBS-A, and the empty
   company overview in DBS-B's PDF), the briefing could only say so; citation discipline (34/34) did not make it more useful.
4. **Provenance rules worked as designed.** Synthetic records stayed labelled as synthetic, contradictions were disclosed and
   not resolved, and nothing in the audit was an unsupported citation.
5. **Freeze and one-attempt rules protect honesty but cost completeness.** They prevented tuning after seeing results, and they
   also prevented a repeat after an external failure.

## 7. Where the evidence is

- Included here: [`docs/evaluation_evidence/`](evaluation_evidence/) (freeze manifest, freeze report, run authorization,
  requirement summary; unmodified copies) and the four briefing PDFs in [`portfolio/pdfs/`](../portfolio/pdfs/) with SHA-256 values in
  [`portfolio/README.md`](../portfolio/README.md). The PDFs are of the unscored briefings as generated; they are shown as evidence,
  not as a claim of quality.
- Not included (private development archive): the frozen package with its 293 hashed files, the third-party source copies, the
  scoring forms, the run records (run `20261120T183238Z_live_FE`) and the runner. The written ratings and Critical-failure details
  are not stored anywhere in the archive either.
