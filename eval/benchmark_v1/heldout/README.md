# Held-out split — FICTIONAL TEST DATA (draft, not frozen)

- **What it holds:** 6 fictional companies (one per industry) and 12 scenarios.
- **Drafted** by Claude Code in I0-b.
- **Then, privately:** the owner edits selected values in `forms/*.txt`.
- **Freeze:** checkpoint A1, by `python scripts/benchmark_heldout.py freeze` (owner's decision only).

Until the freeze, the benchmark runner refuses this split, and the development tools and tests never read it.

## How the owner's private values stay out of the development process

- **Plain-text forms, no JSON.** Each form line is one value, with an explanation and its format.
- **Expected outcomes follow automatically.** They are derived from the values by fixed general rules, so nobody
  edits the answers.
- **The tools never print a value:** `status`, `check` and `freeze` print only OK, problems by value name, counts of
  changed values and file counts. `review <n>` writes a private page under `runs/benchmark_v1/heldout_review/` and
  prints only its path.
- **The rendered copy is deleted.** The copy that `check` renders, to verify that every expected reference matches
  exactly one passage, is deleted afterwards.

## What this does NOT guarantee (stated limitation)

The test is **partially blind, not fully blind**:

1. **Structure.** Claude Code wrote the six companies, their structure, the planted conditions and the derivation
   rules. Only the owner's changed values are unknown to it.
2. **Values left unchanged.** Any value the owner leaves as drafted is known to Claude Code. `status` reports how
   many values were changed.
3. **The files are readable.** The forms are ordinary files on the same disk. Claude Code is committed not to open
   them or the review pages, but no tool can enforce that. The owner can add a Claude Code permission rule that denies
   reading `eval/benchmark_v1/heldout/forms/` and `runs/benchmark_v1/heldout_review/`. That is an owner action, not
   done by Claude Code.
4. **Scored runs reveal little, but not nothing.** Since I0-c, held-out runs show the development process only
   aggregate counts; failure details stay in the gitignored owner folder `runs/benchmark_v1/heldout_private/`, which
   Claude Code is committed not to open (the same procedural limit as point 3). Aggregate counts still reveal a
   little, which is one reason held-out runs are limited to 3.
5. **The hashes.** The freeze hashes prove that files did not change after the freeze. They do not hide the values
   from someone who can read the files.

See `REVIEW_GUIDE.md` for the owner's step-by-step review.
