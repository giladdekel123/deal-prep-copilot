"""Entry point for the free public demonstration (Streamlit Community Cloud): set "Main file path" to this file.

It forces the restricted, offline public-demo mode before the application starts, removes any API keys from the
process environment, and then runs the normal application file. The application itself reads the same switch.
"""
import os
import runpy
from pathlib import Path

os.environ["DEAL_PREP_PUBLIC_DEMO"] = "1"
os.environ["DEAL_PREP_NO_DOTENV"] = "1"
for _key in ("OPENAI_API_KEY", "TAVILY_API_KEY"):
    os.environ.pop(_key, None)

runpy.run_path(str(Path(__file__).with_name("streamlit_app.py")), run_name="__main__")
