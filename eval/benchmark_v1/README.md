# Intelligence benchmark v1 (Phase 4.5) — FICTIONAL TEST DATA

Every company, source, news item and meeting record in this folder is **fictional**, written only to evaluate the
briefing procedure. Domains use the reserved `.example` top-level domain. Nothing here describes a real organization,
and none of it is loaded by the app or into the demo index `dms_kb_v1`.

Plan: section 6.1 (Phase 4.5) of the portfolio release plan, which is in the private development archive and not included here. Status: **I0-b**, 6 development companies with 12 scenarios;
6 held-out companies with 12 scenarios, drafted, awaiting the owner's private edits and the A1 freeze.

## Layout

| Path | Content |
|---|---|
| `dev/companies/*.json` | One specification per fictional development company: sources, news, meeting history, scenarios and named values |
| `heldout/companies/*.json` | The same for the 6 held-out companies (draft values only) |
| `heldout/forms/*.txt` | The owner's plain-text value forms for the held-out companies (the values actually used) |
| `heldout/FROZEN.sha256` | Created only at checkpoint A1; the held-out split cannot run without it |

Each specification is rendered by `scripts/benchmark_spec.py` into source documents, news fixtures, a meeting-history
seed and scenarios. **Expected outcomes are derived from the specification by fixed general rules**, never written by
hand per scenario. For example:
- two different counts for the same date are a genuine contradiction; equal counts make the aggregator a copy;
- a state that begins before the decision that created it is a contradiction; otherwise the pair is compatible;
- a task marked Completed is no longer an open item;
- stale news must not reach the drafter.

Evidence is named by stable references (`<document>:E1`, `<document>:CLAIMS`, `<document>~<text>`, `NEWS:<key>`,
`HIST:<key>`). Each reference must match exactly one passage, otherwise the run stops with an error.

## Running

```
python scripts/benchmark_run.py --split dev --news both --repeat 2
```

- **Two news modes, reported in separate tables:**
  - `news_fixture` replays fictional news;
  - `news_off` switches news off exactly as the offline demo does, so news expectations are dropped, not passed.
- **Isolation:** each scenario runs in its own folder under `runs/benchmark_v1/` (gitignored).
- **Offline and fixed:** outbound connections are blocked, `.env` and API keys are not read, and the clock is fixed
  at 2026-11-09 09:00 UTC.
- **Protected data:** `chroma_db/`, `runs/history.sqlite`, the walkthrough history, `data/`, `src/` and `app/` are
  fingerprinted before and after each run.
- **Held-out split:** it runs only after the freeze, with matching hashes, at most 3 times (every execution counts,
  including failed ones), and only if no held-out name appears in production code. Development tools refuse it.
- **Held-out results are aggregate-only** (owner decision, I0-c): the terminal and `runs/benchmark_v1/<run>_heldout/`
  show only counts, vacuous-pass counts, intervals, rule coverage and limitations. Records, per-scenario scores,
  failure details and the run's console output go only to the gitignored owner folder
  `runs/benchmark_v1/heldout_private/<run>/`.

## Reading the scores

- **Every count is "passed / applicable",** with a 95% interval and every failure listed.
- **Rule coverage is stated for every metric:**
  - **full:** the rule decides the property exactly, given the expected outcomes;
  - **approximation:** a proxy that can miss cases;
  - **partial:** checks one part only.
  A full count on a partial metric is not a 100% result for the property.
- **O1 is a number-consistency check only.** It is **not** factual accuracy. Factual support is measured only by the
  separate manual claim-support audit (M2), whose coverage is always stated (plan §6.1 F).
- **Vacuous passes are reported separately.** A pass is vacuous when what it tests was absent, so nothing could go
  wrong. For example:
  - O3a passes when the system makes no conflict disclosure at all; read it with O3b;
  - O6b passes when no customer-specific opportunity is produced; read it with R1 and O6a.
  Vacuous passes are not a capability.
- **Not measured here:** overall factual accuracy, relevance and usefulness, quality of reasoning, live AI behaviour.

## Known limitation: internal classification (Option A)

- **What happens:** inside the isolated benchmark registry the fictional companies carry `reality: real` (plus
  `benchmark_fictional: true`), so that the unchanged production pipeline treats them as registered companies.
- **The side effect:** production-generated labels inside benchmark run records therefore read "(real, customer)"
  or "relationship with a real company".
- **That wording is not accurate:** every benchmark entity is fictional.
- **How it is contained:**
  - all benchmark records and reports are labelled FICTIONAL TEST DATA;
  - the app never loads this registry or this folder (tested).

Scoring rules: `scripts/benchmark_score.py` (deterministic; no AI judge). Tests: `tests/test_benchmark.py`.
