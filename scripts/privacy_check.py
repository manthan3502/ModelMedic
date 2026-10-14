"""Review commit candidates without printing secret values. Not a general secret scanner."""

import argparse
import re
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true")
    args = parser.parse_args()
    files = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
        )
        .decode()
        .split("\0")
    )
    patterns = {
        "email address": re.compile(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "GitHub token": re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})"),
        "AWS access key": re.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}"),
        "OpenAI key": re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{40,}"),
        "personal filesystem path": re.compile(r"[A-Za-z]:[\\/]Users[\\/]|/" + r"home/[^/\s]+/"),
        "credential-bearing URL": re.compile(
            r"(?:https?|postgresql(?:\+psycopg)?):\/\/[^\s:/]+:([^\s@]+)@"
        ),
    }
    failures = []
    local_env = Path(".env")
    local_secrets = []
    if local_env.exists():
        for line in local_env.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and any(
                word in line.split("=", 1)[0] for word in ("PASSWORD", "TOKEN", "KEY")
            ):
                value = line.split("=", 1)[1].strip()
                if value and "REPLACE_" not in value:
                    local_secrets.append(value)

    def scan(filename: str, content: str) -> None:
        if any(secret in content for secret in local_secrets):
            failures.append(f"{filename}: local environment secret")
        for label, pattern in patterns.items():
            matches = list(pattern.finditer(content))
            if label == "email address":
                matches = [
                    m
                    for m in matches
                    if not re.fullmatch(r"(?:[0-9]+\+)?[\w-]+@users\.noreply\.github\.com", m[0])
                ]
            if label == "credential-bearing URL":
                matches = [
                    m
                    for m in matches
                    if m[1] not in {"disposable-ci-only"}
                    and not any(marker in m[1] for marker in ("${", "REPLACE_", "PASSWORD"))
                ]
            if matches:
                failures.append(f"{filename}: {label}")

    for filename in sorted(set(files) - {""}):
        path = Path(filename)
        if (
            path.name == ".env"
            or path.name.startswith(".env.")
            and path.name != ".env.example"
            or path.suffix in {".csv", ".parquet", ".joblib", ".pem", ".db"}
            or any(part in {"node_modules", ".venv", "artifacts", "data"} for part in path.parts)
        ):
            failures.append(f"{filename}: prohibited commit candidate")
        try:
            scan(filename, path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            failures.append(f"{filename}: binary candidate requires explicit privacy review")
    revisions = []
    if args.history:
        revisions = subprocess.check_output(["git", "rev-list", "HEAD"]).decode().splitlines()
        seen = set()
        for revision in revisions:
            identities = (
                subprocess.check_output(["git", "show", "-s", "--format=%ae%n%ce", revision])
                .decode()
                .splitlines()
            )
            if any(not i.endswith("@users.noreply.github.com") for i in identities):
                failures.append(f"{revision}: non-noreply Git identity")
            for item in (
                subprocess.check_output(["git", "ls-tree", "-r", revision]).decode().splitlines()
            ):
                meta, filename = item.split("\t", 1)
                blob = meta.split()[-1]
                if blob in seen:
                    continue
                seen.add(blob)
                content = subprocess.check_output(["git", "cat-file", "blob", blob])
                path = Path(filename)
                if path.name == ".env" or path.suffix in {
                    ".csv",
                    ".parquet",
                    ".joblib",
                    ".pem",
                    ".db",
                }:
                    failures.append(f"{revision}:{filename}: prohibited historical artifact")
                try:
                    scan(f"{revision}:{filename}", content.decode("utf-8"))
                except UnicodeDecodeError:
                    failures.append(
                        f"{revision}:{filename}: binary historical artifact requires review"
                    )
    if failures:
        raise SystemExit("Privacy review requires attention:\n" + "\n".join(failures))
    subprocess.run(["git", "diff", "--exit-code", "8e2029a", "--", "docs/specs"], check=True)
    locked = list(Path("docs/specs").glob("*.md"))
    if len(locked) != 4:
        raise SystemExit("Exactly four original locked specifications are required")
    for path in locked:
        original = subprocess.check_output(["git", "show", "8e2029a:" + path.as_posix()])
        if path.read_bytes() != original:
            raise SystemExit("Locked specification raw bytes changed: " + path.as_posix())
    ignored = subprocess.run(["git", "check-ignore", "-q", ".env"])
    if ignored.returncode:
        raise SystemExit(".env must be ignored")
    print(
        f"PASS: {len(set(files) - {''})} candidate files; {len(revisions)} historical commits; "
        "no detected private data or token patterns; "
        "locked specifications unchanged; .env ignored. Manual diff review is still required."
    )


if __name__ == "__main__":
    main()
