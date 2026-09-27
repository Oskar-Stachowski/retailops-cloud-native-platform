# Nazwy, wersje i tagi

## Infrastruktura

[`infra/modules/tags/main.tf`](../../infra/modules/tags/main.tf) jest źródłem
normalizacji nazw i tagów. Tworzy prefiks `<project>-<environment>`; poszczególne
moduły dodają własny sufiks zasobu. Sprawdzaj nazwę w planie, nie odtwarzaj jej
na podstawie przykładowego diagramu.

Wymagane tagi: `Project`, `Service`, `Environment`, `Owner`, `ManagedBy`,
`CostCenter`, `Lifecycle`. Wartości pochodzą z wejść modułu; nie wpisuj prywatnych
adresów ani identyfikatorów kont do przykładów. `additional_tags` są scalane
z zestawem domyślnym. Tag sam nie dowodzi, że zasób należy do wybranego state.

## Aplikacja i wydania

`VERSION` identyfikuje wersję platformy. Wersja API w OpenAPI i numer pakietu
frontendu są odrębnymi metadanymi. Zasady tagowania Git, OCI i wyboru digestu
określa [polityka wydań](../governance/releases.md).

Identyfikatory produktu, użytkownika i operacji przekazuj zgodnie z kontraktem
API. Nie zastępuj technicznego UUID przez SKU w kluczach powiązań. Zdarzenia
używają `event_id` do deduplikacji i `correlation_id` do powiązania sygnałów.

## Dokumentacja

Stosuj opisowe nazwy plików i względne odnośniki. Datę umieszczaj w nazwie
utrwalonego dowodu, nie twórz kolejnych wersji plików statusu. Miejsce i sposób
aktualizacji określa [instrukcja dokumentacji](../guides/documentation.md).
