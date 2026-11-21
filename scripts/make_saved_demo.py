"""Create the saved demonstration briefing (offline; no API calls, no credentials).

Usage: python scripts/make_saved_demo.py
Runs the offline demo for Shikun & Binui (follow-up meeting) and stores it in
data/demo/saved_briefing_shikun_binui.json with its original creation date and a SIMULATED label.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from deal_prep.app_service import BriefingService, save_demo  # noqa: E402


def main() -> int:
    result, _ = BriefingService().get("Shikun & Binui", None, "follow_up")
    path = save_demo(result)
    print(f"Saved {result['status']} briefing created {result['created_at']} -> {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
