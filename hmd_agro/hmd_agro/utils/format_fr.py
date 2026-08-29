"""
French display helpers shared by the reports and the validation messages.

Before this module each report carried its own copy of `_fr` and
`maintenance_utils` its own `_jjmmaaaa`; the copies were identical, so they
now live here. The output formats are unchanged on purpose — labels and
error messages read exactly as before.
"""
from frappe.utils import getdate

DATE_VIDE = "—"


def fr_nombre(valeur, decimales=None):
    """Number written the French way (decimal comma).

    `decimales=None` keeps the shortest representation (`:g` — « 2,2 »,
    « 100 », « 33,33 »), the historical format of every label and message;
    an integer forces that many decimals (« 100,00 »).
    """
    texte = f"{valeur:g}" if decimales is None else f"{valeur:.{decimales}f}"
    return texte.replace(".", ",")


def fr_date(date, vide=DATE_VIDE):
    """`date` (date, datetime or string) as jj/mm/aaaa; `vide` when unset."""
    return getdate(date).strftime("%d/%m/%Y") if date else vide
