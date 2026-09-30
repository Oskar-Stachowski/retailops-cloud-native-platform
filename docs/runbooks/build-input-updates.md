# Aktualizacja wejść builda i CI

Zewnętrzne Actions w `.github/` używają pełnych SHA. Bazy Dockerfile oraz
zewnętrzne obrazy Compose, Kubernetes i narzędzi CI używają `tag@sha256:…`.
Tag opisuje linię wersji; o pobranej zawartości decyduje digest.
[GitHub](https://docs.github.com/en/actions/reference/security/secure-use#using-third-party-actions)
opisuje przypinanie Actions do commitów, a
[Docker](https://docs.docker.com/build/building/best-practices/#pin-base-image-versions)
przypinanie baz do digestów.

## Zwykła aktualizacja

1. Użyj PR Dependabota albo utwórz branch z aktualnego `main`. Dependabot
   sprawdza Actions co tydzień, a Dockerfile i Compose co miesiąc. Obejmuje
   również izolowane konfiguracje `scripts/db` i `scripts/release`.
2. Zweryfikuj SHA w repozytorium dostawcy. Dla tagu anotowanego wybierz commit
   wskazany przez `^{}`, nie obiekt tagu. Zachowaj komentarz z wersją Action.

```bash
git ls-remote --tags https://github.com/actions/checkout.git \
  refs/tags/v6 'refs/tags/v6^{}'
docker buildx imagetools inspect python:3.11-slim --format '{{json .Manifest}}'
```

3. Dla obrazu wybierz digest indeksu wieloplatformowego z właściwego rejestru.
   Sprawdź `linux/amd64` i `linux/arm64` dla obrazów używanych na obu platformach.
   Zachowaj obecne linie Python 3.11 i Node 22. Zmiana głównej wersji wymaga
   oddzielnego sprawdzenia zgodności.
4. Obrazy wpisane w poleceniach workflow oraz stała skanera w `registry.py`
   mają ręczną aktualizację w tym samym trybie PR. Zaktualizuj wszystkie
   użycia zmienianego obrazu, w tym cache infrastruktury kind i testy awarii.
5. Uruchom kontrole poniżej i zacommituj kod. Build wydania eksportuje kod
   z Git; nie używa niezacommitowanych zmian Dockerfile.

```bash
python3 scripts/ci/test_immutable_inputs.py
python3 scripts/ci/check_immutable_inputs.py --output ci-cd/reports/immutable-inputs.json
make release-tests
make compose-config compose-profile-config
make release-build
```

Required CI dodatkowo sprawdza workflow, obrazy, pełny Compose oraz restart
i rollback w kind. Scalaj przez chroniony PR po zaliczeniu `required-result`.
Aktualizacja zależności nie uruchamia automatycznie publikacji wersji.

## Dowód builda i wydania

Builder używa Buildx z metadanymi BuildKit. Każdy obraz ma `build_inputs`:
deklaracje `FROM`, rzeczywiste materials i platformę, sumy Dockerfile,
`.dockerignore` i plików zależności oraz digest wyniku. Osobny plik
`<source-sha>-<component>-build.json` ma sumę zapisaną w manifeście.
Raport zawiera również pełne referencje Actions i sumy plików harnessu.

Publikowany manifest v3 i podpisany pakiet dowodów zachowują te dane.
Publikacja odrzuca kandydata z bazą bez digestu, brakujący receipt lub
zmienione metadane. Import porównuje sumy wejść z kodem właściwego commita.
Starszy poprzednik może deklarować tag: jego rzeczywiście użyty digest
zapisuje BuildKit. Nie zmieniaj historycznego commita ani dawnego receipt.

Kontrola dopuszcza lokalne nazwy aplikacji budowanych z tego checkoutu,
referencje aplikacji wybierane z manifestu oraz aliasy etapów Dockerfile.
To nie są pobierane zewnętrzne zależności. Wydanie wybiera zweryfikowane image
IDs/digesty zgodnie z [polityką wydań](../governance/releases.md).

Przypięcie obrazów i Actions nie gwarantuje identycznych bajtów przyszłego
builda: instalacja pakietów systemowych i metadane builda mają własną zmienność.
Rollback używa zachowanego artefaktu. Procedurę publikacji opisuje
[runbook rejestru](registry-release.md), a pomiar OPS-06
[raport odbioru](../evidence/ops/06/README.md).
