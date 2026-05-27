#!/usr/bin/env python3
"""Generate definitions/positions_2022.json … positions_2025.json and positions_2021.json.

2022-2025: FFIEC 1-based field indices from schema_2023_reference.csv (2022+ layout).
2021: cen2021.docx in the extracted 2021 zip (different column layout).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
OUT_DIR = SCRIPT_DIR / "definitions"

FIELD_INDEX = {
    "year": 1,
    "msamd": 2,
    "state_code": 3,
    "county_code": 4,
    "tract_code": 5,
    "principal_city_flag": 6,
    "urban_rural_flag": 10,
    "msa_median_family_income": 11,
    "msa_median_household_income": 12,
    "tract_mfi_pct_of_msamd": 13,
    "ffiec_msamd_mfi": 14,
    "income_level": 15,
    "tract_population": 23,
    "total_families": 24,
    "total_households": 25,
    "minority_population_pct": 29,
    "tract_mfi": 586,
    "tract_mhi": 382,
    "distressed_underserved_flag": 22,
    "owner_occupied_units": 881,
    "one_to_four_family_units": 901,
    "total_housing_units": 874,
    "vacant_units": 879,
    "poverty_population": 756,
    "population_for_poverty_status": 755,
}
FAMILY_START = 570
HOUSEHOLD_START = 366


def col(idx: int) -> int:
    return idx - 1


def modern_positions() -> dict[str, int]:
    pos = {k: col(v) for k, v in FIELD_INDEX.items()}
    fam_names = [
        "families_lt_10k",
        "families_10_15k",
        "families_15_20k",
        "families_20_25k",
        "families_25_30k",
        "families_30_35k",
        "families_35_40k",
        "families_40_45k",
        "families_45_50k",
        "families_50_60k",
        "families_60_75k",
        "families_75_100k",
        "families_100_125k",
        "families_125_150k",
        "families_150_200k",
        "families_200k_plus",
    ]
    hh_names = [n.replace("families_", "households_") for n in fam_names]
    for i, n in enumerate(fam_names):
        pos[n] = col(FAMILY_START + i)
    for i, n in enumerate(hh_names):
        pos[n] = col(HOUSEHOLD_START + i)
    return pos


def build_2021(docx_path: Path, modern: dict[str, int]) -> dict[str, int]:
    from docx import Document

    pos = modern.copy()
    pos.update(
        {
            "tract_population": 14,
            "total_families": 15,
            "total_households": 16,
            "minority_population_pct": 20,
            "households_lt_10k": 360,
            "households_10_15k": 361,
            "households_15_20k": 362,
            "households_20_25k": 363,
            "households_25_30k": 364,
            "households_30_35k": 365,
            "households_35_40k": 366,
            "households_40_45k": 367,
            "households_45_50k": 368,
            "households_50_60k": 369,
            "households_60_75k": 370,
            "households_75_100k": 371,
            "households_100_125k": 372,
            "households_125_150k": 373,
            "households_150_200k": 374,
            "households_200k_plus": 375,
            "families_lt_10k": 564,
            "families_10_15k": 565,
            "families_15_20k": 566,
            "families_20_25k": 567,
            "families_25_30k": 568,
            "families_30_35k": 569,
            "families_35_40k": 570,
            "families_40_45k": 571,
            "families_45_50k": 572,
            "families_50_60k": 573,
            "families_60_75k": 574,
            "families_75_100k": 575,
            "families_100_125k": 576,
            "families_125_150k": 577,
            "families_150_200k": 578,
            "families_200k_plus": 579,
        }
    )

    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", s.lower().strip())

    table = max(Document(docx_path).tables, key=lambda t: len(t.rows))
    for row in table.rows:
        cells = [c.text.strip() for c in row.cells]
        if not cells or not cells[0].isdigit():
            continue
        desc = norm(cells[1] if len(cells) > 1 else "")
        c = int(cells[0]) - 1
        if desc == "median family income - tract level":
            pos["tract_mfi"] = c
        elif desc == "median household income - tract level":
            pos["tract_mhi"] = c
        elif desc == "total housing units":
            pos["total_housing_units"] = c
        elif desc == "total vacant housing units":
            pos["vacant_units"] = c
        elif desc == "total owner occupied housing units":
            pos["owner_occupied_units"] = c
        elif "total housing units in structure - 1 to 4" in desc:
            pos["one_to_four_family_units"] = c
        elif desc == "population where income is below poverty level":
            pos["poverty_population"] = c
        elif desc == "total population for whom poverty status is determined":
            pos["population_for_poverty_status"] = c
        elif "distressed/underserved tract criteria" in desc:
            pos["distressed_underserved_flag"] = c
    return pos


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    modern = modern_positions()
    for year in (2022, 2023, 2024, 2025):
        (OUT_DIR / f"positions_{year}.json").write_text(
            json.dumps(
                {
                    "year": year,
                    "source": "FFIEC 2023 schema reference (2022+ CSV layout)",
                    "positions": modern,
                },
                indent=2,
            )
        )

    docx = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if docx is None:
        print("Skip positions_2021.json (pass path to cen2021.docx to generate)")
        return 0

    pos21 = build_2021(docx, modern)
    (OUT_DIR / "positions_2021.json").write_text(
        json.dumps(
            {
                "year": 2021,
                "source": "cen2021.docx + 2022+ core columns 1-14",
                "positions": pos21,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
