# Karłowice–Różanka — okręgi wyborcze Rad Osiedli 2021

Repozytorium zawiera przestrzenną rekonstrukcję pięciu okręgów wyborczych osiedla **Karłowice–Różanka** użytych w wyborach do Rad Osiedli Wrocławia w 2021 r.

Miasto opublikowało wykazy ulic i numerów adresowych przypisanych do okręgów, ale nie opublikowało gotowych poligonów tych okręgów. Geometrie w tym repozytorium są więc **rekonstrukcją**, a nie urzędowym zbiorem granic okręgów.

## Status i walidacja

Ostatnia rekonstrukcja została wykonana na publicznych danych SIP Wrocławia i przeszła walidację topologiczną oraz adresową:

- **3670** bieżących punktów adresowych EMUiA pasuje do reguł adresowych opublikowanych dla wyborów w 2021 r.;
- **0** dopasowanych punktów adresowych znajduje się poza poligonem swojego okręgu;
- **4494** działki ewidencyjne przecinają granicę osiedla i zostały użyte jako podstawowa siatka przestrzenna;
- **20** działek zawiera punkty adresowe należące do więcej niż jednego okręgu — wszystkie zostały rozdzielone wewnętrznie według najbliższych punktów adresowych, zamiast przypisywania całej działki jednemu okręgowi;
- pokrycie oficjalnej granicy osiedla przez pięć okręgów: **100%**;
- luka pomiędzy okręgami a granicą osiedla: **0 m²**;
- nakładanie się powierzchni okręgów: **0 m²**;
- wszystkie pięć geometrii przechodzi test poprawności geometrii.

Jeden bieżący punkt EMUiA położony w granicy osiedla — **Sołtysowicka 9** — nie mieści się w opublikowanym wykazie adresowym żadnego z pięciu okręgów z 2021 r. Nie jest używany jako punkt kotwiczący rekonstrukcji. Generator zapisuje ten przypadek w `data-2021/generated-2021/validation-2021.json`.

| Okręg | Dopasowane punkty adresowe | Powierzchnia |
|---:|---:|---:|
| 1 | 1107 | 2,352 km² |
| 2 | 447 | 1,420 km² |
| 3 | 923 | 1,598 km² |
| 4 | 475 | 3,613 km² |
| 5 | 718 | 2,110 km² |

## Konwencja nazw - 2021

Wszystkie katalogi i pliki wynikowe dotyczące tego zestawu mają w nazwie **2021**, aby nie mieszać ich z ewentualnymi rekonstrukcjami dla innych wyborów. Główne katalogi to `geojson-2021/`, `data-2021/`, `docs-2021/`, `scripts-2021/` i `pdf-2021/`.

## Wyniki

Po wykonaniu generatora w katalogu `geojson-2021/` znajdują się:

- `karlowice-rozanka-okreg-1-2021.geojson`
- `karlowice-rozanka-okreg-2-2021.geojson`
- `karlowice-rozanka-okreg-3-2021.geojson`
- `karlowice-rozanka-okreg-4-2021.geojson`
- `karlowice-rozanka-okreg-5-2021.geojson`
- `karlowice-rozanka-okregi-wyborcze-2021.geojson` — wszystkie pięć okręgów w jednym pliku
- `karlowice-rozanka-granica-osiedla-rekonstrukcja-2021.geojson` — oficjalna granica osiedla użyta jako maska

Wszystkie pliki GeoJSON wynikowe są w **WGS84 / EPSG:4326** i nadają się do bezpośredniego użycia na podkładzie OpenStreetMap, w Leaflet, MapLibre, QGIS itd. Dodatkowo katalog `pdf-2021/` zawiera sześciostronicowy dokument `Karlowice-Rozanka_okregi-wyborcze_2021.pdf`: na pierwszej stronie mapę pięciu okręgów, a na kolejnych stronach mapę każdego okręgu i adresy zgodne z ogłoszeniem z 2021 r.

## Źródła

### 1. Oficjalny podział wyborczy z 2021 r.

Urząd Miejski Wrocławia opublikował dla Karłowic–Różanki pięć okręgów, numery obwodów, lokale wyborcze oraz wykazy ulic i zakresów numerów:

- https://www.wroclaw.pl/dla-mieszkanca/karlowice-rozanka-kandydaci-na-radnych-2021
- https://www.wroclaw.pl/dla-mieszkanca/okregi-wyborcze-lokale-i-liczby-mandatow-wybory-rady-osiedla-2021
- PDF: https://www.wroclaw.pl/dla-mieszkanca/files/news/46863/Wybory_ro2021_Osiedla_zmiana_wykaz_okregow_obwodow_glosowania.pdf

Znormalizowany zapis reguł znajduje się w `data-2021/source-2021/okregi-wyborcze-2021.json`.

### 2. Oficjalna granica osiedla

