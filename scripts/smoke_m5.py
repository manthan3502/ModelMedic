"""Real mixed history and versioned derived outputs, with restart verification.

prepare retains only this script's synthetic project for verify / browser checks.
verify reopens persisted facts after service restart. cleanup removes that exact
project and its private artifact prefix. No user project is selected by name alone.
"""

import argparse
import json
import time
from hashlib import sha256
from urllib.error import HTTPError
from uuid import UUID

from sqlalchemy import select

from backend.app.core.config import Settings
from backend.app.db.models import MonitoringRun, Project, RunReport, SliceAnalysis
from backend.app.db.session import create_db
from backend.app.science.monitoring import MODE_A_LIMITATION
from backend.app.science.slices import INSUFFICIENT_SLICE, SLICE_LIMITATION
from backend.app.services.reporting import REPORT_FOOTER, REPORT_LIMITATIONS
from backend.app.storage.local import LocalArtifactStore
from scripts.smoke_m1 import call
from scripts.smoke_m3 import run_call, wait_run
from scripts.smoke_m4 import establish

STATE = "verification/m5-state.json"
NAME = "M5 synthetic acceptance"


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def wait_slice(run_id):
    for _ in range(240):
        analysis = run_call(f"/runs/{run_id}/slices")["analyses"][0]
        assert analysis["status"] != "FAILED", analysis["job"]
        if analysis["status"] == "READY":
            return analysis
        time.sleep(0.25)
    raise AssertionError("Slice worker did not finish within the smoke deadline")


def current(mode):
    groups = [""] * 10 + ["null"] * 29 + [" raw "] * 31 + ["raw"] * 50
    return (
        ("amount,segment," + ("target," if mode == "B" else "") + "excluded_id\n")
        + "".join(
            f"{'' if i % 10 == 0 else 1000 + i},{g},"
            + (f"class{i % 2}," if mode == "B" else "")
            + f"synthetic-secret-{i}\n"
            for i, g in enumerate(groups)
        )
    ).encode()


def prepare(store):
    if store.exists(STATE):
        raise AssertionError(
            "An M5 verification fixture already exists; verify / cleanup it first."
        )
    project_id, _ = establish(2, NAME)
    state = {"project_id": project_id, "runs": [], "slice_id": None}
    try:
        for i, mode in enumerate(("B", "A", "B"), 1):
            run = call(
                "/" + project_id + "/runs",
                "POST",
                {
                    "name": f"Synthetic {i} Mode {mode}",
                    "monitoring_date": f"2026-10-0{i}",
                    "notes": "M5 acceptance only",
                },
            )
            run_id = run["id"]
            state["runs"].append(run_id)
            run_call(
                f"/runs/{run_id}/upload", "POST", csv=iter([current(mode)[:80], current(mode)[80:]])
            )
            assert wait_run(run_id, "READY")["mode"] == mode
            run_call(f"/runs/{run_id}/analyze", "POST")
            wait_run(run_id, "ANALYZED")
        last = state["runs"][-1]
        before = run_call(f"/runs/{last}/report")["report"]
        queued = run_call(f"/runs/{last}/slices", "POST", {"feature_id": "f001"})
        assert (
            run_call(f"/runs/{last}/slices", "POST", {"feature_id": "f001"})["id"] == queued["id"]
        )
        ready = wait_slice(last)
        assert ready["id"] == queued["id"]
        state["slice_id"] = ready["id"]
        assert run_call(f"/runs/{last}/report")["report"] == before
        state["summary_hashes"] = [digest(run_call(f"/runs/{r}/summary")) for r in state["runs"]]
        state["report_hashes"] = [
            digest(run_call(f"/runs/{r}/report")["report"]) for r in state["runs"]
        ]
        state["slice_hash"] = digest(ready)
        store.put(STATE, json.dumps(state).encode())
        verify(store)
        print(
            f"PASS: M5 prepared synthetic B-A-B fixture {project_id}; "
            "retained for restart/browser verification",
            flush=True,
        )
    except BaseException:
        cleanup_state(state, store)
        raise


