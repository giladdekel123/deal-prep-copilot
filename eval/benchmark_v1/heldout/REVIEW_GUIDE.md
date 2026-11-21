# Held-out review guide for the owner — FICTIONAL TEST DATA

About 45–60 minutes. You need a text editor and an **Anaconda Prompt** opened in the project folder. You never edit
JSON.

## Before you start

1. Open an Anaconda Prompt and go to the project folder:
   ```
   cd path\to\Deal-Prep-Copilot
   conda activate deal_prep_env
   ```
2. **Keep your values private:**
   - Use this prompt, not the Claude Code chat, for every step below.
   - The commands print no values, so their output is safe to share. The forms and the review pages are not: never
     paste them, or any value, into the chat.
   - **Optional extra protection:** add a Claude Code permission rule that denies reading
     `eval/benchmark_v1/heldout/forms/` and `runs/benchmark_v1/heldout_review/`.

## Step 1 — Look at one company

1. Run `python scripts/benchmark_heldout.py review 1`.
2. Open the page it names. It shows the company's values, what the benchmark will expect because of them, and every
   rendered source and news item.
3. Check that it reads as clearly fictional and sensible.

## Step 2 — Change some of its values

Open `eval/benchmark_v1/heldout/forms/HXA.txt`. Each value has a one-line explanation above it. Change **at least
three** values, keeping the format in [brackets]. Good changes are ones that alter the answer, for example:

- make the aggregator's count **different** from the official count, so there is a genuine contradiction, or the
  **same**, so it is a copy;
- set the state year **earlier** than the decision year, so there is a genuine contradiction;
- change a task's status, for example Completed, so it is no longer an open item;
- set the main news to `stale`, so it must be ignored;
- change dates or the product. Dates must come after the record dates shown on the review page; `check` will tell
  you if one does not.

## Step 3 — Check your edits

Run `python scripts/benchmark_heldout.py check`. Every company should say OK. If one shows PROBLEMS, the message names
the value to fix, without showing your value. Then run `review 1` again to see the new expected answers, if you wish.

## Step 4 — Repeat for companies 2 to 6

The forms are `HXB.txt` … `HXF.txt`; the review pages are `review 2` … `review 6`.

## Step 5 — Confirm and tell Claude Code

Run `python scripts/benchmark_heldout.py status`. It prints how many values you changed per company. Then tell
Claude Code in the chat whether you approve the freeze (A1). Report only the counts, not the values.

## Step 6 — Freeze (after your approval)

`python scripts/benchmark_heldout.py freeze` records the hashes. From then on, any change to a held-out file stops
the held-out run.
