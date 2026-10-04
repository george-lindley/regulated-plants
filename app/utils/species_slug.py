"""Public URL slugs for species pages.

The slug is the permanent address of a species page (``/species/<slug>``) and has
been shared with partners such as CABI, so this function must not change: any change
breaks every link already published. ``prosopis-glandulosa-x-velutina`` comes from
``Prosopis glandulosa x velutina`` (or ``×``).
"""
import re


def species_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower().replace("×", "x")).strip("-")
