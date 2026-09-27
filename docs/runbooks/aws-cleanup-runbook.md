# Zakończenie eksperymentu AWS

Procedura dotyczy zasobów utworzonych dla konkretnego eksperymentu RetailOps.
Jej zakres wynika z rzeczywistego inventory i autorytatywnego state, a nie ze
starego planu lub samych nazw. [Ostatni zapisany przegląd AWS](../evidence/aws/2026-09-26-state-drift.md)
określa punkt odniesienia; przed cleanup wykonaj nowy odczyt.

## 1. Ustal zasoby i własność

W prywatnej sesji wybierz właściwy profil i ustaw `TF_EXPECTED_ACCOUNT_ID`,
a następnie z katalogu repozytorium uruchom:

```bash
python3 scripts/terraform/inventory.py
```

Sprawdź `status` i każdy wynik. `partial` lub `unverified` nie oznacza braku
zasobów. Skrypt obejmuje nazwy/tagi RetailOps w `eu-central-1` i metadane IAM/S3
całego konta; nie jest pełnym audytem wszystkich regionów i zasobów bez tagów.

Porównaj wynik z listą zasobów eksperymentu i jego stanem Terraform. Określ
oddzielnie zasoby do usunięcia i do zachowania. Backend S3/KMS oraz jego state
bootstrapu mają trwały lifecycle. Zachowaj rolę GitHub do planowania, jeśli
pozostaje potrzebna; nie należy do pustego dev state opisanego w dowodzie.
Zasoby niezwiązane z eksperymentem pozostają poza cleanup.

## 2. Przygotuj plan usunięcia

Użyj checkoutu, backendu, workspace i prywatnych parametrów rzeczywistego
wdrożenia. Jeśli state zaginął, najpierw wykonaj
[procedurę odzyskania](terraform-remote-state.md). Nie inicjalizuj pustego stanu
ani nie używaj historycznego `tfplan` jako zamiennika.

Zatrzymaj równoległe zmiany. Zabezpiecz prywatną kopię stanu i potrzebne dane,
zachowaj wymagane artefakty wydania. Ustaw poniższe zmienne na sprawdzone ścieżki:
`RETAILOPS_TF_ROOT` — root deploymentu, `RETAILOPS_TF_VARS` — absolutna ścieżka
jego pliku parametrów, `RETAILOPS_DESTROY_PLAN` — prywatny plik planu poza Git.

```bash
umask 077
terraform -chdir="$RETAILOPS_TF_ROOT" plan -destroy \
  -var-file="$RETAILOPS_TF_VARS" -out="$RETAILOPS_DESTROY_PLAN"
terraform -chdir="$RETAILOPS_TF_ROOT" show "$RETAILOPS_DESTROY_PLAN"
```

Przejrzyj każdy zasób oraz zależności. Plan nie może obejmować backendu stanu,
utrzymywanych danych, cudzych zasobów ani infrastruktury, której właściciela
nie ustalono. Zawartość ECR, zależne interfejsy sieciowe i zasoby utworzone
przez kontrolery mogą wymagać osobnego, dokładnie określonego cleanup.

## 3. Zastosuj przejrzany plan

Po potwierdzeniu zakresu usunięcia wykonaj dokładnie zapisany plan, używając
tożsamości operatora uprawnionej do tej operacji:

```bash
terraform -chdir="$RETAILOPS_TF_ROOT" apply "$RETAILOPS_DESTROY_PLAN"
```

Przy błędzie zachowaj state i ustal pozostałe zasoby. Nie usuwaj ich ze state
tylko po to, by uzyskać pustą listę. Nie wyłączaj `prevent_destroy` trwałego
backendu w ramach rutynowego zakończenia eksperymentu.

## 4. Potwierdź zakończenie

Sprawdź stan deploymentu, ponów inventory i porównaj z planowaną listą.
Zweryfikuj także dodatkowe regiony/usługi, jeżeli używał ich eksperyment.
Pusty state nie dowodzi braku osieroconych zasobów; plan pokazujący ponowne
tworzenie z istniejącej konfiguracji nie oznacza, że cleanup się nie powiódł.

Zapisz datę UTC, commit, zakres, wynik usunięcia, potwierdzone pozostałości
i uzasadnienie każdego zachowanego zasobu. Publikuj jedynie zredagowany raport
zgodnie z [zasadami dowodów](../evidence/README.md). Po odświeżeniu danych
rozliczeniowych sprawdź koszty pozostałych usług; odczyt inventory nie zastępuje
kontroli rozliczeń.
