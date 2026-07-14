# ruff: noqa: INP001, PT009
import unittest

from detect_required_ci_changes import GATE_FIELDS, classify_paths


class RequiredCIPathDetectionTests(unittest.TestCase):
    def assert_gates(self, paths: list[str], expected: set[str]) -> None:
        decision = classify_paths(paths)
        actual = {name for name in GATE_FIELDS if getattr(decision, name)}
        self.assertEqual(expected, actual)

    def test_api_change(self) -> None:
        self.assert_gates(
            ["services/api/app/main.py"],
            {"api", "docker", "security"},
        )

    def test_frontend_change(self) -> None:
        self.assert_gates(
            ["frontend/src/App.jsx"],
            {"frontend", "docker", "security"},
        )

    def test_docker_compose_change(self) -> None:
        for path in ("docker-compose.yml", "compose.yaml", "images/api/Dockerfile"):
            with self.subTest(path=path):
                self.assert_gates([path], {"docker", "security"})

    def test_terraform_change(self) -> None:
        self.assert_gates(["infra/modules/vpc/main.tf"], {"terraform"})

    def test_kubernetes_change(self) -> None:
        self.assert_gates(
            ["k8s/base/api/deployment.yaml"],
            {"kubernetes", "security"},
        )

    def test_kubernetes_security_config_change(self) -> None:
        self.assert_gates(
            ["security/k8s/checkov.yml"],
            {"kubernetes", "security"},
        )

    def test_policy_change(self) -> None:
        decision = classify_paths(["policy/conftest/kubernetes.rego"])
        self.assertTrue(decision.policy)
        self.assert_gates(
            ["policy/conftest/kubernetes.rego"],
            {"kubernetes", "security"},
        )

    def test_docs_only_change(self) -> None:
        decision = classify_paths(["docs/runbooks/example.md", "README.md"])
        self.assertTrue(decision.docs_only)
        self.assert_gates(["docs/runbooks/example.md", "README.md"], set())

    def test_mixed_change_uses_union(self) -> None:
        self.assert_gates(
            ["services/api/app/main.py", "infra/modules/vpc/main.tf"],
            {"api", "docker", "security", "terraform"},
        )

    def test_cross_area_rename_uses_old_and_new_paths(self) -> None:
        self.assert_gates(
            ["services/api/app/legacy.py", "docs/legacy-api.md"],
            {"api", "docker", "security"},
        )

    def test_shared_change_runs_every_gate(self) -> None:
        decision = classify_paths(["Makefile"])
        self.assertTrue(decision.shared)
        self.assert_gates(["Makefile"], set(GATE_FIELDS))

    def test_unknown_change_runs_every_gate(self) -> None:
        decision = classify_paths(["tools/new-helper.sh"])
        self.assertTrue(decision.unknown)
        self.assert_gates(["tools/new-helper.sh"], set(GATE_FIELDS))

    def test_data_change_runs_data_api_docker_and_security(self) -> None:
        self.assert_gates(
            ["data/contracts/retailops_seed_dataset.contract.json"],
            {"api", "data", "docker", "security"},
        )

    def test_empty_or_manual_input_runs_every_gate(self) -> None:
        self.assert_gates([], set(GATE_FIELDS))
        decision = classify_paths(["docs/README.md"], force_all=True)
        actual = {name for name in GATE_FIELDS if getattr(decision, name)}
        self.assertEqual(set(GATE_FIELDS), actual)


if __name__ == "__main__":
    unittest.main()
