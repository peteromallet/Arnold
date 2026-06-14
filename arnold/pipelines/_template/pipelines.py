"""Stub re-export for the template pipeline entrypoint.

Package authors: the real pipeline construction logic should live here
(or be imported here from a submodule).  The ``build_pipeline`` exported
by ``__init__.py`` delegates to :func:`arnold.pipelines._authoring.build_skeleton_pipeline`;
replace that delegation with a call to a real builder defined here.
"""

from arnold.pipelines._template import build_pipeline  # noqa: F401 — re-export
