"""Typed-handle parity fixture — re-exports the converted ready_template build.

After the JSON-flavored→real-Python conversion (per docs/megaplan_briefs/
convert_templates_to_real_python.md), the ready_template *is* the typed
parity reference. The original pre-conversion fixture targeted the broken
2-node UUID-wrapper shape; the converted form is the canonical typed shape.
"""

from __future__ import annotations

from ready_templates.image.z_image import build  # noqa: F401
