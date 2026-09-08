"""Entrada de console para iniciar o piloto Streamlit."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    app_path = Path(__file__).with_name("pilot_app.py")
    completed = subprocess.run(  # noqa: S603 - argumentos fixos, sem shell.
        [sys.executable, "-m", "streamlit", "run", str(app_path), *sys.argv[1:]],
        check=False,
    )
    return completed.returncode


__all__ = ["main"]
