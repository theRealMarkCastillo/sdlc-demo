"""CVE-2025-71176 mitigation: override pytest basetemp to a project-local
directory instead of the predictable /tmp/pytest-of-{user}.

This prevents local symlink-race (TOCTOU) attacks on multi-user UNIX systems.
Dev-only — CI/Docker environments have ephemeral filesystem isolation."""
import os
import stat
from pathlib import Path

import pytest


def _make_secure_basetemp() -> Path:
    """Create a project-local basetemp with 0o700 permissions."""
    basetemp = Path(__file__).resolve().parent.parent / ".pytest_tmp"
    os.makedirs(basetemp, exist_ok=True)
    os.chmod(basetemp, stat.S_IRWXU)  # 0o700 — owner-only
    return basetemp


def pytest_configure(config: pytest.Config) -> None:
    """Set basetemp to a project-local directory with restricted permissions."""
    # Only override if not already set (e.g. by --basetemp CLI flag or CI)
    if config.option.basetemp is None:
        config.option.basetemp = str(_make_secure_basetemp())
