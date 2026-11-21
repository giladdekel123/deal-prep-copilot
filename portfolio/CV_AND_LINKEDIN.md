# CV and LinkedIn text (draft for the owner to edit)

Every statement below is taken from the repository or the owner's recorded evaluation findings. Edit freely, but do not
upgrade the evaluation claims: the final frozen evaluation did **not** meet its acceptance criteria.

## CV entry (short)

**Deal-Prep Copilot — AI meeting-briefing assistant** (personal project, 2026; local only, not deployed) · Python, Streamlit, Chroma, OpenAI API, SQLite · developed with AI coding assistants (Claude Code, ChatGPT)

- Built a retrieval-augmented briefing generator for a fictional document-management vendor: hybrid vector + BM25 search over a
  local knowledge base, one structured AI draft, English/Hebrew PDF export, meeting history and follow-up tasks.
- Implemented code-level safeguards: citation, source-origin (real public versus synthetic) and conflict-disclosure validators that
  reject unsupported drafts; a bounded agent limited to three read-only searches; hard per-briefing and daily spend caps.
- Set up and ran a frozen, hash-verified, one-attempt internal evaluation (43 requirements). It did not meet its acceptance
  criteria: 4 of 8 scenarios completed (provider credits ran out), 3 Critical failures, average usefulness 3.0/5 (ratings produced by
  ChatGPT and adopted by me), and 34 of 34 audited citation-bearing items supported or appropriately qualified. Documented the
  runner defect and lessons learned.
- Offline pytest suite: 1,297 tests passed on 20 November 2026 (historical result).

## CV entry (one line)

Personal Python RAG application, built with AI coding assistants, with enforced citations, provenance rules, spend caps and a frozen internal evaluation that it did not pass.

## LinkedIn project description (about 120 words)

Deal-Prep Copilot is a personal project that prepares short meeting briefings for a salesperson at a fictional software vendor.
It combines hybrid search (vectors and BM25) over a local knowledge base with a single AI draft, then checks the draft in code:
every citation must exist, come from the right kind of source (real public information versus synthetic records) and disclose
conflicts. Costs are capped in code, and briefings export to English or Hebrew PDF. I developed it with AI coding assistants, and also ran a frozen, one-attempt internal evaluation.
It did not meet its acceptance criteria: only four of eight scenarios completed before the provider's credits ran out, and three
Critical requirements failed. I documented the results and lessons as they are. It is a local, undeployed portfolio project, not a production system. Stack: Python, Streamlit, Chroma, OpenAI, SQLite, pytest.

## Skills demonstrated

RAG and hybrid retrieval · LLM output validation and provenance · cost control · agent boundaries · evaluation design
(pre-registration, freezing, one-attempt rules) · incident analysis · test-driven development · technical writing.

## Do not claim

That the final evaluation passed; that results are independent (the ratings are ChatGPT's, adopted by the owner, from an internal
non-blind evaluation); that real companies are customers or partners; that the system is production-ready.
