# Karłowice-Różanka - 2027 - propozycja miasta

Równoległa do zestawu 2021 rekonstrukcja przestrzenna pięciu okręgów wyborczych dla Karłowic-Różanki, przygotowana na podstawie **propozycji miasta dla planowanych wyborów do Rad Osiedli Wrocławia w 2027 r.**

**Status:** propozycja miasta - nie ostatecznie uchwalony podział.

**Stan danych wskazany w tabeli źródłowej:** 30 czerwca 2026 r.

## Wyniki

- `geojson-2027-propozycja-miasta/karlowice-rozanka-okreg-1-2027-propozycja-miasta.geojson`
- `geojson-2027-propozycja-miasta/karlowice-rozanka-okreg-2-2027-propozycja-miasta.geojson`
- `geojson-2027-propozycja-miasta/karlowice-rozanka-okreg-3-2027-propozycja-miasta.geojson`
- `geojson-2027-propozycja-miasta/karlowice-rozanka-okreg-4-2027-propozycja-miasta.geojson`
- `geojson-2027-propozycja-miasta/karlowice-rozanka-okreg-5-2027-propozycja-miasta.geojson`
- `geojson-2027-propozycja-miasta/karlowice-rozanka-okregi-wyborcze-2027-propozycja-miasta.geojson`
- `pdf-2027-propozycja-miasta/Karlowice-Rozanka_okregi-wyborcze_2027-propozycja-miasta.pdf`

## Dane propozycji

| Okręg | Obwód | Mandaty | Mieszkańcy | Proponowana siedziba |
|---:|---:|---:|---:|---|
| 1 | 85 | 4 | 5824 | LO nr XIV, al. Aleksandra Brücknera 10 |
| 2 | 86 | 3 | 3663 | SP nr 83, ul. Stanisława Przybyszewskiego 59 |
| 3 | 87 | 3 | 4767 | SP nr 20, ul. Henryka Michała Kamieńskiego 24 |
| 4 | 88 | 6 | 8110 | LO nr X, ul. Piesza 1 |
| 5 | 89 | 5 | 6888 | SP nr 50, ul. Czeska 38 |

Razem: **21 mandatów, 29252 mieszkańców** według tabeli miasta.

## Walidacja wyniku

Końcowy przebieg generatora dla wersji **2027 - propozycja miasta**:

- bieżące punkty adresowe EMUiA w granicy osiedla: **3671**;
- dopasowane do reguł propozycji: **3670**;
- niedopasowany bieżący adres: **Sołtysowicka 9**;
- niejednoznaczne dopasowania reguł: **0**;
- działki przecinające osiedle: **4494**;
- działki z adresami więcej niż jednego okręgu: **20**, wszystkie rozdzielone wewnętrznie;
- punkty adresowe poza przypisanym okręgiem: **0**;
- pokrycie granicy osiedla: **100%**;
- luka: **0 m²**;
- nakładanie powierzchniowe: **0 m²**.

Przy bieżących danych SIP wynikowa geometria pięciu okręgów jest identyczna z geometrią rekonstrukcji 2021. Wersje różnią się jednak regułami źródłowymi, numerami obwodów, danymi o mieszkańcach i oznaczeniem statusu propozycji.

## Metoda

Metoda rekonstrukcji jest taka sama jak dla wersji 2021:
1. oficjalna granica osiedla z SIP Wrocławia;
2. miejskie punkty adresowe EMUiA;
3. reguły adresowe z propozycji miasta;
4. działki ewidencyjne jako podstawowa jednostka przestrzenna;
5. działki zawierające adresy różnych okręgów dzielone wewnętrznie według punktów adresowych;
6. walidacja pełnego pokrycia granicy osiedla i przynależności punktów adresowych.

Szczegółowy opis dokumentów źródłowych: `data-2027-propozycja-miasta/source-2027-propozycja-miasta/source-documents-2027-propozycja-miasta.md`.
