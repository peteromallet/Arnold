"""Compatibility shim — identity primitives now live at ``vibecomfy.identity``.

Kept so existing ``from vibecomfy.porting.identity import ...`` imports keep
resolving while consumers migrate to the foundational ``vibecomfy.identity``
package (identity is used by IR-core, so it must sit above the porting layer).
"""
from vibecomfy.identity import *  # noqa: F401,F403
from vibecomfy.identity import __all__  # noqa: F401
