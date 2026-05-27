# FFIEC Census flat file load (2021–2025)

Tract-level FFIEC Census flat file data in BigQuery for LMI drift / income-distribution analysis. Loads a focused ~55-column subset (family and household income brackets, AMI fields, core demographics) from the annual FFIEC CSV releases.

## BigQuery location

| Object | ID |
|--------|-----|
| Project | `ncrc-project-jason` |
| Dataset | `ffiec_census` |
| Tables | `ffiec_census_2021` … `ffiec_census_2025` |
| View | `ffiec_census_all_years` |

Example:

```sql
SELECT year, geoid, msamd, ffiec_msamd_mfi, tract_mfi_pct_of_msamd,
       families_lt_10k, families_200k_plus, total_families
FROM `ncrc-project-jason.ffiec_census.ffiec_census_all_years`
WHERE msamd = '35614' AND year = 2025;
```

## Row counts (loaded 2026-05-26)

| Year | Tracts | Notes |
|------|--------|--------|
| 2021 | 75,883 | 2010-vintage tract geography |
| 2022 | 87,275 | 2020-vintage tracts |
| 2023 | 87,275 | |
| 2024 | 87,276 | |
| 2025 | 87,281 | |

## Source files

FFIEC publishes **headerless CSV** files inside the annual zips (not fixed-width `.dat` in recent years). Place extracted CSVs under:

```
<workdir>/extracted/2025/CensusFlatFile2025.csv
<workdir>/extracted/2024/CensusFlatFile2024/CensusFlatFile2024.csv  # nested folder in 2024 zip
...
```

Official dictionaries: [FFIEC flat files](https://www.ffiec.gov/data/census/flat-files) (XLSX; Cloudflare may block automated download). This repo stores **0-based CSV column indices** in `definitions/positions_*.json`.

- **2022–2025:** Derived from [djarrard/ffiec_2023_arcgis schema](https://github.com/djarrard/ffiec_2023_arcgis/blob/main/schema_2023.csv) (1-based index → column = index − 1).
- **2021:** Different layout (1,247 columns). Bracket columns from `cen2021.docx` in the 2021 zip; run `build_positions.py` with path to that docx.

## Refresh workflow

1. Download zips from FFIEC (browser).
2. Extract to `<workdir>/extracted/YEAR/`.
3. Regenerate `positions_2021.json` if needed:  
   `python build_positions.py path/to/cen2021.docx`
4. Parse and load (ADC → `ncrc-project-jason`):

```bash
python load_ffiec_census.py --workdir C:/Users/edite/Desktop/ffiec_load
```

Options: `--parse-only`, `--skip-upload`, `--years 2025`.

## Validation

- Family bracket sums ≈ `total_families` (&lt;2% tracts off by &gt;5%).
- 2025 `ffiec_msamd_mfi` vs `hdma1-242116.geo.census` (2025): **417 MSAs, 0 mismatches**.

## Caveats

- **`msa_md_name`, `state_name`, `county_name`:** NULL (not in CSV; join from FIPS/MSA crosswalk if needed).
- **`income_level`:** NULL for **2021** (field index not in 2021 docx table used; derive from `tract_mfi_pct_of_msamd` if needed).
- **`msamd`:** NULL when non-metro (`99999` stripped).
- Do not write to `hdma1-242116`; this dataset is the research copy in `ncrc-project-jason`.

## Files

| File | Purpose |
|------|---------|
| `HANDOFF.md` | Original build spec |
| `load_ffiec_census.py` | Parse CSV → parquet → BigQuery |
| `build_positions.py` | Build `definitions/positions_*.json` |
| `definitions/positions_*.json` | Per-year column map |
