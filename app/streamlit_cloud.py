"""Entry point for the free public demonstration (Streamlit Community Cloud): set "Main file path" to this file.

It forces the restricted, offline public-demo mode before the application starts, removes any API keys from the
process environment, and then runs the normal application file. The application itself reads the same switch.
"""
import hashlib
import os
import runpy
import sys
from pathlib import Path

os.environ["DEAL_PREP_PUBLIC_DEMO"] = "1"
os.environ["DEAL_PREP_NO_DOTENV"] = "1"
for _key in ("OPENAI_API_KEY", "TAVILY_API_KEY"):
    os.environ.pop(_key, None)

# Streamlit re-imports a changed module only if it watches it, and it watches only the script's folder (app/) and
# PYTHONPATH. src/deal_prep is on sys.path at run time, so it is not watched: after an automatic redeploy the new page
# script would run against the previous deploy's already-imported modules. Dropping the project's own package from
# sys.modules (what Streamlit does for modules it watches) makes the next import read the files currently on disk.
# This is done only when the source files have changed since the last run (a redeploy), so two visitors browsing at the
# same time never evict modules under each other; `pop(name, None)` tolerates an entry another thread already removed.
# Only deal_prep is touched; libraries stay loaded. It does nothing in the normal Windows app.
_src = Path(__file__).resolve().parents[1] / "src" / "deal_prep"
_signature = hashlib.sha1(repr(sorted((p.name, p.stat().st_mtime_ns, p.stat().st_size)
                                      for p in _src.glob("*.py"))).encode()).hexdigest()
if os.environ.get("DEAL_PREP_SRC_SIGNATURE") != _signature:
    for _name in [n for n in list(sys.modules) if n == "deal_prep" or n.startswith("deal_prep.")]:
        sys.modules.pop(_name, None)
    os.environ["DEAL_PREP_SRC_SIGNATURE"] = _signature

runpy.run_path(str(Path(__file__).with_name("streamlit_app.py")), run_name="__main__")
