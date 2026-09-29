# Kontrakty i specyfikacje

| Temat | Dokument |
|---|---|
| HTTP API | [Mapa API](api.md), [listy i paginacja](api-list-contract.md) |
| Dane aplikacji | [Model danych](data-model.md), [workflow i role](business-workflows.md) |
| Dane syntetyczne | [Profile](data-profiles.md), [wymiary i kalendarz AI](retail-dimensions.md), [ceny/promocje AI](retail-pricing.md), [popyt/panel/koszyki AI](daily-demand.md), [chronologia/zwroty AI](retail-returns.md), [odbiór źródła i izolacja workera](source-acceptance.md), [kontrakty danych](data-contracts.md), [historyczne fixtures](source-compatibility-fixtures.md) |
| Streaming | [Zdarzenia](events.md), [trwałość metryk](live-metrics-persistence.md) |
| Eksport do AI | [Parquet i polityka artefaktów](parquet-artifacts.md), [niezmienne snapshoty](ai-snapshots.md), [handoff do repo AI](source-snapshot-handoff.md), [pełna bramka cross-repo](ai03-cross-repo.md) |
| Zapas AI 06 | [Kontrakt ledgeru, opening, replay i adapter legacy](inventory-ledger.md) |
| ML | [Kontrakt cech](ml-features.md), [lokalna polityka dopuszczenia RF](ml-admission-policy.md) |
| Konwencje | [Nazwy i tagi](conventions.md) |
| Terraform | [Mapa modułów](../guides/infrastructure.md), [backend state](terraform-state-backend.md) |
| Zależności kind | [Przypięte manifesty kindnet](kindnet-vendor.md) |

Schematy JSON, migracje i kod walidatorów są źródłami kontraktów wykonywanych
przez narzędzia. Dokumenty wyjaśniają ich użycie, nie kopiują wszystkich pól.
