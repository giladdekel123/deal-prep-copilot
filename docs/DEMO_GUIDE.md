# Deal-Prep Copilot — Optional Interview Walkthrough

A short walkthrough (about 5–8 minutes, shortenable to 3) for a job interview or a screen share. It is optional: the README
and `portfolio/` stand on their own. The application is shown **offline at no cost**; AI output is shown from **recorded PDFs**.
No API key and no live call are needed.

> Nivarque Document Systems is **fictional**; every customer relationship, proposal and meeting described here is **synthetic**. The real
> companies named have no affiliation with this project and have not reviewed it (see "No affiliation" in `README.md`).

Companion documents: `README.md`, `portfolio/README.md` (recorded PDFs, CV text), `docs/FINAL_EVALUATION_SUMMARY.md`,
`docs/KNOWN_LIMITATIONS.md`.

## Before the interview

1. In a Conda prompt:
   ```
   conda activate deal_prep_env
   set HF_HUB_OFFLINE=1
   set TRANSFORMERS_OFFLINE=1
   set ANONYMIZED_TELEMETRY=False
   python scripts/demo_rehearsal.py
   ```
   Every check should print PASS (35 of 35 on 21 November 2026). If not, see Troubleshooting in the README.
2. Start the app: `streamlit run app/streamlit_app.py --server.address 127.0.0.1 --server.port 8501`. Click **Load saved
   demonstration briefing (SIMULATED)** once to warm the index (about 10 seconds the first time).
3. Open `portfolio/pdfs/AAL-B.pdf` and `portfolio/pdfs/DBS-B.pdf`.

## Walkthrough

**1. The one-sentence pitch (30 s).** "A meeting-briefing assistant for a salesperson at a *fictional* vendor, Nivarque Document
Systems. Public facts about real companies are cited from dated sources; every relationship with them is synthetic and labelled,
and code rejects drafts whose citations are invented, mis-attributed or hide a conflict."

**2. Architecture (1 min).** Show the README diagram: code-driven orchestrator → hybrid search (vector + BM25) over a local
knowledge base and approved meeting history → one AI draft → validators → English/Hebrew PDF. Optional bounded agent (at most
three read-only searches). Spend caps are enforced in code before any paid call.

**3. The app, offline (2–3 min).** State that offline mode is a template, not AI; it shows the interface and the checks.
- *Saved demonstration:* the SIMULATED banner, the six sections, `FACT`/`ANALYSIS`/`RECOMMENDATION` tags and `PUBLIC SOURCE`/`SYNTHETIC` badges.
- *Public portfolio version:* the public-source sentences in this app are project-written summaries of facts (not quotations); say so if asked.
- *Name ambiguity:* choose **Other company**, type **Arup**, leave the domain empty, **Prepare briefing**. The app stops and asks
  for the domain instead of guessing (Arup versus ARUP Laboratories). Then run **Arup / Negotiation**: both of Arup's own dates
  (1977 and 1979) appear with sources; neither is presented as established. In this public version the two statements are project-written summaries, shown with the prefix "Summary:".
- *Optional, if time:* on **Meeting History**, paste synthetic notes, **Propose structure**, approve, and open **Follow-up Tasks**.
  The proposer is rule-based (no AI). In the 9 November 2026 walkthrough a later briefing missed some follow-up details; a later development phase addressed this (limitation 24), but it has not been re-demonstrated in the interface.

**4. Recorded AI output (1–2 min).**
- `AAL-B.pdf` (Anglo American, negotiation): a customer asked for a 28% discount; the briefing says Nivarque's reply "was not
  approval" and cites the synthetic records.
- `DBS-B.pdf` (DBS Group, product demo): two synthetic vendor documents disagree on which tiers include SCIM; the briefing quotes both
  and says "neither is treated as established". Its company overview reads "No supported content": an honest gap.
- Say that the relationships are fictional and that these are two of four completed outputs from an evaluation that did not pass.

**5. The evaluation, honestly (1–2 min).** A frozen, pre-registered evaluation (43 requirements, 15 Critical, one attempt per
scenario). Result: **criteria not met**; 4 of 8 scenarios completed (provider credits ran out); 3 Critical failures; usefulness
3.0/5 (ChatGPT's ratings, adopted by the owner, not independent); citations 34/34; public-only briefings had inadequate research
coverage; the runner did not stop at the first credit failure (defect, frozen, unrepaired).

**6. What I learned (30 s).** Citation discipline made the output trustworthy but not automatically useful; coverage of the
company's own public information limited usefulness most; check the provider balance before an irreversible run; test stopping
rules on the real error path; freeze rules protect honesty but make a run brittle.

## Questions to expect

- **"Did it pass?"** No. Say what failed and what you would do next (restore credits, repair the runner's classifier in a new
  versioned evaluation, improve public-source retrieval).
- **"Is the data real?"** Public facts are real and cited; the vendor and every customer relationship are synthetic and labelled.
- **"Why offline mode without AI?"** So the project runs anywhere at no cost; AI quality is shown only through recorded outputs.
- **"What would you change?"** Retrieval coverage for public companies; a cross-platform font and launcher; a second, independent assessor.
- **"Can it run live now?"** Only with your own key and credits; the project account's credits were exhausted on 20 November 2026.
  Earlier live runs (6 November 2026) took 17.6–32.7 seconds and USD 0.007–0.013 per briefing.

## Reset

Stop the app. Delete `runs/history.sqlite` to remove demonstration records. Do not delete the spend and credit ledgers in `runs/`.
