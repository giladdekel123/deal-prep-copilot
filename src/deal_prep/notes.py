"""Propose a structured meeting record from free-text notes (Prompt 06 step 3–4; spec FR-13).

This is a deterministic, rule-based demo proposer (no AI model): it only copies sentences from the
notes into categories, so it cannot invent participants, decisions, commitments or dates. Its output
is a PROPOSAL, stored as DRAFT until a person reviews, edits and approves it.

Dates: an explicit calendar date written in a task sentence becomes a *suggested* due date that still
needs confirmation; vague expressions (e.g. "Friday", "next week", "end of the month") are kept as raw
text with NO due date. Missing information is listed under `unknowns`, never filled in.
The same output contract can later be produced by an LLM proposer behind the same validation.
"""
import re
from datetime import date, datetime

PROPOSER_LABEL = "Proposed by a rule-based demo extractor from your notes (no AI model). Review before approving."

_CATEGORIES = {
    "concerns": r"\b(concern|concerned|worried|worry|risk|issue|problem|asked about|question about|unsure)\b",
    "decisions": r"\b(agreed|decided|decision|approved|chose|selected|confirmed that)\b",
    "commitments": r"\b(we will|we'll|they will|they'll|will send|will provide|will confirm|committed|promised)\b",
}
_TASK = r"\b(follow[- ]up|action|to do|todo|send|prepare|schedule|share|arrange|confirm)\b"
_VAGUE = (r"\b(next\s+(week|month|monday|tuesday|wednesday|thursday|friday)|"
          r"(this|by)\s+(monday|tuesday|wednesday|thursday|friday|week|weekend)|"
          r"monday|tuesday|wednesday|thursday|friday|tomorrow|soon|asap|end of (the )?(week|month|quarter)|"
          r"later this (week|month))\b")
_MONTHS = "january february march april may june july august september october november december".split()


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip(" -•*\t") for p in parts if p.strip(" -•*\t")]


def _explicit_date(sentence: str) -> tuple[str, str] | None:
    """(ISO date, the exact text matched) for a full calendar date written in the sentence."""
    iso = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", sentence)
    if iso:
        try:
            return date.fromisoformat(iso.group(1)).isoformat(), iso.group(1)
        except ValueError:
            return None
    m = re.search(r"\b(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\s+(\d{4})\b", sentence, re.IGNORECASE)
    if m:
        try:
            parsed = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %B %Y").date()
            return parsed.isoformat(), m.group(0)
        except ValueError:
            return None
    return None


def propose_structure(notes: str) -> dict:
    sentences = _sentences(notes)
    proposal = {"participants": [], "summary": "", "concerns": [], "decisions": [], "commitments": [],
                "tasks": [], "unknowns": [], "proposer": PROPOSER_LABEL}
    body = []
    for s in sentences:
        lead = re.match(r"^(participants|attendees)\s*:\s*(.+)$", s, re.IGNORECASE)
        if lead:
            proposal["participants"] = [p.strip() for p in re.split(r",|;| and ", lead.group(2)) if p.strip()]
            continue
        body.append(s)
        for cat, pattern in _CATEGORIES.items():
            if re.search(pattern, s, re.IGNORECASE):
                proposal[cat].append(s)
        if re.search(_TASK, s, re.IGNORECASE):
            explicit = _explicit_date(s)
            vague = re.search(_VAGUE, s, re.IGNORECASE)
            proposal["tasks"].append({
                "description": s,
                "suggested_due_date": explicit[0] if explicit else None,  # still needs confirmation
                "due_raw": explicit[1] if explicit else (vague.group(0) if vague else None),
                "needs_confirmation": bool(explicit or vague),
            })
    proposal["summary"] = " ".join(body[:2])
    if not proposal["participants"]:
        proposal["unknowns"].append("participants not stated in the notes")
    for t in proposal["tasks"]:
        if t["suggested_due_date"] is None and t["due_raw"]:
            proposal["unknowns"].append(f"due date for '{t['description'][:60]}' is vague ('{t['due_raw']}'); "
                                        "not converted to a calendar date")
    return proposal
