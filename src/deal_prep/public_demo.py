"""Public demonstration mode (Phase 9B): a restricted, strictly offline view of the saved synthetic briefing.

Switch: the environment variable DEAL_PREP_PUBLIC_DEMO. It is read on every call, on the server, so nothing a visitor
does in the browser can change it. Any value except empty, 0, false, no or off turns the mode ON (fail-safe).

When it is on, the service boundary refuses everything that could spend money, reach an external service or write
shared state: new briefings, OpenAI, Tavily, and the history/tasks database. Visitors can only view the saved
SIMULATED briefing and download its approved English PDF.

This module is deliberately light: it imports only the standard library and `config`, so the public demo never has
to import Chroma, torch, sentence-transformers, OpenAI or httpx.
"""
import json
import os
from pathlib import Path

from deal_prep import config

ENV_VAR = "DEAL_PREP_PUBLIC_DEMO"
SAVED_DEMO_PATH = config.PROJECT_ROOT / "data" / "demo" / "saved_briefing_shikun_binui.json"
APPROVED_PDF_PATH = config.PROJECT_ROOT / "portfolio" / "pdfs" / "examples" / "saved_demo_shikun_binui_en.pdf"
NOTICE = ("**Public demonstration: simulated data.** This page shows one saved, SIMULATED briefing for a fictional "
          "vendor (Nivarque Document Systems). It runs offline: no AI service, no news search and no database is "
          "used, and nothing you do here is saved. It is a portfolio demonstration, not a production service.")


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


class PublicDemoService:
    """The only service the public demo uses. It holds no state and touches no database."""

    def pdf(self, result: dict, language: str = "en") -> tuple[bytes, dict]:
        """The existing approved English PDF of the saved demonstration, served as stored (never generated)."""
        if language != "en":
            raise PublicDemoRestricted("Only the English PDF is available in the public demonstration.")
        if not result.get("saved_demo"):
            raise PublicDemoRestricted("Only the saved demonstration briefing can be downloaded.")
        return APPROVED_PDF_PATH.read_bytes(), {"pages": 1}
