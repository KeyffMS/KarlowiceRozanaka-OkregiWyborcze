#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests
from pyproj import Transformer
from shapely import make_valid
from shapely.geometry import GeometryCollection, MultiPoint, MultiPolygon, Point, Polygon, mapping, shape
from shapely.ops import transform, unary_union, voronoi_diagram
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "data" / "source" / "okregi-2021.json"
OUT_GEOJSON = ROOT / "geojson"
OUT_DATA = ROOT / "data" / "generated"
OUT_DOCS = ROOT / "docs"

BOUNDARY_URL = "https://gis.um.wroc.pl/portal_srv/rest/services/search/MapServer/12/query"
ADDRESS_URL = "https://gis.um.wroc.pl/portal_srv/rest/services/emuia_wroclaw/MapServer/0/query"
PARCEL_URL = "https://gis.um.wroc.pl/portal_srv/rest/services/Dzia%C5%82ki/MapServer/0/query"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "KarlowiceRozanaka-OkregiWyborcze/1.0 (+https://github.com/KeyffMS/KarlowiceRozanaka-OkregiWyborcze)"
})

PREFIX_TOKENS = {"ul", "ulica", "al", "aleja", "pl", "plac"}
TITLE_TOKENS = {
    "bp", "biskup", "biskupa",
    "gen", "general", "generala",
    "marsz", "marszalek", "marszalka",
    "ks", "ksiadz", "ksiedza",
}
TRANSLATE = str.maketrans({"ł": "l", "Ł": "L"})


def ensure_dirs() -> None:
    for d in (OUT_GEOJSON, OUT_DATA, OUT_DOCS):
        d.mkdir(parents=True, exist_ok=True)


def clean_ascii(value: str) -> str:
    value = value.translate(TRANSLATE)
    value = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in value if not unicodedata.combining(ch))


def normalize_street(value: str | None) -> str:
    if not value:
        return ""
    value = clean_ascii(value).lower()
    value = value.replace("–", "-").replace("—", "-")
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    tokens = value.split()
    while tokens and tokens[0] in PREFIX_TOKENS:
        tokens.pop(0)
    while tokens and tokens[0] in TITLE_TOKENS:
        tokens.pop(0)
    return " ".join(tokens)


def normalize_neighborhood(value: str | None) -> str:
    return normalize_street((value or "").replace(" - ", "-"))


def normalize_number(value: str | None) -> str:
    if value is None:
        return ""
    value = clean_ascii(str(value)).upper()
    value = re.sub(r"\s+", "", value)
    value = value.replace("–", "-").replace("—", "-")
    # EMUiA currently records some combined house numbers with a dash
    # although the 2021 election list used a slash (e.g. 33-35 vs 33/35).
    value = re.sub(r"^(\d+)-(\d+)$", r"\1/\2", value)
    return value


def leading_number(value: str | None) -> int | None:
    m = re.match(r"^(\d+)", normalize_number(value))
    return int(m.group(1)) if m else None


def number_matches(spec: dict[str, Any], number: str | None) -> bool:
    typ = spec.get("type")
    norm = normalize_number(number)
    n = leading_number(norm)

    if typ == "all":
        return bool(norm)
    if typ == "exact":
        exact = {normalize_number(x) for x in spec.get("exact", [])}
        return norm in exact
    if typ == "range":
        return n is not None and int(spec["min"]) <= n <= int(spec["max"])
    if typ == "range_parity":
        if n is None or not (int(spec["min"]) <= n <= int(spec["max"])):
            return False
        parity = spec.get("parity")
        return (n % 2 == 0) if parity == "even" else (n % 2 == 1)
    if typ == "ranges_exact":
        if norm in {normalize_number(x) for x in spec.get("exact", [])}:
            return True
        if n is None:
            return False
        return any(int(a) <= n <= int(b) for a, b in spec.get("ranges", []))
    if typ == "compound":
        return any(number_matches(clause, number) for clause in spec.get("clauses", []))
    raise ValueError(f"Unknown number spec type: {typ!r}")


def street_matches(rule_name: str, actual_name: str | None) -> bool:
    a = normalize_street(actual_name)
    b = normalize_street(rule_name)
    if a == b:
        return True
    at = a.split()
    bt = b.split()
    if len(at) >= 2 and len(bt) >= 2:
        if a.endswith(b) or b.endswith(a):
            return True
        if at[-2:] == bt[-2:]:
            return True
    return False


