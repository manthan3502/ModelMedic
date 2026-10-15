import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import privacy_check

ASSET = "docs/assets/reviewed/example.png"
BINARY = bytes((137, 80, 78, 71, 255, 0))


def approval(path=ASSET, content=BINARY):
    return {"path": path, "sha256": hashlib.sha256(content).hexdigest()}


@pytest.fixture
def run_scan(tmp_path, monkeypatch):
    """Exercise the complete CLI with explicit Git fixtures, including history guards."""
    monkeypatch.chdir(tmp_path)
    originals = {f"docs/specs/locked{i}.md": f"locked {i}\n".encode() for i in range(4)}
    for name, content in originals.items():
        path = Path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def run(files=None, assets=None, history=None, history_identity=None):
        files = files or {}
        history = history or {}
        manifest = Path("scripts/reviewed_binaries.json")
        manifest.parent.mkdir(exist_ok=True)
        manifest.write_text(json.dumps({"version": 1, "assets": assets or []}), encoding="utf-8")
        for name, content in files.items():
            path = Path(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        blobs = {
            hashlib.sha256(content).hexdigest(): content
            for entries in history.values()
            for _, content in entries
        }
        candidates = [manifest.as_posix(), *files, *originals]

        def check_output(command):
            if command == ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"]:
                return "\0".join(candidates).encode()
            if command == ["git", "rev-list", "HEAD"]:
                return "\n".join(history).encode()
            if command[:3] == ["git", "show", "-s"]:
                identity = history_identity or "123+fixture@users.noreply.github.com"
                return f"{identity}\n{identity}\n".encode()
            if command[:3] == ["git", "ls-tree", "-r"]:
                return "".join(
                    f"100644 blob {hashlib.sha256(content).hexdigest()}\t{name}\n"
                    for name, content in history[command[3]]
                ).encode()
            if command[:3] == ["git", "cat-file", "blob"]:
                return blobs[command[3]]
            if command[:2] == ["git", "show"] and command[2].startswith("8e2029a:"):
                return originals[command[2].partition(":")[2]]
            raise AssertionError(command)

        def git_run(command, **kwargs):
            assert command in (
                ["git", "diff", "--exit-code", "8e2029a", "--", "docs/specs"],
                ["git", "check-ignore", "-q", ".env"],
            )
            return subprocess.CompletedProcess(command, 0)

        monkeypatch.setattr(privacy_check.subprocess, "check_output", check_output)
        monkeypatch.setattr(privacy_check.subprocess, "run", git_run)
        monkeypatch.setattr(sys, "argv", ["privacy_check.py", "--history"])
        privacy_check.main()

    return run


def test_unapproved_binary_fails(run_scan):
    with pytest.raises(SystemExit, match="binary candidate requires explicit privacy review"):
        run_scan(files={ASSET: BINARY})


def test_ordinary_text_still_passes(run_scan, capsys):
    run_scan(files={"notes.md": b"Reviewed documentation.\n"})
    assert "PASS:" in capsys.readouterr().out


def test_exact_review_passes_current_and_historical_scan(run_scan, capsys):
    run_scan(
        files={ASSET: BINARY},
        assets=[approval()],
        history={"revision": [(ASSET, BINARY)]},
    )
    assert "PASS:" in capsys.readouterr().out


@pytest.mark.parametrize("changed", [BINARY + b"changed", b"now UTF-8 text"])
def test_changed_approved_bytes_fail_even_if_they_become_text(run_scan, changed):
    with pytest.raises(SystemExit, match="reviewed binary SHA-256 mismatch"):
        run_scan(files={ASSET: changed}, assets=[approval()])


def test_matching_bytes_at_unapproved_path_fail(run_scan):
    with pytest.raises(SystemExit, match="renamed.png: binary candidate"):
        run_scan(files={"docs/assets/reviewed/renamed.png": BINARY}, assets=[approval()])


def test_history_deduplication_does_not_transfer_approval_to_other_paths(run_scan):
    with pytest.raises(SystemExit, match="older:docs/assets/renamed.png: binary historical"):
        run_scan(
            assets=[approval()],
            history={
                "newer": [(ASSET, BINARY)],
                "older": [("docs/assets/renamed.png", BINARY)],
            },
        )


def test_unapproved_historical_binary_fails(run_scan):
    with pytest.raises(SystemExit, match="binary historical artifact requires review"):
        run_scan(history={"revision": [(ASSET, BINARY)]})


def test_changed_historical_binary_fails(run_scan):
    with pytest.raises(SystemExit, match="revision:.*reviewed binary SHA-256 mismatch"):
        run_scan(assets=[approval()], history={"revision": [(ASSET, BINARY + b"changed")]})


@pytest.mark.parametrize("historical", [False, True])
def test_approval_does_not_override_forbidden_artifact_rules(run_scan, historical):
    name = "docs/assets/reviewed/forbidden.joblib"
    options = {"assets": [approval(name)]}
    if historical:
        options["history"] = {"revision": [(name, BINARY)]}
    else:
        options["files"] = {name: BINARY}
    with pytest.raises(SystemExit, match="prohibited"):
        run_scan(**options)


@pytest.mark.parametrize("historical", [False, True])
@pytest.mark.parametrize("approved", [False, True])
@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (("person" + "@" + "example.invalid").encode(), "email address"),
        (("gh" + "p_" + "A" * 36).encode(), "GitHub token"),
        (("sk-" + "A" * 45).encode(), "OpenAI key"),
        (("https://account:" + "sensitive" + "@service.invalid").encode(), "credential-bearing"),
    ],
)
def test_text_secret_checks_remain_enforced(run_scan, historical, approved, content, reason):
    options = {"assets": [approval(content=content)] if approved else []}
    if historical:
        options["history"] = {"revision": [(ASSET, content)]}
    else:
        options["files"] = {ASSET: content}
    with pytest.raises(SystemExit, match=reason):
        run_scan(**options)


