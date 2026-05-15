# RetailOps SAST implementation

Implemented SAST controls:

| Tool | Scope | Evidence |
|---|---|---|
| Ruff | Python quality and safe refactors | `ci-cd/reports/ruff/*.txt` |
| Bandit | Python security linting | `ci-cd/reports/security/bandit-devsecops.json` |
| Semgrep | Project-specific source security rules | `ci-cd/reports/security/semgrep-devsecops.json` |

Local command:

```bash
python -m pip install bandit semgrep
bandit -r services/api/app services/api/scripts data/generator ml -f json -o ci-cd/reports/security/bandit-devsecops.json
semgrep scan --config security/sast/semgrep.yml --json --output ci-cd/reports/security/semgrep-devsecops.json
```
