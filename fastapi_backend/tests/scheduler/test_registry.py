from __future__ import annotations

import subprocess
import sys

from scheduler.jobs._registry import discover, reset_discovery_for_tests
from scheduler.jobs.registry import refresh_registered_job_keys


def test_discover_registers_sample_heartbeat():
    reset_discovery_for_tests()
    registry = discover()
    refresh_registered_job_keys()
    assert "sample_heartbeat" in registry
    assert registry["sample_heartbeat"].title == "Sample Heartbeat"


def test_no_duplicate_job_keys():
    reset_discovery_for_tests()
    assert discover()  # duplicate keys raise RuntimeError during discover
    refresh_registered_job_keys()


def test_job_modules_stay_light():
    """job 패키지 import 만으로 무거운 의존성이 끌려오면 실패한다."""
    code = (
        "import sys; "
        "from scheduler.jobs._registry import reset_discovery_for_tests, discover; "
        "reset_discovery_for_tests(); discover(); "
        "heavy={'playwright','selenium','pandas','bs4'} & "
        "set(m.split('.')[0] for m in sys.modules); "
        "print(sorted(heavy))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=None,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "[]", (
        f"job 모듈이 최상단에서 무거운 패키지를 import 함: {out.stdout}"
    )
