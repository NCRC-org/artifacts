# Handoff: FFIEC Census flat files → `ncrc-project-jason`

See [README.md](README.md) for what was built and how to refresh.

## Completed (2026-05-26)

- Dataset `ncrc-project-jason.ffiec_census` created (Jay had not named an existing census dataset; used suggested `ffiec_census`).
- Tables `ffiec_census_2021`–`ffiec_census_2025` and view `ffiec_census_all_years`.
- Source: FFIEC annual zips on Desktop; files are **CSV** (1,212 cols for 2022+, 1,247 for 2021), not fixed-width.
- AMI cross-check vs `hdma1-242116.geo.census` (2025 only in hdma1): 417 MSAs, 0 mismatches.
- Loader and `definitions/positions_*.json` in this folder.

## Original goals

Per-MSA chart: FFIEC AMI (`ffiec_msamd_mfi`) vs ACS family income distribution (16 brackets), 2021–2025, including where 80% LMI threshold falls in the distribution.

## Field subset

~55 columns: GEOID, MSAMD, tract/MSA income fields, 16 family + 16 household income brackets, poverty, basic housing counts. Full handoff column list is in the Cursor task that created this load.

## Not loaded / NULL by design

- Geographic names (not in CSV).
- `income_level` for 2021 (docx did not map cleanly; use `tract_mfi_pct_of_msamd`).