Granice osiedli Wrocławia zostały jednoznacznie zdefiniowane uchwałą Rady Miejskiej Wrocławia nr XX/419/16 z 21 stycznia 2016 r. i są publikowane przez System Informacji Przestrzennej Wrocławia.

- opis: https://geoportal.wroclaw.pl/osiedla/
- warstwa ArcGIS REST: https://gis.um.wroc.pl/portal_srv/rest/services/search/MapServer/12

### 3. Punkty adresowe EMUiA

Do zakotwiczenia adresów z wykazu wyborczego używany jest miejski rejestr punktów adresowych EMUiA:

- https://gis.um.wroc.pl/portal_srv/rest/services/emuia_wroclaw/MapServer/0
- opis zasobu: https://geoportal.wroclaw.pl/zasoby/

### 4. Działki ewidencyjne

Granice terenów są prowadzone po geometrii działek ewidencyjnych publikowanych w SIP:

- https://gis.um.wroc.pl/portal_srv/rest/services/Dzia%C5%82ki/MapServer/0

SIP opisuje publiczne zbiory adresowe i granice osiedli jako dane dostępne do pobrania bez ograniczeń.

## Metoda rekonstrukcji

Generator `scripts-2021/build-districts-2021.py` wykonuje następujące kroki:

1. pobiera oficjalną granicę Karłowic–Różanki;
2. pobiera aktualne punkty adresowe EMUiA położone w tej granicy;
3. dopasowuje punkty adresowe do reguł wyborczych z 2021 r., uwzględniając zakresy numerów i parzystość;
4. pobiera działki ewidencyjne przecinające osiedle;
5. działki zawierające rozpoznane adresy traktuje jako twarde punkty kotwiczące danego okręgu;
6. jeżeli na jednej działce znajdują się adresy należące do więcej niż jednego okręgu, dzieli tę działkę wewnętrznie według komórek Voronoi liczonych od punktów adresowych w metrycznym układzie EPSG:2180; dzięki temu granica nie jest arbitralnie przypisana całej działce;
7. działki bez adresu wyborczego przypisuje przestrzennie do najbliższego rozpoznanego adresu (również w EPSG:2180), dzięki czemu parki, drogi, tereny usługowe i inne obszary bez mieszkańców dostają ciągłe przypisanie;
8. geometrię każdego okręgu scala, przycina do oficjalnej granicy osiedla i waliduje;
9. zapisuje raport walidacji, przypadki konfliktowe oraz punkty adresowe użyte do rekonstrukcji.

Takie podejście wykorzystuje działki jako podstawową jednostkę przestrzenną i nie próbuje wymyślać „wyborców” dla terenów bez adresów.

## Ważne ograniczenie historyczne

Wykaz wyborczy pochodzi z **2021 r.**, natomiast miejski SIP udostępnia bieżącą geometrię adresów i działek. Oznacza to, że:

- przypisanie mieszkańców do okręgów wynika z urzędowego wykazu z 2021 r.;
- geometria działek jest współczesnym podkładem służącym do rekonstrukcji;
- podziały/scalenia działek wykonane po 2021 r. mogą lokalnie zmieniać techniczny przebieg poligonu;
- pliki należy traktować jako możliwie wierną rekonstrukcję przestrzenną, nie jako urzędową mapę wyborczą.

## Walidacja

Po każdym uruchomieniu generator zapisuje:

- `data-2021/generated-2021/validation-2021.json` — statystyki i testy spójności,
- `data-2021/generated-2021/adresy-dopasowane-2021.geojson` — rozpoznane punkty adresowe z przypisanym okręgiem,
- `docs-2021/summary-2021.md` — czytelne podsumowanie.

Podstawowy warunek poprawności: każdy rozpoznany punkt adresowy z oficjalnego wykazu musi leżeć w poligonie odpowiadającego mu okręgu, a suma pięciu geometrii ma pokrywać granicę osiedla bez zamierzonych luk.

## Odtworzenie danych

Lokalnie:

```bash
python -m pip install -r requirements.txt
python scripts-2021/build-districts-2021.py
```

Repozytorium zawiera również workflow GitHub Actions. Po zmianie reguł lub generatora wynik może zostać odtworzony automatycznie z publicznych źródeł miejskich.

## Podgląd

`docs-2021/index-2021.html` ładuje pięć plików GeoJSON na podkładzie OpenStreetMap i pozwala szybko sprawdzić przebieg granic.

## Issues

Dla każdego z pięciu okręgów utworzono osobne issue z oficjalnym wykazem ulic/adresów, lokalem wyborczym, metodą i ścieżką pliku wynikowego. Po wygenerowaniu i zweryfikowaniu danych issues są uzupełniane raportem i zamykane.

## Status danych

Geometrie są produktem rekonstrukcji. Przy wykorzystaniu do analiz, publikacji lub dalszego przetwarzania należy zachować informację o tej metodzie i roku odniesienia (2021).
