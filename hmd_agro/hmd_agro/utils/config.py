"""Centralized accessor for HMD Configuration values.

All callers should use `get_config(field, default=...)` instead of literals.
The `default` argument is mandatory in spirit — it's the documented constant
that preserves historical behavior when the Single hasn't been initialized
(e.g. fresh DB, unit tests). Frappe caches Singles per-request so repeated
calls within one request are cheap.
"""
import frappe


def get_config(fieldname, default=None):
    try:
        value = frappe.db.get_single_value("HMD Configuration", fieldname)
    except Exception:
        value = None
    return value if value is not None else default
