# Polityki Kubernetes

| Źródło | Zastosowanie |
|---|---|
| `policy/conftest/` | Obowiązująca kontrola renderowanych manifestów w CI i lokalnie |
| `policy/kyverno/` | Definicje do przyszłego wdrożenia admission z Kyverno |
| `policy/gatekeeper/` | Definicje do przyszłego wdrożenia admission z Gatekeeper |

Obsługiwana ścieżka z katalogu głównego:

```bash
make k8s-policy
```

Cel renderuje base i dev i sprawdza wynik Conftestem. Dla pełnych kontroli,
w tym schematów i Checkov, wykonaj `make k8s-ci`.
Wymagane narzędzia i runtime: [Kubernetes](../guides/kubernetes.md).

Polityki odrzucają m.in. `latest`, brak wymaganych probes/resources i eskalację
uprawnień. Manifesty źródłowe nie mogą zawierać sekretów runtime. Dev używa
Kustomize secretGenerator z ignorowanego pliku
`k8s/overlays/dev/secrets/runtime-secrets.env`; dopuszczenie wygenerowanego Secret
wymaga adnotacji `retailops.io/generated-by: kustomize-secretGenerator` oraz
`retailops.io/secret-source: uncommitted-local-env`.

Raporty powstają w `ci-cd/reports/k8s/`. Wyjątki skanowania opisuje
[polityka bezpieczeństwa](controls.md). Obecność manifestów Kyverno/Gatekeeper
nie oznacza działającego kontrolera admission ani wymuszania podpisów obrazów.
