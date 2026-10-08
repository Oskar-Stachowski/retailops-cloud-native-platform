# Karta danych AI 06

Syntetyczne dane, seed 42, koniec sprzedaży 2026-07-31; brak danych klientów.
Profile: smoke 30 dni/20 produktów/3 sklepy/2 magazyny; temporal 102 dni/8 produktów/3 sklepy/2 magazyny.
Source 2.7: 58 tabel; snapshot i curated 1.1: 43 facts/plans. 12 truth tables
oraz kwalifikacja okien są osobnym wejściem ewaluatora. Target downstream
forecastu to obserwowana sprzedaż ograniczona dostępnością, nie latent demand.

### ai-smoke

- Source: `source-sha256-70f155b79f449d9b7be6c3798dba839383a02b9afd50bd19d98bb1ff283b666a`
- Qualification: `inventory-labels-sha256-6084d3465a9841df163efa80a92412b5a63c05a01c60cde01af7a7a337219d0c`
- Snapshot: `snapshot-sha256-10ebfa41adc95966a785876565c3fa391006726184975b0d4d823fe2d083d6a4`
- Curated: `curated-sha256-4f3457a8557879ccfe8263d7f4080e9eb24d3ed009c4b605ab286add27bfc0bb`

### ai-temporal-smoke

- Source: `source-sha256-d76d0942c703ceaefd9fde5c921560886fe9b8c833693ee32eb12eb594b8867f`
- Qualification: `inventory-labels-sha256-a697f24ab5c735e49557fe901b620e341cb936403c755608fdf5e4b018c3ef12`
- Snapshot: `snapshot-sha256-f36775eed4a0a6df8be8e8baa17821324b072f647330547dffa6747e3e1edce3`
- Curated: `curated-sha256-a23ae90c556a0c69e808fcbb886a137ee1f5fc1316e41eecda963f3d540df5f6`

[Końcowy odbiór](README.md) definiuje lineage, budżet, gotowość i ograniczenia.
Okna already-stockout/inactive/missing/immature pozostają bez labelu.
Obsługa źródła nie kwalifikuje modelu 08 ani podziałów train/validation/test.
Nowe IDs wymagają własnej oceny 04/05 przed wykorzystaniem prognoz w 07/08.
