"""Fixed reviewed UI interpretation templates. No scientific recomputation.

Kept outside immutable result artifacts: UI integration never rewrites M0–M5 facts.
Feature and prediction interpretations already come from their saved/read payloads.
"""

from typing import Any

TEMPLATES = {
    "data": {
        "may": (
            "Detected means statistical evidence of difference. "
            "Review magnitude and context separately."
        ),
        "cannot": (
            "Drift does not prove predictive degradation. "
            "NOT DETECTED does not prove populations are identical."
        ),
    },
    "confidence": {
        "may": (
            "The KS test measures evidence of a confidence distribution "
            "difference in these samples."
        ),
    },
    "performance": {
        "may": "These values describe predictive performance on the supplied labeled observations.",
    },
    "calibration": {
        "may": (
            "Compare empirical event frequencies with mean predicted probabilities "
            "in these samples."
        ),
    },
}


def interpretations(results: dict[str, Any]) -> dict[str, dict[str, str]]:
    return {
        "data": TEMPLATES["data"],
        "confidence": {**TEMPLATES["confidence"], "cannot": results["confidence"]["limitation"]},
        **(
            {
                key: {**TEMPLATES[key], "cannot": results[key]["limitation"]}
                for key in ("performance", "calibration")
            }
            if results["mode"] == "B"
            else {}
        ),
    }