def classify_address(street: str | None, number: str | None, districts: list[dict[str, Any]]) -> tuple[int | None, list[tuple[int, str]]]:
    hits: list[tuple[int, str]] = []
    for district in districts:
        dno = int(district["district"])
        for rule in district["rules"]:
            if street_matches(rule["street"], street) and number_matches(rule["numbers"], number):
                hits.append((dno, rule["street"]))
    if not hits:
        return None, []
    unique = sorted({h[0] for h in hits})
    return (unique[0] if len(unique) == 1 else None), hits


def request_json(url: str, params: dict[str, Any], timeout: int = 90) -> dict[str, Any]:
    response = SESSION.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(f"ArcGIS error from {url}: {data['error']}")
    return data


def query_geojson(url: str, params: dict[str, Any], page_size: int = 2000) -> dict[str, Any]:
    features: list[dict[str, Any]] = []
    offset = 0
    while True:
        q = dict(params)
        q.update({
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": page_size,
            "returnGeometry": "true",
            "outSR": 4326,
        })
        data = request_json(url, q)
        page = data.get("features", [])
        features.extend(page)
        if len(page) < page_size:
            break
        offset += len(page)
        if offset > 200000:
            raise RuntimeError(f"Pagination safety limit exceeded for {url}")
    return {"type": "FeatureCollection", "features": features}


def polygonal(geom):
    if geom is None or geom.is_empty:
        return MultiPolygon([])
    geom = make_valid(geom)
    if isinstance(geom, Polygon):
        return geom
    if isinstance(geom, MultiPolygon):
        return geom
    if isinstance(geom, GeometryCollection):
        polys = [g for g in geom.geoms if isinstance(g, (Polygon, MultiPolygon))]
        if not polys:
            return MultiPolygon([])
        return unary_union(polys)
    polys = [g for g in getattr(geom, "geoms", []) if isinstance(g, (Polygon, MultiPolygon))]
    return unary_union(polys) if polys else MultiPolygon([])


def iter_polygons(geom) -> Iterable[Polygon]:
    geom = polygonal(geom)
    if isinstance(geom, Polygon):
        yield geom
    elif isinstance(geom, MultiPolygon):
        yield from geom.geoms


def write_geojson(path: Path, features: list[dict[str, Any]]) -> None:
    payload = {"type": "FeatureCollection", "features": features}
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def feature(geom, properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "Feature", "properties": properties, "geometry": mapping(geom)}


