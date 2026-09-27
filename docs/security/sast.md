# Analiza statyczna kodu

| Kontrola | Zakres wykonywany przez Make i API CI | Wynik |
|---|---|---|
| Ruff | `services/api/app`, `scripts`, `tests`, `data`, `ml`; lint i format | Wyjście polecenia / log CI |
| mypy | Zakres określony w `pyproject.toml` | Log kontroli typów |
| Bandit | `services/api/app` i `services/api/scripts`; high severity i high confidence | `ci-cd/reports/security/bandit-api.txt` |

```bash
make api-lint api-format-check api-type-check api-security-lint
```

Źródła wykonywanych kontroli: [Makefile](../../Makefile) i
[API CI](../../.github/workflows/api-ci.yml).

[`security/sast/semgrep.yml`](../../security/sast/semgrep.yml) zawiera reguły do
opcjonalnej kontroli ręcznej. Semgrep nie jest obecnie wykonywany przez Required
CI ani `make api-security-lint`. Po zainstalowaniu go w osobnym środowisku:

```bash
mkdir -p ci-cd/reports/security
semgrep scan --config security/sast/semgrep.yml --json --output ci-cd/reports/security/semgrep.json
```

Raport ręczny nie zastępuje wyniku wymaganych kontroli.
