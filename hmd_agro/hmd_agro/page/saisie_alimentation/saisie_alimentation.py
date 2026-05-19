"""
Saisie Alimentation page — thin Frappe page wrapper around
utils/feed_correction.py.

The Python side does almost nothing — it just re-exports the three
whitelisted endpoints under the page's namespace so the JS frontend can
call them via the conventional `<module>.<page>.<method>` path. The real
logic lives in utils/feed_correction.py and is tested independently by
tests/test_feed_correction.py.
"""
from hmd_agro.hmd_agro.utils.feed_correction import (
    get_saisie_state,
    post_correction,
    post_corrections_batch,
    cancel_correction,
)

__all__ = [
    "get_saisie_state",
    "post_correction",
    "post_corrections_batch",
    "cancel_correction",
]