def main() -> int:
    ensure_dirs()
    rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    districts: list[dict[str, Any]] = rules["districts"]
    target_name = rules["neighborhood"]

    print("1/7 Pobieranie oficjalnej granicy osiedla...")
    boundary_fc = query_geojson(
        BOUNDARY_URL,
        {"where": "1=1", "outFields": "OBJECTID,NAZWAOSIEDLA,DATA"},
        page_size=1000,
    )
    boundary_features = [
        f for f in boundary_fc["features"]
        if normalize_neighborhood(f.get("properties", {}).get("NAZWAOSIEDLA")) == normalize_neighborhood(target_name)
    ]
    if len(boundary_features) != 1:
        names = [f.get("properties", {}).get("NAZWAOSIEDLA") for f in boundary_fc["features"]]
        raise RuntimeError(f"Expected one neighborhood boundary for {target_name!r}; got {len(boundary_features)}. Available names: {names}")
    boundary = polygonal(shape(boundary_features[0]["geometry"]))
    if boundary.is_empty:
        raise RuntimeError("Neighborhood boundary is empty.")
    minx, miny, maxx, maxy = boundary.bounds
    envelope = f"{minx},{miny},{maxx},{maxy}"

    print("2/7 Pobieranie punktów adresowych EMUiA...")
    addresses_fc = query_geojson(
        ADDRESS_URL,
        {
            "where": "1=1",
            "outFields": "OBJECTID,NAZWA_ULICY,NUMER_PORZADKOWY,KOD_POCZTOWY,DATA,ID_IIP",
            "geometry": envelope,
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
        },
    )
    current_addresses: list[tuple[dict[str, Any], Point]] = []
    for f in addresses_fc["features"]:
        try:
            p = shape(f["geometry"])
        except Exception:
            continue
        if isinstance(p, Point) and boundary.covers(p):
            current_addresses.append((f, p))

    matched: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for f, p in current_addresses:
        props = f.get("properties", {})
        district_no, hits = classify_address(props.get("NAZWA_ULICY"), props.get("NUMER_PORZADKOWY"), districts)
        row = {
            "feature": f,
            "point": p,
            "street": props.get("NAZWA_ULICY"),
            "number": props.get("NUMER_PORZADKOWY"),
            "district": district_no,
            "hits": hits,
        }
        if district_no is not None:
            matched.append(row)
        elif hits:
            ambiguous.append(row)
        else:
            unmatched.append(row)

    if not matched:
        raise RuntimeError("No EMUiA address matched the 2021 electoral rules.")

    by_district_seed = Counter(int(r["district"]) for r in matched)
    missing_seed_districts = [d["district"] for d in districts if by_district_seed[int(d["district"])] == 0]
    if missing_seed_districts:
        raise RuntimeError(f"No address seeds for districts: {missing_seed_districts}")

    print(f"   adresy w osiedlu: {len(current_addresses)}, dopasowane do 2021: {len(matched)}, niejednoznaczne: {len(ambiguous)}")

    print("3/7 Pobieranie działek ewidencyjnych...")
    parcels_fc = query_geojson(
        PARCEL_URL,
        {
            "where": "1=1",
            "outFields": "OBJECTID,ID_SWDE,OBREB,KARTA_MAPY,NUMER",
            "geometry": envelope,
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
        },
    )
    parcels: list[dict[str, Any]] = []
    parcel_geoms = []
    for f in parcels_fc["features"]:
        try:
            g = polygonal(shape(f["geometry"]).intersection(boundary))
        except Exception:
            continue
        if g.is_empty:
            continue
        parcels.append({"feature": f, "geometry": g})
        parcel_geoms.append(g)

    if not parcels:
        raise RuntimeError("Parcel query returned no usable parcels.")

    print(f"   działki po przycięciu do osiedla: {len(parcels)}")

    print("4/7 Kotwiczenie adresów w działkach i przypisanie terenów bez adresów...")
    to_metric = Transformer.from_crs(4326, 2180, always_xy=True)
    to_wgs84 = Transformer.from_crs(2180, 4326, always_xy=True)
    project = lambda g: transform(to_metric.transform, g)
    unproject = lambda g: transform(to_wgs84.transform, g)

    parcel_tree = STRtree(parcel_geoms)
    seed_labels: dict[int, list[int]] = defaultdict(list)
    seed_rows_by_parcel: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for row in matched:
        p = row["point"]
        candidates = list(parcel_tree.query(p, predicate="intersects"))
        chosen: int | None = None
        if candidates:
            covered = [int(i) for i in candidates if parcel_geoms[int(i)].covers(p)]
            if covered:
                chosen = min(covered, key=lambda i: parcel_geoms[i].area)
        if chosen is None:
            nearest = parcel_tree.nearest(p)
            if nearest is not None:
                chosen = int(nearest)
        if chosen is not None:
            seed_labels[chosen].append(int(row["district"]))
            seed_rows_by_parcel[chosen].append(row)
            row["parcel_index"] = chosen

    parcel_conflicts: list[dict[str, Any]] = []
    conflict_indices: set[int] = set()
    parcel_label: dict[int, int] = {}
    for idx, labels in seed_labels.items():
        counts = Counter(labels)
        if len(counts) == 1:
            parcel_label[idx] = int(next(iter(counts)))
            continue
        conflict_indices.add(idx)
        parcel_conflicts.append({
            "parcel_index": idx,
            "id_swde": parcels[idx]["feature"].get("properties", {}).get("ID_SWDE"),
            "labels": dict(sorted(counts.items())),
            "addresses": [
                {
                    "street": row["street"],
                    "number": row["number"],
                    "district": int(row["district"]),
                }
                for row in seed_rows_by_parcel[idx]
            ],
            "resolution": "parcel split by Voronoi cells of electoral address points in EPSG:2180",
        })

    seed_points_metric = [project(r["point"]) for r in matched]
    seed_districts = [int(r["district"]) for r in matched]
    seed_tree_metric = STRtree(seed_points_metric)

    for idx, parcel in enumerate(parcels):
        if idx in parcel_label or idx in conflict_indices:
            continue
        rep_metric = project(parcel["geometry"].representative_point())
        nearest = seed_tree_metric.nearest(rep_metric)
        if nearest is None:
            raise RuntimeError("Could not find nearest electoral address seed.")
        parcel_label[idx] = seed_districts[int(nearest)]

    district_parts: dict[int, list[Any]] = {int(d["district"]): [] for d in districts}
    district_parcel_count = Counter()

    for idx, parcel in enumerate(parcels):
        if idx not in conflict_indices:
            dno = parcel_label[idx]
            district_parts[dno].append(parcel["geometry"])
            district_parcel_count[dno] += 1
            continue

        parcel_metric = project(parcel["geometry"])
        rows = seed_rows_by_parcel[idx]
        sites = [project(row["point"]) for row in rows]

        # If several EMUiA records use exactly the same point, collapse identical
        # sites only when they agree on the district. Different districts at the
        # same coordinate cannot be separated geometrically and are reported.
        unique_sites: dict[tuple[float, float], dict[str, Any]] = {}
        duplicate_site_conflict = False
        for row, site in zip(rows, sites):
            key = (round(site.x, 4), round(site.y, 4))
            existing = unique_sites.get(key)
            if existing is not None and int(existing["district"]) != int(row["district"]):
                duplicate_site_conflict = True
                break
            unique_sites[key] = {"point": site, "district": int(row["district"])}

        if duplicate_site_conflict:
            raise RuntimeError(
                f"Conflicting electoral districts share an identical EMUiA coordinate on parcel "
                f"{parcels[idx]['feature'].get('properties', {}).get('ID_SWDE')}"
            )

        site_records = list(unique_sites.values())
        if len(site_records) < 2:
            dno = int(site_records[0]["district"])
            district_parts[dno].append(parcel["geometry"])
            district_parcel_count[dno] += 1
            continue

        diagram = voronoi_diagram(
            MultiPoint([rec["point"] for rec in site_records]),
            envelope=parcel_metric.envelope,
            edges=False,
        )
        for cell in diagram.geoms:
            clipped = polygonal(cell.intersection(parcel_metric))
            if clipped.is_empty:
                continue
            representative = clipped.representative_point()
            nearest_site = min(
                site_records,
                key=lambda rec: representative.distance(rec["point"]),
            )
            dno = int(nearest_site["district"])
            district_parts[dno].append(polygonal(unproject(clipped)))
            district_parcel_count[dno] += 1

    parcel_union = polygonal(unary_union(parcel_geoms))
    leftovers = polygonal(boundary.difference(parcel_union))
    leftover_components = list(iter_polygons(leftovers))
    for comp in leftover_components:
        rep_metric = project(comp.representative_point())
        nearest = seed_tree_metric.nearest(rep_metric)
        if nearest is not None:
            district_parts[seed_districts[int(nearest)]].append(comp)

    district_geoms: dict[int, Any] = {}
    for dno, parts in district_parts.items():
        district_geoms[dno] = polygonal(unary_union(parts).intersection(boundary))

    print("5/7 Walidacja topologii i punktów adresowych...")
    boundary_area = project(boundary).area
    union_all = polygonal(unary_union(list(district_geoms.values())).intersection(boundary))
    union_area = project(union_all).area
    gap = polygonal(boundary.difference(union_all))
    gap_area = project(gap).area if not gap.is_empty else 0.0
    district_area_sum = sum(project(g).area for g in district_geoms.values())
    overlap_area = max(0.0, district_area_sum - union_area)

    address_validation_errors: list[dict[str, Any]] = []
    for row in matched:
        dno = int(row["district"])
        if not district_geoms[dno].covers(row["point"]):
            address_validation_errors.append({
                "street": row["street"],
                "number": row["number"],
                "district": dno,
            })

    covered_area_report = max(0.0, boundary_area - gap_area)
    coverage_ratio = covered_area_report / boundary_area if boundary_area else 0.0
    coverage_ratio = min(1.0, max(0.0, coverage_ratio))
    if coverage_ratio < 0.999:
        raise RuntimeError(f"District coverage is too low: {coverage_ratio:.6f}")

    print("6/7 Zapisywanie GeoJSON i raportów...")
    retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    write_geojson(
        OUT_GEOJSON / "osiedle-karlowice-rozanka.geojson",
        [feature(boundary, {
            "name": target_name,
            "source": "SIP Wrocławia — granice osiedli",
            "source_url": BOUNDARY_URL.rsplit("/query", 1)[0],
            "crs": "EPSG:4326",
        })],
    )

    combined_features = []
    district_metrics = {}
    for d in districts:
        dno = int(d["district"])
        geom = district_geoms[dno]
        props = {
            "name": f"Karłowice–Różanka — okręg {dno}",
            "district": dno,
            "precinct": int(d["precinct"]),
            "seats": int(d["seats"]),
            "election_year": int(rules["election_year"]),
            "polling_station": d["polling_station"],
            "reconstruction": True,
            "method": "official 2021 address rules + current SIP EMUiA address points + current cadastral parcels",
            "crs": "EPSG:4326",
        }
        f = feature(geom, props)
        write_geojson(OUT_GEOJSON / f"okreg-{dno}.geojson", [f])
        combined_features.append(f)
        district_metrics[str(dno)] = {
            "matched_addresses": int(by_district_seed[dno]),
            "parcel_count": int(district_parcel_count[dno]),
            "area_m2": round(project(geom).area, 2),
            "valid_geometry": bool(geom.is_valid),
            "geometry_type": geom.geom_type,
        }

    write_geojson(OUT_GEOJSON / "karlowice-rozanka-okregi-2021.geojson", combined_features)

    matched_features = []
    for row in matched:
        props = row["feature"].get("properties", {})
        matched_features.append(feature(row["point"], {
            "district": int(row["district"]),
            "street": row["street"],
            "number": row["number"],
            "postal_code": props.get("KOD_POCZTOWY"),
            "source_objectid": props.get("OBJECTID"),
        }))
    write_geojson(OUT_DATA / "addresses-2021-matched.geojson", matched_features)

    validation = {
        "generated_at_utc": retrieved_at,
        "election_year": int(rules["election_year"]),
        "neighborhood": target_name,
        "inputs": {
            "boundary_url": BOUNDARY_URL,
            "address_url": ADDRESS_URL,
            "parcel_url": PARCEL_URL,
            "election_sources": rules["sources"],
        },
        "counts": {
            "current_addresses_in_neighborhood": len(current_addresses),
            "matched_2021_addresses": len(matched),
            "ambiguous_rule_matches": len(ambiguous),
            "current_addresses_not_in_2021_rules": len(unmatched),
            "parcels_intersecting_neighborhood": len(parcels),
            "parcel_seed_conflicts": len(parcel_conflicts),
            "parcel_seed_conflicts_resolved_by_internal_split": len(parcel_conflicts),
            "leftover_polygon_components": len(leftover_components),
        },
        "districts": district_metrics,
        "topology": {
            "boundary_area_m2": round(boundary_area, 2),
            "covered_area_m2": round(covered_area_report, 2),
            "coverage_ratio": round(coverage_ratio, 9),
            "gap_area_m2": round(gap_area, 4),
            "overlap_area_m2": round(overlap_area, 4),
        },
        "validation": {
            "address_points_outside_expected_district": address_validation_errors,
            "parcel_seed_conflicts": parcel_conflicts,
            "current_addresses_not_in_2021_rules": [
                {
                    "street": row["street"],
                    "number": row["number"],
                }
                for row in unmatched
            ],
        },
        "notes": [
            "Election address rules are historical (2021).",
            "EMUiA address points and cadastral parcel geometries are current at build time.",
            "Unaddressed parcels are assigned to the nearest address point that matches a 2021 district rule, using metric EPSG:2180 distance.",
            "Parcels containing address points from more than one district are split internally with Voronoi cells in EPSG:2180.",
            "The output is a reconstruction, not an official municipal district-boundary dataset.",
        ],
    }
    (OUT_DATA / "validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    (OUT_DATA / "source-metadata.json").write_text(
        json.dumps({
            "retrieved_at_utc": retrieved_at,
            "sources": [
                {"name": "SIP — granice osiedli", "url": BOUNDARY_URL},
                {"name": "SIP — EMUiA punkty adresowe", "url": ADDRESS_URL},
                {"name": "SIP — działki ewidencyjne", "url": PARCEL_URL},
                {"name": "Wybory do Rad Osiedli 2021 — Karłowice-Różanka", "url": rules["sources"]["city_article"]},
                {"name": "Wykaz okręgów, obwodów i lokali", "url": rules["sources"]["city_districts_article"]},
                {"name": "Oficjalny PDF 2021", "url": rules["sources"]["official_pdf"]},
            ],
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    summary_lines = [
        "# Raport rekonstrukcji",
        "",
        f"Generowanie: `{retrieved_at}`",
        "",
        "## Wynik walidacji",
        "",
        f"- Powierzchnia osiedla: **{boundary_area/1_000_000:.3f} km²**",
        f"- Pokrycie pięcioma okręgami: **{coverage_ratio*100:.6f}%**",
        f"- Luka powierzchniowa: **{gap_area:.2f} m²**",
        f"- Nakładanie powierzchniowe: **{overlap_area:.2f} m²**",
        f"- Rozpoznane punkty adresowe z reguł 2021: **{len(matched)}**",
        f"- Niejednoznaczne dopasowania reguł: **{len(ambiguous)}**",
        f"- Konflikty okręgów w obrębie tej samej działki: **{len(parcel_conflicts)}**",
        f"- Punkty adresowe poza swoim poligonem po walidacji: **{len(address_validation_errors)}**",
        "",
        "## Okręgi",
        "",
        "| Okręg | Adresy kotwiczące | Działki | Powierzchnia |",
        "|---:|---:|---:|---:|",
    ]
    for dno in sorted(int(d["district"]) for d in districts):
        m = district_metrics[str(dno)]
        summary_lines.append(
            f"| {dno} | {m['matched_addresses']} | {m['parcel_count']} | {m['area_m2']/1_000_000:.3f} km² |"
        )
    summary_lines += [
        "",
        "## Interpretacja",
        "",
        "Poligony są rekonstrukcją. Przynależność adresów wynika z urzędowego wykazu wyborczego z 2021 r.; "
        "przebieg po terenach bez adresów wynika z bieżącego układu działek i najbliższych punktów adresowych przypisanych do okręgów.",
        "",
        "Szczegóły maszynowe: `data/generated/validation.json`.",
        "",
    ]
    (OUT_DOCS / "summary.md").write_text("\n".join(summary_lines), encoding="utf-8")

    combined_json = json.dumps({"type": "FeatureCollection", "features": combined_features}, ensure_ascii=False)
    html = f"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Karłowice–Różanka — okręgi 2021</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
html,body,#map{{height:100%;margin:0}}
.info{{background:white;padding:8px 10px;font:14px/1.35 system-ui,sans-serif;border-radius:4px;box-shadow:0 1px 5px #0004}}
</style>
</head>
<body>
<div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const districts={combined_json};
const colors={{1:"#e41a1c",2:"#377eb8",3:"#4daf4a",4:"#984ea3",5:"#ff7f00"}};
const map=L.map("map");
L.tileLayer("https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}}).addTo(map);
const layer=L.geoJSON(districts,{{
  style:f=>({{color:colors[f.properties.district],weight:2,fillOpacity:0.24}}),
  onEachFeature:(f,l)=>l.bindPopup(
    `<b>Okręg ${{f.properties.district}}</b><br>`+
    `Obwód: ${{f.properties.precinct}}<br>`+
    `Lokal: ${{f.properties.polling_station}}`
  )
}}).addTo(map);
map.fitBounds(layer.getBounds(),{{padding:[10,10]}});
const info=L.control({{position:"topright"}});
info.onAdd=()=>{{const d=L.DomUtil.create("div","info");d.innerHTML="<b>Karłowice–Różanka</b><br>Rekonstrukcja okręgów wyborczych 2021";return d;}};
info.addTo(map);
</script>
</body>
</html>
"""
    (OUT_DOCS / "index.html").write_text(html, encoding="utf-8")

    print("7/7 Gotowe.")
    print(json.dumps({
        "matched_addresses": len(matched),
        "parcels": len(parcels),
        "coverage_ratio": coverage_ratio,
        "gap_area_m2": gap_area,
        "overlap_area_m2": overlap_area,
        "address_validation_errors": len(address_validation_errors),
        "parcel_seed_conflicts": len(parcel_conflicts),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
