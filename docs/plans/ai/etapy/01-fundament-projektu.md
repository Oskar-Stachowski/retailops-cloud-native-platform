# 01 — Fundament projektu AI

**Etap odebrany 28.09.2026. Repozytoria: oba. Zależność: 00.**

Aktualny zakres to osobne repo AI z pakietem, settings/CLI, diagnostycznym HTTP,
telemetrią, PostgreSQL/pgvector, oddzielną bazą/rolą MLflow, migracjami i Compose,
wykonywalnymi kontraktami danych/run/tool oraz lokalną tożsamością i scope API.
[Dowody](../../../evidence/ai/01/README.md) rozdzielają lokalny macOS/ARM64
i zdalny Linux/AMD64. Required CI PR i push na main ma success w obu repo;
ochrona main wymaga PR, aktualności gałęzi i required-result także od administratora.

Lokalny auth używa prywatnej polityki ładowanej przy starcie; zmiana grants lub
revoked wymaga restartu. Forecast-check sprawdza uprawnienia, nie odczytuje modelu
ani danych. Compose nie montuje polityki aplikacji; MLflow ma izolację sieciową,
bez aplikacyjnego auth. Fundament nie obejmuje produkcyjnego IAM, importerów,
modeli, właściwego serving, RAG, agenta ani AWS.

Następna implementacja: **DATA-01 w [etapie 02](02-dane-sprzedazowe.md)**.
Równolegle dostępny jest [etap 11 — RAG](11-rag.md), począwszy od zatwierdzonego
korpusu i jego metadanych. Projektowanie [16A](16-aws.md) wymaga wcześniejszego
ustalenia infrastrukturalnego input contract. Bieżący zakres prac opisuje
[backlog](../backlog.md); wspólne reguły pozostają w [architekturze](../architektura.md)
i kontraktach.
