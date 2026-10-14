"""Private operator API client; no endpoint, model loading or fabricated science."""

import json
import os
import time
from collections.abc import Callable, Iterator
from typing import Any
from urllib.request import Request, urlopen

ROOT = (
    os.environ.get("MM_OPERATOR_ORIGIN", os.environ.get("MM_SMOKE_ORIGIN", "http://frontend:5173"))
    + "/api/v1"
)


def run_call(
    path: str, method: str = "GET", body: Any = None, csv: Iterator[bytes] | None = None
) -> Any:
    data = csv if csv is not None else json.dumps(body).encode() if body is not None else None
    request = Request(
        ROOT + path,
        data=data,
        method=method,
        headers={"Content-Type": "text/csv" if csv is not None else "application/json"},
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response) if response.status != 204 else None


def call(path: str = "", method: str = "GET", body: Any = None) -> Any:
    return run_call("/projects" + path, method, body)


def wait(path: str, predicate: Callable[[Any], bool]) -> Any:
    for _ in range(240):
        project = call(path)
        assert project["job"]["state"] != "FAILED", "Synthetic seed job failed"
        if predicate(project):
            return project
        time.sleep(0.5)
    raise RuntimeError("Synthetic seed worker deadline exceeded")


def wait_run(run_id: str, state: str) -> Any:
    for _ in range(240):
        run = run_call("/runs/" + run_id)
        assert not run["job"] or run["job"]["state"] != "FAILED", "Synthetic run job failed"
        assert run["state"] != "VALIDATION_FAILED", "Synthetic run validation failed"
        if run["state"] == state:
            return run
        time.sleep(0.25)
    raise RuntimeError("Synthetic run worker deadline exceeded")
