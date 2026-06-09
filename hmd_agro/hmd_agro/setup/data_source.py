"""Shared CSV loader for the import scripts.

Keeps per-farm DATA in external CSV files (NOT baked into the code), so the import
scripts are generic and reusable for any farm. By default the CSVs live in the
site's private folder — `sites/<site>/private/farm_data/` — which is on the shared
`sites` volume (so every container sees them; no per-container copy needed). Override
the folder by passing `source="/some/path"` to a script's run().

Drop the CSV set there once, then run the imports.
"""
import csv
import os

import frappe


def folder(source=None):
    """Resolve the data folder: explicit `source`, else <site>/private/farm_data."""
    return source or frappe.get_site_path("private", "farm_data")


def read(source, filename):
    """Return the CSV rows as a list of dicts (header row = keys)."""
    path = os.path.join(folder(source), filename)
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def num(value, cast=float):
    """'' -> None; otherwise cast (int/float). For optional numeric CSV columns."""
    value = (value or "").strip()
    return None if value == "" else cast(value)


def txt(value):
    """Trim; '' -> None (for optional text columns / links)."""
    value = (value or "").strip()
    return value or None
