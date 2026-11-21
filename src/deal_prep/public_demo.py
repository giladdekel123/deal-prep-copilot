"""Public demonstration mode (Phase 9B): a restricted, strictly offline view of the saved synthetic briefing.

Switch: the environment variable DEAL_PREP_PUBLIC_DEMO. It is read on every call, on the server, so nothing a visitor
does in the browser can change it. Any value except empty, 0, false, no or off turns the mode ON (fail-safe).

When it is on, the service boundary refuses everything that could spend money, reach an external service or write
shared state: new briefings, OpenAI, Tavily, and the history/tasks database. Visitors can only view the saved
SIMULATED briefing and download its approved English PDF.

This module is deliberately light: it imports only the standard library and `config`, so the public demo never has
to import Chroma, torch, sentence-transformers, OpenAI or httpx.
"""
import copy
import functools
import json
import os
from dataclasses import dataclass
from pathlib import Path

from deal_prep import config

ENV_VAR = "DEAL_PREP_PUBLIC_DEMO"
DEMO_DIR = config.PROJECT_ROOT / "data" / "demo"
SAVED_DEMO_PATH = DEMO_DIR / "saved_briefing_shikun_binui.json"
APPROVED_PDF_PATH = config.PROJECT_ROOT / "portfolio" / "pdfs" / "examples" / "saved_demo_shikun_binui_en.pdf"
NOTICE = ("**Public demonstration: simulated data.** Each briefing here was saved earlier by the project's offline "
          "template (no AI model, no news search, no database); choosing a company only opens its saved briefing. "
          "Nothing is researched or generated while you browse, and nothing you do is saved. "
          "**Nivarque Document Systems is fictional, and every relationship, proposal, price and meeting between it and "
          "these companies is synthetic.** The public facts about the real companies come from dated public sources, "
          "summarised in the project's own words; they are not fictional, but they may be out of date. "
          "This is a portfolio demonstration, not a production service.")


@dataclass(frozen=True)
class ApprovedDemo:
    company: str
    json_path: Path
    pdf_path: Path


# The only briefings the public demo can open: a fixed allowlist with explicit file mappings. A path is never built
# from visitor input; a visitor's choice is only ever looked up here.
APPROVED_DEMOS = {
    "shikun_binui": ApprovedDemo("Shikun & Binui", SAVED_DEMO_PATH, APPROVED_PDF_PATH),
    "arup": ApprovedDemo("Arup", DEMO_DIR / "saved_briefing_arup.json", DEMO_DIR / "saved_briefing_arup_en.pdf"),
    "ashtrom_group": ApprovedDemo("Ashtrom Group", DEMO_DIR / "saved_briefing_ashtrom_group.json",
                                  DEMO_DIR / "saved_briefing_ashtrom_group_en.pdf"),
}
DEFAULT_DEMO = "shikun_binui"


class PublicDemoRestricted(RuntimeError):
    """Raised when an action that the public demonstration forbids is attempted."""


def enabled() -> bool:
    return os.environ.get(ENV_VAR, "").strip().lower() not in ("", "0", "false", "no", "off")


def require_not_public(action: str) -> None:
    """Call at the top of anything that spends money, uses an external service or writes shared state."""
    if enabled():
        raise PublicDemoRestricted(f"{action} is disabled in the public demonstration ({ENV_VAR} is set).")


def load_saved_demo(path: Path = SAVED_DEMO_PATH) -> dict:
    """Load the saved demonstration. Never re-dated, never re-researched."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data.get("saved_demo"):
        raise ValueError(f"{path} is not a saved demonstration briefing")
    return data


def demo_label(key: str) -> str:
    return APPROVED_DEMOS[key].company


def purpose_label(saved: dict) -> str:
    """The meeting purpose stored in a saved briefing, for display only (e.g. "follow_up" -> "Follow-up")."""
    purpose = str(saved.get("purpose") or "")
    return purpose.replace("_", "-").capitalize() if purpose else "Not recorded"


def _approved(key) -> ApprovedDemo:
    if not isinstance(key, str) or key not in APPROVED_DEMOS:
        raise PublicDemoRestricted("That briefing is not one of the approved saved examples.")
    return APPROVED_DEMOS[key]


@functools.cache
def _load_approved(key: str) -> dict:
    return load_saved_demo(_approved(key).json_path)


def load_approved_demo(key) -> dict:
    """The saved briefing for an allowlisted key; anything else is refused. Returns a private copy."""
    _approved(key)
    return copy.deepcopy(_load_approved(key))


class PublicDemoService:
    """The only service the public demo uses. It holds no state and touches no database."""

    def pdf(self, result: dict, language: str = "en") -> tuple[bytes, dict]:
        """The approved English PDF of the saved demonstration, served as stored (never generated)."""
        if language != "en":
            raise PublicDemoRestricted("Only the English PDF is available in the public demonstration.")
        for key in APPROVED_DEMOS:  # find which approved briefing this is, by its run id and company
            saved = _load_approved(key)
            if (result.get("saved_demo") and result.get("run_id") == saved["run_id"]
                    and result.get("company_input") == saved["company_input"]):
                return _approved(key).pdf_path.read_bytes(), {"pages": 1}
        raise PublicDemoRestricted("Only the approved saved demonstration briefings can be downloaded.")
