from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_empty_operational_state_smoke() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/smoke_empty_state.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "'status': 'passed'" in result.stdout
