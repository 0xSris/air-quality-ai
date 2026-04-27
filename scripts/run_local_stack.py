from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend-only", action="store_true")
    parser.add_argument("--frontend-only", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    python_executable = Path(os.environ.get("AIR_QUALITY_PYTHON", sys.executable))
    backend_cmd = [
        str(python_executable),
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--reload",
    ]
    frontend_cmd = ["npm.cmd", "run", "dev", "--", "--host", "0.0.0.0"]

    env = os.environ.copy()
    processes: list[subprocess.Popen[str]] = []
    try:
        if not args.frontend_only:
            processes.append(subprocess.Popen(backend_cmd, cwd=root, env=env))
        if not args.backend_only:
            processes.append(subprocess.Popen(frontend_cmd, cwd=root / "frontend", env=env))
        while True:
            time.sleep(1)
            for process in processes:
                if process.poll() is not None:
                    raise SystemExit(process.returncode)
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        sys.exit(0)


if __name__ == "__main__":
    main()
