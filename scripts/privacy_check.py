"""Review commit candidates without printing secret values. Not a general secret scanner."""

import re
import subprocess
from pathlib import Path


def main() -> None:
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
    for filename in sorted(set(files) - {""}):
        path = Path(filename)
        if (
            path.name == ".env"
            or path.suffix in {".csv", ".parquet", ".joblib", ".pem", ".db"}
            or any(part in {"node_modules", ".venv", "artifacts", "data"} for part in path.parts)
        ):
            failures.append(f"{filename}: prohibited commit candidate")
        content = path.read_text(encoding="utf-8")
        if any(secret in content for secret in local_secrets):
            failures.append(f"{filename}: local environment secret")
        for label, pattern in patterns.items():
            if pattern.search(content):
                failures.append(f"{filename}: {label}")
    if failures:
        raise SystemExit("Privacy review requires attention:\n" + "\n".join(failures))
    subprocess.run(["git", "diff", "--exit-code", "8e2029a", "--", "docs/specs"], check=True)
    ignored = subprocess.run(["git", "check-ignore", "-q", ".env"])
    if ignored.returncode:
        raise SystemExit(".env must be ignored")
    print(
        f"PASS: {len(set(files) - {''})} candidate files; "
        "no detected private data or token patterns; "
        "locked specifications unchanged; .env ignored. Manual diff review is still required."
    )


if __name__ == "__main__":
    main()
