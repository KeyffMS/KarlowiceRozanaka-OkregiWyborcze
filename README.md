# Karłowice–Różanka — okręgi wyborcze Rad Osiedli 2021

Repozytorium zawiera przestrzenną rekonstrukcję pięciu okręgów wyborczych osiedla **Karłowice–Różanka** użytych w wyborach do Rad Osiedli Wrocławia w 2021 r.

Miasto opublikowało wykazy ulic i numerów adresowych przypisanych do okręgów, ale nie opublikowało gotowych poligonów tych okręgów. Geometrie w tym repozytorium są więc **rekonstrukcją**, a nie urzędowym zbiorem granic okręgów.

## Wyniki

Po wykonaniu generatora w katalogu `geojson/` znajdują się:

- `okreg-1.geojson`
- `okreg-2.geojson`
- `okreg-3.geojson`
- `okreg-4.geojson`
- `okreg-5.geojson`
- `karlowice-rozanka-okregi-2021.geojson` — wszystkie pięć okręgów w jednym pliku
- `osiedle-karlowice-rozanka.geojson` — oficjalna granica osiedla użyta jako maska

Wszystkie pliki wynikowe są w **WGS84 / EPSG:4326** i nadają się do bezpośredniego użycia na podkładzie OpenStreetMap, w Leaflet, MapLibre, QGIS itd.

## Źródła

### 1. Oficjalny podział wyborczy z 2021 r.

Urząd Miejski Wrocławia opublikował dla Karłowic–Różanki pięć okręgów, numery obwodów, lokale wyborcze oraz wykazy ulic i zakresów numerów:

- https://www.wroclaw.pl/dla-mieszkanca/karlowice-rozanka-kandydaci-na-radnych-2021
- https://www.wroclaw.pl/dla-mieszkanca/okregi-wyborcze-lokale-i-liczby-mandatow-wybory-rady-osiedla-2021
- PDF: https://www.wroclaw.pl/dla-mieszkanca/files/news/46863/Wybory_ro2021_Osiedla_zmiana_wykaz_okregow_obwodow_glosowania.pdf

Znormalizowany zapis reguł znajduje się w `data/source/okregi-2021.json`.

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

Generator `scripts/build_districts.py` wykonuje następujące kroki:

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

- `data/generated/validation.json` — statystyki i testy spójności,
- `data/generated/addresses-2021-matched.geojson` — rozpoznane punkty adresowe z przypisanym okręgiem,
- `docs/summary.md` — czytelne podsumowanie.

Podstawowy warunek poprawności: każdy rozpoznany punkt adresowy z oficjalnego wykazu musi leżeć w poligonie odpowiadającego mu okręgu, a suma pięciu geometrii ma pokrywać granicę osiedla bez zamierzonych luk.

## Odtworzenie danych

Lokalnie:

```bash
python -m pip install -r requirements.txt
python scripts/build_districts.py
```

Repozytorium zawiera również workflow GitHub Actions. Po zmianie reguł lub generatora wynik może zostać odtworzony automatycznie z publicznych źródeł miejskich.

## Podgląd

`docs/index.html` ładuje pięć plików GeoJSON na podkładzie OpenStreetMap i pozwala szybko sprawdzić przebieg granic.

## Issues

Dla każdego z pięciu okręgów utworzono osobne issue z oficjalnym wykazem ulic/adresów, lokalem wyborczym, metodą i ścieżką pliku wynikowego. Po wygenerowaniu i zweryfikowaniu danych issues są uzupełniane raportem i zamykane.

## Status danych

Geometrie są produktem rekonstrukcji. Przy wykorzystaniu do analiz, publikacji lub dalszego przetwarzania należy zachować informację o tej metodzie i roku odniesienia (2021).
