"""Structural CI guard, paired with actionlint and actual local execution of its commands."""

import re
from pathlib import Path

import yaml


def main() -> None:
    data = yaml.load(Path(".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
    assert set(data["jobs"]) == {"backend", "postgres", "frontend", "system"}
    assert data["permissions"] == {"contents": "read"}
    assert data["env"]["MM_CODE_VERSION"] == "${{ github.sha }}"
    assert data["env"]["MM_CODE_DIRTY"] == "false"
    for name, job in data["jobs"].items():
        assert "timeout-minutes" in job
        for step in job["steps"]:
            if "uses" in step:
                assert re.fullmatch(r"[\w-]+/[\w-]+@[0-9a-f]{40}", step["uses"])
            assert "continue-on-error" not in step
        commands = "\n".join(step.get("run", "") for step in job["steps"])
        if name == "postgres":
            assert "--require-postgres" in commands and "alembic check" in commands
        if name == "system":
            assert set(job["needs"]) == {"backend", "postgres", "frontend"}
            assert "m7-gate.ps1" in commands
    print(
        "PASS: parsed CI jobs, immutable action revisions, "
        "PostgreSQL requirement and gate dependencies"
    )


if __name__ == "__main__":
    main()
