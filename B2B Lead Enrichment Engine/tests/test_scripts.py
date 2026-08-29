import pytest
import os
import subprocess
import sys


def test_script_enrich_inn_cli():
    cmd = [
        sys.executable,
        "scripts/enrich_inn.py",
        "7736207543",
        "--json"
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
    assert proc.returncode == 0
    assert "ЯНДЕКС" in proc.stdout or "7736207543" in proc.stdout


def test_script_audit_deliverability_cli():
    cmd = [
        sys.executable,
        "scripts/audit_deliverability.py",
        "yandex.ru",
        "--json"
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
    assert proc.returncode == 0
    assert "yandex.ru" in proc.stdout
    assert "deliverability_score" in proc.stdout
