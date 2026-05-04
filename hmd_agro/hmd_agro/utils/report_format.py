"""Project-wide formatting helpers for query reports.

Centralizes display conventions so every report shows numbers consistently,
regardless of who wrote the column definition or when.
"""
import functools


NUMERIC_FIELDTYPES = ("Float", "Percent", "Currency")


def with_uniform_precision(columns, precision=1):
    """Force `precision=1` (or other) on all Float/Percent/Currency columns.

    Mutates the columns list in place AND returns it for chaining.
    Skips Int (no decimals) and non-numeric fieldtypes.
    """
    for c in columns:
        if c.get("fieldtype") in NUMERIC_FIELDTYPES:
            c["precision"] = precision
    return columns


def with_uniform_summary_precision(summary, precision=1):
    """Frappe's build_summary_item ignores `precision` on summary items
    (it only forwards `datatype` to its formatter), so the only reliable way
    to control display is to pre-format the value in Python and switch
    `datatype` to "Data" — Frappe then renders the string verbatim.

    Uses space as thousands separator to match French/European convention
    (12 345.6 instead of 12,345.6). System Settings → Number Format must be
    set to "# ###.##" so table cells (which Frappe formats automatically)
    use the same convention.

    Skips Currency to avoid breaking currency-symbol rendering.
    """
    for s in summary:
        dt = s.get("datatype")
        v = s.get("value")
        if dt not in ("Float", "Percent"):
            continue
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            continue
        suffix = " %" if dt == "Percent" else ""
        # f"{v:,.1f}" → "12,345.6" → swap comma for space → "12 345.6"
        s["value"] = f"{v:,.{precision}f}".replace(",", " ") + suffix
        s["datatype"] = "Data"
    return summary


def normalize_precision(execute_fn):
    """Decorator: force precision=1 on every numeric thing a Frappe report
    returns — both table columns AND summary cards (the values displayed
    above the chart). Handles tuple shapes from 2 up to 5 elements:
        (columns, data)
        (columns, data, message)
        (columns, data, message, chart)
        (columns, data, message, chart, summary)
    """
    @functools.wraps(execute_fn)
    def wrapper(filters=None):
        result = execute_fn(filters)
        if isinstance(result, tuple) and result and isinstance(result[0], list):
            with_uniform_precision(result[0])
            # Summary is at index 4 in the canonical 5-tuple shape.
            if len(result) >= 5 and isinstance(result[4], list):
                with_uniform_summary_precision(result[4])
        return result
    return wrapper
