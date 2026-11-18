"""Fresh component checkouts must build the pinned commit, not a moved branch head."""

import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def git(*args, cwd=None):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.fixture
def remote(tmp_path):
    """A remote whose branch moved past the reviewed commit, plus an unrelated commit."""
    work = tmp_path / "work"
    work.mkdir()
    git("init", "--quiet", "--initial-branch=feature/pinned", cwd=work)
    git("config", "user.name", "Offline Test", cwd=work)
    git("config", "user.email", "offline@example.invalid", cwd=work)
    (work / "app.txt").write_text("reviewed")
    git("add", ".", cwd=work)
    git("commit", "--quiet", "-m", "reviewed", cwd=work)
    pinned = git("rev-parse", "HEAD", cwd=work)
    (work / "app.txt").write_text("later unvalidated merge")
    git("commit", "--quiet", "-am", "later", cwd=work)
    head = git("rev-parse", "HEAD", cwd=work)
    git("checkout", "--quiet", "--orphan", "unrelated", cwd=work)
    (work / "app.txt").write_text("foreign")
    git("commit", "--quiet", "-am", "foreign", cwd=work)
    foreign = git("rev-parse", "HEAD", cwd=work)
    bare = tmp_path / "remote.git"
    git("clone", "--quiet", "--bare", str(work), str(bare))
    git("--git-dir", str(bare), "config", "uploadpack.allowFilter", "true")
    git("--git-dir", str(bare), "config", "uploadpack.allowAnySHA1InWant", "true")
    return {"url": bare.resolve().as_uri(), "pinned": pinned, "head": head, "foreign": foreign}


def run_checkout(shell, tmp_path, url, expected):
    executable = shutil.which(shell)
    if not executable:
        pytest.skip(f"{shell} is unavailable")
    target = tmp_path / f"component-{shell}"
    environment = {
        **os.environ,
        "TEST_REPO": url, "TEST_TARGET": str(target), "TEST_EXPECTED": expected,
        # Keep the hook's safe.directory registration out of the user's real config.
        "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"),
    }
    if shell == "pwsh":
        source = (ROOT / "scripts/preDeploy.ps1").read_text(encoding="utf-8-sig")
        start = source.index("  if (Test-Path -LiteralPath $target) {")
        block = source[start:source.index("  $componentStatus =", start)]
        script = tmp_path / "checkout.ps1"
        script.write_text(
            '$name="fixture"; $refType="branch"; $ref="feature/pinned"; $hadErrors=$false\n'
            "$repo=$env:TEST_REPO; $target=$env:TEST_TARGET; $expectedCommit=$env:TEST_EXPECTED\n"
            "foreach ($item in @(1)) {\n" + block + "}\nif ($hadErrors) { exit 9 }\n",
            encoding="utf-8",
        )
        command = [executable, "-NoProfile", "-File", str(script)]
    else:
        source = (ROOT / "scripts/preDeploy.sh").read_text(encoding="utf-8")
        start = source.index('  if [ -d "$target" ]; then')
        block = source[start:source.index("  if ! component_status=", start)]
        script = tmp_path / "checkout.sh"
        script.write_text(
            'name=fixture; ref_type=branch; ref=feature/pinned; had_errors=0\n'
            'repo="$TEST_REPO"; target="$TEST_TARGET"; expected_commit="$TEST_EXPECTED"\n'
            'red(){ printf "%s\\n" "$*" >&2; }; yellow(){ printf "%s\\n" "$*"; }\n'
            "for item in 1; do\n" + block + 'done\n[ "$had_errors" = 0 ]\n',
            encoding="utf-8", newline="\n",
        )
        command = [executable, str(script)]
    result = subprocess.run(
        command, env=environment, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
    )
    return result, target


@pytest.mark.parametrize("shell", ["pwsh", "bash"])
@pytest.mark.parametrize("pin", ["pinned", "head"])
def test_fresh_branch_checkout_builds_the_exact_pin(tmp_path, remote, shell, pin):
    result, target = run_checkout(shell, tmp_path, remote["url"], remote[pin])
    assert result.returncode == 0, result.stdout + result.stderr
    assert git("rev-parse", "HEAD", cwd=target) == remote[pin]
    assert git("status", "--porcelain", "--untracked-files=all", cwd=target) == ""


@pytest.mark.parametrize("shell", ["pwsh", "bash"])
def test_unpinned_branch_still_clones_the_branch_head(tmp_path, remote, shell):
    result, target = run_checkout(shell, tmp_path, remote["url"], "")
    assert result.returncode == 0, result.stdout + result.stderr
    assert git("rev-parse", "HEAD", cwd=target) == remote["head"]


@pytest.mark.parametrize("shell", ["pwsh", "bash"])
@pytest.mark.parametrize("pin", ["foreign", "0" * 40])
def test_pin_outside_the_branch_history_fails(tmp_path, remote, shell, pin):
    result, _ = run_checkout(shell, tmp_path, remote["url"], remote.get(pin, pin))
    assert result.returncode != 0, result.stdout + result.stderr
    assert "not in the history of branch" in result.stdout + result.stderr


@pytest.mark.parametrize("shell", ["pwsh", "bash"])
def test_existing_stale_checkout_is_reported_and_left_unchanged(tmp_path, remote, shell):
    target = tmp_path / f"component-{shell}"
    git("clone", "--quiet", "--branch", "feature/pinned", remote["url"], str(target))
    result, _ = run_checkout(shell, tmp_path, remote["url"], remote["pinned"])
    assert result.returncode != 0
    assert "must resolve to" in result.stdout + result.stderr
    assert git("rev-parse", "HEAD", cwd=target) == remote["head"]
