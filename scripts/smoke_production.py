"""Real production-image same-origin reads, refresh/deep links and static boundaries."""

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from scripts.smoke_m3 import ROOT, run_call


def main() -> None:
    origin = ROOT.removesuffix("/api/v1")
    project = run_call("/projects")[0]
    pid = project["id"]
    runs = run_call(f"/projects/{pid}/runs")
    pages = [
        "/",
        "/projects",
        "/methodology",
        f"/projects/{pid}/setup/results",
        f"/projects/{pid}/overview",
        f"/projects/{pid}/trends",
    ]
    for run in runs:
        pages += [
            f"/runs/{run['id']}/{section}"
            for section in (
                "overview",
                "data",
                "features/f000",
                "performance",
                "calibration",
                "report",
            )
        ]
    for path in pages:
        with urlopen(origin + path, timeout=10) as response:
            html = response.read().decode()
            assert response.status == 200 and '<div id="root"></div>' in html
            assert response.headers["Content-Security-Policy"]
            assert response.headers["X-Request-ID"]
    for path in ("/api/v1/future-export", "/artifacts/demo/seed.json", "/docs", "/openapi.json"):
        try:
            urlopen(origin + path, timeout=10)
        except HTTPError as exc:
            assert exc.code == 403, (path, exc.code)
            assert exc.headers["Content-Type"].startswith("application/json")
        else:
            raise AssertionError("Private or unreviewed read admitted")
    for path in ("/", "/projects", "/assets/app.js"):
        for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"):
            try:
                urlopen(Request(origin + path, method=method), timeout=10)
            except HTTPError as exc:
                assert exc.code == 403
            else:
                raise AssertionError("Static route bypass admitted")
    assert (
        json.loads(urlopen(origin + "/api/v1/health/worker", timeout=10).read())["status"]
        == "NOT_REQUIRED"
    )
    print(
        f"PASS: production image {len(pages)} same-origin deep links; "
        "private paths and mutations denied"
    )


if __name__ == "__main__":
    main()
