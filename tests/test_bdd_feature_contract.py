"""Quality guardrails for human-readable BDD feature files."""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
FEATURES_DIR = REPO_ROOT / "features"

_LAYER_TAGS = {"@ui", "@pipeline", "@accessibility"}
_SCENARIO_RE = re.compile(r"^\s*Scenario:\s+", re.MULTILINE)


def _split_scenarios(feature_text: str) -> list[str]:
    parts = _SCENARIO_RE.split(feature_text)
    # First part is the feature header; remaining parts are scenario bodies.
    return parts[1:]


def test_feature_files_have_traceability_and_layer_tags() -> None:
    feature_files = sorted(FEATURES_DIR.glob("*.feature"))
    assert feature_files, "Expected at least one .feature file under features/"

    for feature_file in feature_files:
        text = feature_file.read_text(encoding="utf-8")

        assert "# Traceability:" in text, f"{feature_file.name} must include a Traceability block"
        assert "DEFINITION_OF_DONE.md" in text, (
            f"{feature_file.name} must reference DEFINITION_OF_DONE.md in its traceability block"
        )
        assert "FEATURES.md" in text, (
            f"{feature_file.name} must reference FEATURES.md in its traceability block"
        )

        tags = {token for token in re.findall(r"@[-\w]+", text)}
        assert tags & _LAYER_TAGS, (
            f"{feature_file.name} needs one layer tag from: {', '.join(sorted(_LAYER_TAGS))}"
        )


def test_each_scenario_is_readable_and_single_outcome() -> None:
    for feature_file in sorted(FEATURES_DIR.glob("*.feature")):
        text = feature_file.read_text(encoding="utf-8")
        scenarios = _split_scenarios(text)
        assert scenarios, f"{feature_file.name} must include at least one Scenario"
        has_background = bool(re.search(r"^\s*Background:\s*$", text, flags=re.MULTILINE))

        for scenario_body in scenarios:
            then_count = len(re.findall(r"^\s*Then\s+", scenario_body, flags=re.MULTILINE))
            given_count = len(re.findall(r"^\s*Given\s+", scenario_body, flags=re.MULTILINE))
            when_count = len(re.findall(r"^\s*When\s+", scenario_body, flags=re.MULTILINE))

            assert given_count >= 1 or has_background, (
                "Each scenario should have a Given step directly or via Background"
            )
            assert when_count == 1, "Each scenario should have exactly one When step"
            assert then_count == 1, "Each scenario should have exactly one Then step"
