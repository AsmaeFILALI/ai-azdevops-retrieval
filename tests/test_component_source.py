"""Execute the exact paired component clean-source guards against local Git."""

import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("shell", ["pwsh", "bash"])
@pytest.mark.parametrize("change", ["clean", "modified", "staged", "untracked", "not-a-repository"])
def test_component_build_requires_clean_source(tmp_path, shell, change):
    executable = shutil.which(shell)
    if not executable:
        pytest.skip(f"{shell} is unavailable")
    checkout = tmp_path / "component"
    checkout.mkdir()

    def git(*args):
        subprocess.run(["git", "-C", str(checkout), *args], check=True, capture_output=True)

    git("init", "--quiet")
    git("config", "user.name", "Offline Test")
    git("config", "user.email", "offline@example.invalid")
    (checkout / ".gitignore").write_text(".azure/\n")
    document = checkout / "file.txt"
    document.write_text("original")
    git("add", ".")
    git("commit", "--quiet", "-m", "fixture")
    if change in {"modified", "staged"}:
        document.write_text("changed")
        if change == "staged":
            git("add", "file.txt")
    elif change == "untracked":
        (checkout / "new.py").write_text("unreviewed")
    elif change == "not-a-repository":
        checkout = tmp_path / "not-git"
        checkout.mkdir()
    before = document.read_bytes()
    if shell == "pwsh":
        source = (ROOT / "scripts/preDeploy.ps1").read_text(encoding="utf-8-sig")
        guard = source[source.index("  $componentStatus ="):source.index("  # Copy shared azd env")]
        script = tmp_path / "guard.ps1"
        script.write_text(
            '$ErrorActionPreference="Continue"; $target=$env:TEST_CHECKOUT; $name="fixture"; $hadErrors=$false\n'
            + "foreach ($item in @(1)) {\n" + guard + "}\nif($hadErrors){exit 9}\n",
        )
        command = [executable, "-NoProfile", "-File", str(script)]
    else:
        source = (ROOT / "scripts/preDeploy.sh").read_text(encoding="utf-8")
        start = source.index('  if ! component_status=')
        guard = source[start:source.index('  git config --global --add safe.directory "$target"', start)]
        script = tmp_path / "guard.sh"
        script.write_text(
            'target="$TEST_CHECKOUT"; name=fixture; had_errors=0\nred(){ printf "%s\\n" "$*" >&2; }\n'
            + "for item in 1; do\n" + guard + 'done\n[ "$had_errors" = 0 ]\n',
            newline="\n",
        )
        command = [executable, str(script)]
    result = subprocess.run(
        command, env={**os.environ, "TEST_CHECKOUT": str(checkout)},
        capture_output=True, text=True, timeout=30,
    )
    assert (result.returncode == 0) == (change == "clean"), result.stdout + result.stderr
    assert document.read_bytes() == before


def test_clean_source_guard_precedes_environment_copy_and_child_build():
    ps1 = (ROOT / "scripts/preDeploy.ps1").read_text(encoding="utf-8-sig")
    bash = (ROOT / "scripts/preDeploy.sh").read_text(encoding="utf-8")
    assert ps1.index("$componentStatus =") < ps1.index("# Copy shared azd env")
    start = bash.index('if ! component_status=')
    assert start < bash.index('copy_dot_azure "$dot_azure" "$target"', start)