def test_local_env_secret_still_rejected_without_logging_value(run_scan):
    secret = "local-fixture-" + "private-value"
    Path(".env").write_text("EXAMPLE_TOKEN=" + secret, encoding="utf-8")
    with pytest.raises(SystemExit, match="local environment secret") as error:
        run_scan(files={"notes.md": secret.encode()})
    assert secret not in str(error.value)


def test_history_identity_guard_still_enforced(run_scan):
    with pytest.raises(SystemExit, match="non-noreply Git identity"):
        run_scan(history={"revision": []}, history_identity="person" + "@" + "example.invalid")


@pytest.mark.parametrize(
    "raw",
    [
        "not JSON",
        "[]",
        "{}",
        '{"version":true,"assets":[]}',
        '{"version":2,"assets":[]}',
        '{"version":1,"assets":{}}',
        '{"version":1,"assets":[],"extra":true}',
        '{"version":1,"version":1,"assets":[]}',
        json.dumps({"version": 1, "assets": [approval(), approval()]}),
        json.dumps(
            {"version": 1, "assets": [approval(), approval(ASSET.replace("example", "EXAMPLE"))]}
        ),
        json.dumps({"version": 1, "assets": [approval(), approval(content=b"different")]}),
        json.dumps({"version": 1, "assets": [{**approval(), "extra": True}]}),
        json.dumps({"version": 1, "assets": [{"path": ASSET}]}),
        json.dumps({"version": 1, "assets": ["not an object"]}),
        '{"version":1,"assets":[{"path":"a","path":"b","sha256":"' + "a" * 64 + '"}]}',
    ],
)
def test_malformed_manifest_fails_closed_without_echoing_contents(tmp_path, raw):
    path = tmp_path / "manifest.json"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(SystemExit, match="^Reviewed binary manifest is missing or invalid$"):
        privacy_check.load_reviewed_binaries(path)


@pytest.mark.parametrize(
    "name",
    [
        "docs/assets/*",
        "docs/assets/?.png",
        "docs/assets/[ab].png",
        "docs/assets/",
        "docs/assets/../private.png",
        "docs/assets/a//b.png",
        "docs/assets/./b.png",
        "docs/assets/.hidden.png",
        "docs/assets/a\\b.png",
        "/docs/assets/a.png",
        "backend/a.png",
    ],
)
def test_patterns_directories_and_noncanonical_paths_fail(tmp_path, name):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"version": 1, "assets": [approval(name)]}), encoding="utf-8")
    with pytest.raises(SystemExit, match="manifest is missing or invalid"):
        privacy_check.load_reviewed_binaries(path)


@pytest.mark.parametrize("digest", ["a" * 63, "a" * 65, "A" * 64, "g" * 64, None, 1])
def test_malformed_digest_fails(tmp_path, digest):
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps({"version": 1, "assets": [{"path": ASSET, "sha256": digest}]}),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="manifest is missing or invalid"):
        privacy_check.load_reviewed_binaries(path)


def test_missing_manifest_fails(tmp_path):
    with pytest.raises(SystemExit, match="manifest is missing or invalid"):
        privacy_check.load_reviewed_binaries(tmp_path / "absent.json")
