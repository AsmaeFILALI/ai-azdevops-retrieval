"""Package registry settings must reach builds without silently being ignored."""

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("shell", ["pwsh", "bash"])
@pytest.mark.parametrize("name", ["PIP_INDEX_URL", "NPM_CONFIG_REGISTRY"])
@pytest.mark.parametrize(
    "value,mode,accepted",
    [
        ("https://packages.example.invalid:443/repository/feed/", "local", True),
        ("https://packages.example.invalid/simple/", "LOCAL", True),
        ("", "", True),
        ("", "acr-task", True),
        ("https://packages.example.invalid/simple/", "acr-task", False),
        ("https://packages.example.invalid/simple/", "", False),
        ("http://packages.example.invalid/simple/", "local", False),
        ("https://user:dummy@packages.example.invalid/simple/", "local", False),
        ("https://packages.example.invalid/simple/?token=dummy", "local", False),
        ("https://packages.example.invalid/simple/#dummy", "local", False),
        ("https://packages.example.invalid/with space", "local", False),
    ],
)
def test_registry_preflight(tmp_path, shell, name, value, mode, accepted):
    executable = shutil.which(shell)
    if not executable:
        pytest.skip(f"{shell} is unavailable")
    suffix = "ps1" if shell == "pwsh" else "sh"
    source = (ROOT / "scripts" / f"preDeploy.{suffix}").read_text(encoding="utf-8-sig")
    start = source.index("# Package registry overrides")
    end = source.index("# Foundation guard", start) if shell == "pwsh" else source.index(
        "# ---------- Global env & RG", start
    )
    script = tmp_path / f"registry.{suffix}"
    prefix = "" if shell == "pwsh" else 'red() { printf "%s\\n" "$*" >&2; }\n'
    script.write_text(prefix + source[start:end], encoding="utf-8", newline="\n")
    environment = {
        **os.environ,
        "PIP_INDEX_URL": "",
        "NPM_CONFIG_REGISTRY": "",
        "BUILD_MODE": mode,
        name: value,
    }
    command = [executable, "-NoProfile", "-File", str(script)] if shell == "pwsh" else [
        executable, str(script)
    ]
    result = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=30)
    assert (result.returncode == 0) == accepted, result.stdout + result.stderr
    if not accepted:
        assert name in result.stdout + result.stderr
        assert "dummy" not in result.stdout + result.stderr
        assert value not in result.stdout + result.stderr


def test_customer_profile_exposes_optional_registries_without_changing_defaults():
    inputs = json.loads(
        (ROOT / "samples/customer-poc/azd-env.example.json").read_text(encoding="utf-8")
    )["inputs"]
    assert inputs["BUILD_MODE"] == "local"
    assert inputs["PIP_INDEX_URL"] == ""
    assert inputs["NPM_CONFIG_REGISTRY"] == ""


def test_bash_fails_before_using_inherited_values_when_jq_is_unsupported(tmp_path):
    executable = shutil.which("bash")
    if not executable:
        pytest.skip("bash is unavailable")
    source = (ROOT / "scripts/preDeploy.sh").read_text(encoding="utf-8")
    snippet = source[source.index('azd_values="$(cd'):source.index("# ---------- Global env & RG")]
    script = tmp_path / "unsupported-jq.sh"
    script.write_text(
        'repo_root=.\nred() { printf "%s\\n" "$*" >&2; }\n'
        'azd() { printf \'%s\' \'{"BUILD_MODE":"local"}\'; }\n'
        'jq() { return 2; }\n' + snippet + '\nprintf "unexpected-success"\n',
        encoding="utf-8", newline="\n",
    )
    result = subprocess.run(
        [executable, str(script)], capture_output=True, text=True, timeout=30
    )
    assert result.returncode != 0
    assert "jq 1.7+" in result.stderr
    assert "unexpected-success" not in result.stdout


def test_customer_runbook_explains_saving_and_resetting_registries():
    guide = (ROOT / "docs/customer/azure-devops-markdown-poc.md").read_text(encoding="utf-8")
    for name in ("PIP_INDEX_URL", "NPM_CONFIG_REGISTRY"):
        assert f"azd env set {name}" in guide
        assert f"azd env unset {name}" in guide
    for required in ("BUILD_MODE local", "credential-free HTTPS", "files.pythonhosted.org"):
        assert required in guide
