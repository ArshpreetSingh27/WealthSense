"""Refresh market research and run only opted-in user paper bots."""

import os
import subprocess
import sys


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT_DIR = os.path.dirname(__file__)


def main():
    for script_name in ("fetch_benchmarks.py", "update_pipeline.py", "generate_daily_signals.py"):
        subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, script_name)], cwd=BASE_DIR, check=True)
    sys.path.insert(0, BASE_DIR)
    from paper_bot import run_all_enabled
    results = run_all_enabled()
    print(f"Market research refreshed; {len(results)} opted-in paper bots processed.")


if __name__ == "__main__":
    main()