def verify(store):
    state = json.loads(store.get(STATE))
    project_id, run_ids = state["project_id"], state["runs"]
    assert call("/" + project_id)["name"] == NAME
    for i, run_id in enumerate(run_ids):
        summary = run_call(f"/runs/{run_id}/summary")
        report = run_call(f"/runs/{run_id}/report")["report"]
        assert digest(summary) == state["summary_hashes"][i]
        assert digest(report) == state["report_hashes"][i]
        assert report["report_template_version"] == "report-v1" and report["generated_at"]
        assert len(report["code_version"]) == 40
        assert len(report["sections"]) == 12 and report["footer"] == REPORT_FOOTER
        assert all(p in report["sections"][-1]["paragraphs"] for p in REPORT_LIMITATIONS)
        assert "synthetic-secret" not in json.dumps(report)
        if i == 1:
            assert all(
                MODE_A_LIMITATION in s["paragraphs"] and not s["tables"]
                for s in report["sections"][7:10]
            )
            assert run_call(f"/runs/{run_id}/slices")["status"] == "UNAVAILABLE"
            try:
                run_call(f"/runs/{run_id}/slices", "POST", {"feature_id": "f001"})
            except HTTPError as exc:
                assert exc.code == 409
            else:
                raise AssertionError("Mode A created slices")
        else:
            assert all(s["tables"] for s in report["sections"][7:10])
        for fid in ("f000", "f001"):
            feature = run_call(f"/runs/{run_id}/features/{fid}")
            assert "all valid baseline rows" in feature["interpretation"]["measured"]
            assert (
                feature["interpretation"]["cannot_conclude"]
                == "ModelMedic does not claim this feature change caused any change in performance."
            )
    last = run_ids[-1]
    slices = run_call(f"/runs/{last}/slices", "POST", {"feature_id": "f001"})
    assert slices["id"] == state["slice_id"] and digest(slices) == state["slice_hash"]
    assert slices["limitation"] == SLICE_LIMITATION
    assert slices["rows"][0]["is_overall"] and slices["rows"][0]["row_count"] == 120
    assert [r["slice_value"] for r in slices["rows"][1:]] == [None, " raw ", "null", "raw"]
    assert all(
        r["metrics"] == {} and r["reason"] == INSUFFICIENT_SLICE
        for r in slices["rows"]
        if r["row_count"] < 30
    )
    assert all(sum(r["class_support"].values()) == r["row_count"] for r in slices["rows"])
    base = f"/projects/{project_id}/trends"
    history = run_call(base + "?group=performance&signal=balanced_accuracy")
    assert [p["run_id"] for p in history["points"]] == run_ids
    assert [p["mode"] for p in history["points"]] == ["B", "A", "B"]
    assert history["points"][1]["value"] is None and history["points"][1]["reason"]
    assert history["points"][0]["value"] is not None and history["points"][2]["value"] is not None
    for group, signals in history["options"].items():
        for signal in signals:
            suffix = (
                "&feature_id=" + ("f001" if signal == "js" else "f000")
                if group == "data"
                else "&class_label=class0"
                if group == "predictions"
                else ""
            )
            selected = run_call(base + f"?group={group}&signal={signal}" + suffix)
            assert selected["group"] == group and selected["signal"] == signal
            if signal in {"ks", "js"}:
                assert selected["reference"] is None
    engine, sessions = create_db(Settings())
    with sessions() as session:
        for r, expected in zip(run_ids, state["summary_hashes"], strict=True):
            saved = session.get(MonitoringRun, UUID(r))
            assert digest(json.loads(store.get(saved.result_object_key))) == expected
            assert sha256(store.get(saved.result_object_key)).hexdigest() == saved.result_sha256
            assert session.get(RunReport, saved.id)
        assert (
            len(
                list(
                    session.scalars(select(SliceAnalysis).where(SliceAnalysis.run_id == UUID(last)))
                )
            )
            == 1
        )
    engine.dispose()
    print(
        "PASS: M5 stored feature diagnostics / slices / idempotence / all signal groups / "
        "B-A-B gap / reports / immutable hashes / reload",
        flush=True,
    )


def cleanup_state(state, store):
    for run_id in state["runs"]:
        run_call(f"/runs/{run_id}", "DELETE")
    engine, sessions = create_db(Settings())
    with sessions.begin() as session:
        project = session.get(Project, UUID(state["project_id"]))
        assert project and project.name == NAME
        session.delete(project)
    store.delete_prefix("projects/" + state["project_id"])
    store.delete(STATE)
    engine.dispose()
    print(
        "PASS: M5 exact synthetic project, runs, derived results and private artifacts cleaned",
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "verify", "cleanup"])
    args = parser.parse_args()
    store = LocalArtifactStore(Settings().artifact_root)
    if args.action == "prepare":
        prepare(store)
    elif args.action == "verify":
        verify(store)
    else:
        cleanup_state(json.loads(store.get(STATE)), store)


if __name__ == "__main__":
    main()
