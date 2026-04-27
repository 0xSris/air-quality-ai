from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from zipfile import ZipFile


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Path to the provided SIH zip file")
    parser.add_argument("--target", default="ml/data/raw", help="Directory where raw data should be extracted")
    args = parser.parse_args()

    source = Path(args.source)
    target = Path(args.target)
    target.mkdir(parents=True, exist_ok=True)
    with ZipFile(source) as zf:
        zf.extractall(target)
    print(f"Extracted dataset into {target.resolve()}")


if __name__ == "__main__":
    main()

