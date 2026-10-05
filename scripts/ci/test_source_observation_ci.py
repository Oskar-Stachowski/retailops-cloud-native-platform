# ruff: noqa: INP001, PT027
"""Keep real publisher durability required, covered once and exported as evidence."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REASON = "source_observation_required_ci_bypassed"


def validate(document: str) -> None:
    marker = "      - name: Verify checkpoint, approved head and suggestion durability before broad regression"
    if marker not in document:
        raise ValueError(REASON)
    early = document.split(marker, 1)[1].split("      - name:", 1)[0]
    if (
        'REQUIRE_BROKER_TESTS: "1"' not in early
        or "tests/test_source_observation_durability.py" not in early
    ):
        raise ValueError(REASON)
    required = (
        'REQUIRE_BROKER_TESTS: "1"',
        'SOURCE_OBSERVATION_OUTBOX_REPORT: "../../ci-cd/reports/api/source-observation-outbox.json"',
        "            tests/test_source_observation_durability.py \\",
        "            --ignore=tests/test_source_observation_durability.py \\",
        "            ci-cd/reports/api/source-observation-outbox.json",
        "            --cov=app --cov-branch --cov-report= --cov-fail-under=0",
        "            --cov-append \\",
    )
    if any(item not in document for item in required):
        msg = "source_observation_required_ci_bypassed"
        raise ValueError(msg)


class ObservationCIContract(unittest.TestCase):
    def test_required_real_gate_and_evidence(self) -> None:
        validate((ROOT / ".github/workflows/api-ci.yml").read_text())

    def test_each_bypass_is_refused(self) -> None:
        document = (ROOT / ".github/workflows/api-ci.yml").read_text()
        for token in (
            'REQUIRE_BROKER_TESTS: "1"',
            'SOURCE_OBSERVATION_OUTBOX_REPORT: "../../ci-cd/reports/api/source-observation-outbox.json"',
            "            tests/test_source_observation_durability.py \\",
            "            --ignore=tests/test_source_observation_durability.py \\",
            "            ci-cd/reports/api/source-observation-outbox.json",
            "            --cov=app --cov-branch --cov-report= --cov-fail-under=0",
            "            --cov-append \\",
        ):
            with (
                self.subTest(token=token),
                self.assertRaisesRegex(ValueError, "required_ci_bypassed"),
            ):
                validate(document.replace(token, ""))


if __name__ == "__main__":
    unittest.main()
