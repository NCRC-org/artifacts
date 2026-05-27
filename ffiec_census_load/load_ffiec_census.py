#!/usr/bin/env python3
"""Parse FFIEC Census flat CSVs and load focused subset to BigQuery.

Expects extracted CSVs and definitions/positions_*.json under --workdir (default: ./data).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from google.cloud import bigquery

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_WORKDIR = Path(os.environ.get("FFIEC_LOAD_WORKDIR", SCRIPT_DIR / "data"))

PROJECT = os.environ.get("FFIEC_BQ_PROJECT", "ncrc-project-jason")
DATASET = os.environ.get("FFIEC_BQ_DATASET", "ffiec_census")

INT_COLS = {
    "year",
    "tract_population",
    "total_families",
    "total_households",
    "tract_mfi",
    "tract_mhi",
    "msa_median_family_income",
    "msa_median_household_income",
    "ffiec_msamd_mfi",
    "income_level",
    "owner_occupied_units",
    "one_to_four_family_units",
    "total_housing_units",
    "vacant_units",
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
    "households_lt_10k",
    "households_10_15k",
    "households_15_20k",
    "households_20_25k",
    "households_25_30k",
    "households_30_35k",
    "households_35_40k",
    "households_40_45k",
    "households_45_50k",
    "households_50_60k",
    "households_60_75k",
    "households_75_100k",
    "households_100_125k",
    "households_125_150k",
    "households_150_200k",
    "households_200k_plus",
    "poverty_population",
    "population_for_poverty_status",
}
FLOAT_COLS = {"minority_population_pct", "tract_mfi_pct_of_msamd"}

ROW_COUNT_RANGES = {
    2021: (73000, 76000),
    2022: (84000, 88000),
    2023: (86000, 89000),
    2024: (86000, 89000),
    2025: (86000, 89000),
}

FAMILY_BRACKET_COLS = [
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

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def csv_path(workdir: Path, year: int) -> Path:
    base = workdir / "extracted" / str(year)
    if year == 2024:
        nested = base / f"CensusFlatFile{year}" / f"CensusFlatFile{year}.csv"
        if nested.exists():
            return nested
    matches = sorted(base.glob("**/*.csv"))
    if not matches:
        raise FileNotFoundError(f"No CSV extracted for {year} under {base}")
    return matches[0]


def load_positions(defs_dir: Path, year: int) -> dict[str, int]:
    path = defs_dir / f"positions_{year}.json"
    return json.loads(path.read_text())["positions"]


def _to_int(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def _to_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def parse_year(workdir: Path, defs_dir: Path, year: int) -> pd.DataFrame:
    pos = load_positions(defs_dir, year)
    usecols = sorted(set(pos.values()))
    path = csv_path(workdir, year)
    log.info("Reading %s (%s)", path, year)

    raw = pd.read_csv(
        path,
        header=None,
        usecols=usecols,
        dtype=str,
        encoding="utf-8-sig",
        low_memory=False,
    )
    raw = raw.rename(columns={v: k for k, v in pos.items()})

    out = pd.DataFrame()
    out["year"] = pd.Series([year] * len(raw), dtype="int64")
    out["state_code"] = raw["state_code"].str.zfill(2)
    out["county_code"] = raw["county_code"].str.zfill(3)
    out["tract_code"] = raw["tract_code"].str.zfill(6)
    out["geoid"] = out["state_code"] + out["county_code"] + out["tract_code"]
    out["msamd"] = raw["msamd"].str.strip().replace("", pd.NA)
    out["msa_md_name"] = pd.NA
    out["state_name"] = pd.NA
    out["county_name"] = pd.NA
    out["principal_city_flag"] = raw["principal_city_flag"].astype(str).str.strip()
    out["urban_rural_flag"] = raw["urban_rural_flag"].astype(str).str.strip()
    out["distressed_underserved_flag"] = (
        raw["distressed_underserved_flag"].astype(str).str.strip().replace({"": pd.NA})
    )

    for col in INT_COLS - {"year"}:
        if col in raw.columns:
            out[col] = _to_int(raw[col])
        else:
            out[col] = pd.NA
            log.warning("%s: field %s missing in positions", year, col)

    for col in FLOAT_COLS:
        out[col] = _to_float(raw[col])

    out.loc[out["msamd"].isin(["99999", "0", ""]), "msamd"] = pd.NA
    return out


def validate_frame(df: pd.DataFrame, year: int) -> None:
    lo, hi = ROW_COUNT_RANGES[year]
    n = len(df)
    if not (lo <= n <= hi):
        raise ValueError(f"{year}: row count {n} outside expected {lo}-{hi}")

    bracket_sum = df[FAMILY_BRACKET_COLS].sum(axis=1, skipna=True)
    fam = df["total_families"].astype("float")
    bad = ((bracket_sum - fam).abs() > (fam * 0.05 + 5)) & fam.notna() & (fam > 0)
    pct_bad = bad.mean()
    if pct_bad > 0.02:
        raise ValueError(f"{year}: {pct_bad:.1%} tracts fail family bracket sum check")
    log.info("%s: %s tracts, bracket mismatch rate %.2f%%", year, n, 100 * pct_bad)


def save_parquet(df: pd.DataFrame, parquet_dir: Path, year: int) -> Path:
    parquet_dir.mkdir(parents=True, exist_ok=True)
    out = parquet_dir / f"ffiec_census_{year}.parquet"
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), out)
    log.info("Wrote %s", out)
    return out


def upload_parquet(parquet_path: Path, year: int, client: bigquery.Client) -> None:
    table_id = f"{PROJECT}.{DATASET}.ffiec_census_{year}"
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    with open(parquet_path, "rb") as f:
        job = client.load_table_from_file(f, table_id, job_config=job_config)
    job.result()
    log.info("Loaded %s (%s rows)", table_id, job.output_rows)


def create_union_view(client: bigquery.Client) -> None:
    parts = [f"SELECT * FROM `{PROJECT}.{DATASET}.ffiec_census_{y}`" for y in range(2021, 2026)]
    sql = (
        f"CREATE OR REPLACE VIEW `{PROJECT}.{DATASET}.ffiec_census_all_years` AS\n"
        + "\nUNION ALL\n".join(parts)
    )
    client.query(sql).result()


def cross_check_ami(client: bigquery.Client) -> dict:
    q = f"""
    WITH new_tbl AS (
      SELECT DISTINCT msamd, ffiec_msamd_mfi
      FROM `{PROJECT}.{DATASET}.ffiec_census_2025`
      WHERE msamd IS NOT NULL
    ),
    old_tbl AS (
      SELECT DISTINCT msamd, ffiec_msamd_mfi
      FROM `hdma1-242116.geo.census`
      WHERE year = '2025'
    )
    SELECT
      COUNT(*) AS rows_compared,
      COUNTIF(n.ffiec_msamd_mfi = o.ffiec_msamd_mfi) AS matches,
      COUNTIF(n.ffiec_msamd_mfi != o.ffiec_msamd_mfi) AS mismatches
    FROM new_tbl n
    JOIN old_tbl o USING (msamd)
    """
    return dict(list(client.query(q).result())[0])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--workdir", type=Path, default=DEFAULT_WORKDIR)
    p.add_argument(
        "--definitions",
        type=Path,
        default=None,
        help="Directory with positions_*.json (default: <workdir>/definitions or repo definitions/)",
    )
    p.add_argument("--years", nargs="+", type=int, default=[2021, 2022, 2023, 2024, 2025])
    p.add_argument("--parse-only", action="store_true")
    p.add_argument("--skip-upload", action="store_true")
    args = p.parse_args(argv)

    defs_dir = args.definitions or (
        args.workdir / "definitions"
        if (args.workdir / "definitions").exists()
        else SCRIPT_DIR / "definitions"
    )
    parquet_dir = args.workdir / "parquet"

    if not defs_dir.exists():
        log.error("Definitions not found at %s", defs_dir)
        return 1

    client = bigquery.Client(project=PROJECT)
    for year in args.years:
        df = parse_year(args.workdir, defs_dir, year)
        validate_frame(df, year)
        save_parquet(df, parquet_dir, year)
        if not args.parse_only and not args.skip_upload:
            upload_parquet(parquet_dir / f"ffiec_census_{year}.parquet", year, client)

    if not args.parse_only and not args.skip_upload:
        create_union_view(client)
        cc = cross_check_ami(client)
        log.info("AMI cross-check: %s", cc)
        if cc.get("mismatches"):
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
