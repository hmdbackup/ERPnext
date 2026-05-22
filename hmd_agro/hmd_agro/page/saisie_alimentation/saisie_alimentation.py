"""
Saisie Alimentation page — thin Frappe page wrapper around
utils/feed_correction.py.

The supervisor-validated model is per-aliment: rows are aliments, the farmer
enters the actual total distributed across the herd, and the system splits
the delta proportionally across lots. The Python side just re-exports the
whitelisted endpoints under the page's namespace so the JS frontend can
call them via the conventional `<module>.<page>.<method>` path.
"""
from hmd_agro.hmd_agro.utils.feed_correction import (
    get_aliment_state,
    post_aliment_corrections_batch,
    cancel_aliment_correction,
)

__all__ = [
    "get_aliment_state",
    "post_aliment_corrections_batch",
    "cancel_aliment_correction",
]
