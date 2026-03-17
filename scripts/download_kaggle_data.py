#!/usr/bin/env python3
"""
Download March Machine Learning Mania data from Kaggle into data/raw/.

One-time setup (required for download):
  1. Create a Kaggle account at https://www.kaggle.com
  2. Join the competition (Accept the rules): https://www.kaggle.com/competitions/march-machine-learning-mania-2026
  3. Get an API key/token from Account → Create New API Token (or copy the key shown).
  4. Either:
     - Set env: export KAGGLE_API_TOKEN='KGAT_your_key_here'
     - Or put the key in ~/.kaggle/access_token: echo -n 'KGAT_...' > ~/.kaggle/access_token && chmod 600 ~/.kaggle/access_token
     - Or (legacy) put kaggle.json with {"username":"your_username","key":"your_key"} in ~/.kaggle/
  5. pip install kaggle  (or pip install -e ".[kaggle]" from project root)
  6. Run: python scripts/download_kaggle_data.py

If you get 403 Forbidden, you must join the competition and accept its rules on Kaggle first.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
COMPETITION = "march-machine-learning-mania-2026"


def main() -> int:
    try:
        import kaggle
    except ImportError:
        print("Kaggle API not installed. Run: pip install kaggle")
        print("Or from project root: pip install -e '.[kaggle]'")
        return 1

    if not RAW_DIR.exists():
        RAW_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {COMPETITION} into {RAW_DIR} ...")
    try:
        kaggle.api.competition_download_files(COMPETITION, path=str(RAW_DIR))
    except Exception as e:
        err = str(e)
        print("Download failed. Common causes:")
        if "403" in err or "Forbidden" in err:
            print("  - 403 Forbidden: join the competition and accept the rules at:")
            print("    https://www.kaggle.com/competitions/march-machine-learning-mania-2026")
        if "401" in err or "Unauthorized" in err:
            print("  - Set KAGGLE_API_TOKEN or add ~/.kaggle/access_token (or kaggle.json)")
        print("Error:", e)
        return 1

    # Kaggle downloads a zip; unzip if present
    zip_path = RAW_DIR / f"{COMPETITION}.zip"
    if zip_path.exists():
        import zipfile
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(RAW_DIR)
        zip_path.unlink()
        print("Extracted and removed zip.")
    print("Done. Files in", RAW_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
