"""External read-only verification; repeat after restart with the same synthetic snapshot."""

import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

# Support the documented direct-file command as well as module invocation.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origin")
    parser.add_argument("--snapshot", type=Path, default=Path(".cache/public-demo-smoke.json"))
    args = parser.parse_args()
    parsed = urlsplit(args.origin)
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
    ):
        raise SystemExit("Provide the actual public HTTPS origin without credentials or paths")
    origin = args.origin.rstrip("/")

    def get(path):
        with urlopen(origin + "/api/v1" + path, timeout=30) as response:
            assert response.headers["X-Request-ID"]
            return json.load(response)

    assert get("/runtime")["deployment_mode"] == "DEMO_MODE"
    assert get("/health/ready")["status"] == "ready"
    assert get("/health/worker")["status"] == "NOT_REQUIRED"
    projects = get("/projects")
    assert len(projects) == 1
    pid = projects[0]["id"]
    assert projects[0]["baseline"]["status"] == "ESTABLISHED"
    runs = get(f"/projects/{pid}/runs")
    assert [r["mode"] for r in runs] == ["B", "A", "B"]
    paths = [
        "/",
        "/projects",
        "/methodology",
        f"/projects/{pid}/setup/results",
        f"/projects/{pid}/overview",
        f"/projects/{pid}/trends",
    ]
    hashes = {}
    for section in ("summary", "metrics", "calibration", "importance"):
        assert get(f"/projects/{pid}/baseline/{section}")
    history = get(f"/projects/{pid}/trends?group=performance&signal=balanced_accuracy")
    assert history["points"][1]["value"] is None
    for run in runs:
        rid = run["id"]
        for section in (
            "summary",
            "features/f000",
            "metrics",
            "calibration",
            "errors",
            "slices",
            "report",
        ):
            data = get(f"/runs/{rid}/{section}")
            assert data
            if section in {"summary", "report"}:
                hashes[f"{rid}/{section}"] = sha256(
                    json.dumps(data, sort_keys=True).encode()
                ).hexdigest()
        paths += [
            f"/runs/{rid}/{section}"
            for section in (
                "overview",
                "data",
                "features/f000",
                "performance",
                "calibration",
                "report",
            )
        ]
    for path in paths:
        with urlopen(origin + path, timeout=30) as response:
            assert response.status == 200 and '<div id="root"></div>' in response.read().decode()
    from backend.app.core.config import Settings
    from backend.app.main import create_app

    app = create_app(
        Settings(
            database_url="postgresql+psycopg://unused/unused",
            environment="local",
            deployment_mode="full",
            artifact_backend="local",
            artifact_root=Path(".cache/public-route-enumeration"),
            frontend_root=None,
        )
    )
    slice_id = get(f"/runs/{runs[0]['id']}/slices")["analyses"][0]["id"]
    denied = 0
    for path in app.openapi()["paths"]:
        path = path.replace("{project_id}", pid).replace("{run_id}", runs[0]["id"])
        path = path.replace("{job_id}", runs[0]["job"]["id"]).replace("{slice_id}", slice_id)
        path = path.replace("{section}", "summary").replace("{feature_id}", "f000")
        for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"):
            try:
                urlopen(Request(origin + path, method=method), timeout=30)
            except HTTPError as exc:
                assert exc.code == 403, (path, method, exc.code)
                assert exc.headers["X-Request-ID"]
            else:
                raise AssertionError("Public mutation admitted")
            denied += 1
    snapshot = args.snapshot.resolve()
    if not snapshot.is_relative_to(Path.cwd().resolve()):
        raise SystemExit("Keep the synthetic verification snapshot inside the repository cache")
    if snapshot.exists():
        assert json.loads(snapshot.read_text()) == hashes, "Persisted public outputs changed"
    else:
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_text(json.dumps(hashes, sort_keys=True), encoding="utf-8")
    print(
        f"PASS: public HTTPS UI/deep links, B-A-B gap, {denied} denied pairs "
        "and persisted fingerprints"
    )


if __name__ == "__main__":
    main()
