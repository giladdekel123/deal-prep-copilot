"""Create the two additional saved SIMULATED demonstration briefings for the public demo (offline; no API calls).

Usage: python scripts/make_cloud_demos.py

Same procedure as scripts/make_saved_demo.py: the offline demo (template drafting, no AI, no news) runs for each
company over the approved local corpus, and the result is stored with `save_demo` (original creation date,
SIMULATED label) together with its English PDF, built by the same `build_pdf` the application uses.
Nothing is edited by hand. The Shikun & Binui demonstration is not touched.
A temporary index and history database are used, so the local application state is not changed.
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("DEAL_PREP_NO_DOTENV", "1")  # offline only: never read .env or API keys
for key in ("OPENAI_API_KEY", "TAVILY_API_KEY", "DEAL_PREP_PUBLIC_DEMO"):
    os.environ.pop(key, None)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from deal_prep.app_service import DEMO_COMPANIES, BriefingService, save_demo  # noqa: E402
from deal_prep.pdf_export import build_pdf  # noqa: E402
from deal_prep.public_demo import APPROVED_DEMOS, load_saved_demo  # noqa: E402

PURPOSE = "general"


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="deal_prep_cloud_demos_"))
    service = BriefingService(chroma_dir=tmp / "chroma", history_path=tmp / "history.sqlite")
    for key, demo in APPROVED_DEMOS.items():
        if key == "shikun_binui":
            continue  # the existing demonstration is preserved as it is
        result, _ = service.get(demo.company, DEMO_COMPANIES[demo.company], PURPOSE, "offline_demo")
        path = save_demo(result, demo.json_path)
        saved = load_saved_demo(path)  # the PDF is built from the saved record, so it carries the SIMULATED label
        pdf, info = build_pdf(saved, saved.get("generation_label", ""), "en")
        demo.pdf_path.write_bytes(pdf)
        print(f"{demo.company}: {result['status']}, {len(result['evidence'])} evidence items, created "
              f"{result['created_at']} -> {path.relative_to(ROOT)}, {demo.pdf_path.relative_to(ROOT)} "
              f"({info['pages']} pages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
