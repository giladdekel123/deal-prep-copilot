"""Plain-language run outcomes for the user interface (kept apart from the pipeline so the public demo can show them
without importing the research pipeline)."""

STATUS_TEXT = {
    "briefing_ready": "Briefing ready",
    "partial_briefing": "Partial briefing: some information is not included (see gaps)",
    "no_briefing": "No briefing: not enough reliable sources",
    "clarification_required": "Please clarify which company you mean",
    "error": "No briefing: the draft could not be produced",
}
