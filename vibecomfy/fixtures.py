"""Public smoke-fixture CLI wrapper.

The implementation lives in ``vibecomfy.testing._fixtures_smoke``; this module
preserves the ``python -m vibecomfy.fixtures`` CLI contract.
"""

from __future__ import annotations

from vibecomfy.testing._fixtures_smoke import (  # noqa: F401, F403
    FIXTURE_ROOT,
    GUIDE_VIDEOS,
    SMOKE_FIXTURES,
    __all__ as _smoke_all,
    _main,
    available_fixtures,
    copy_smoke_fixtures,
    main,
    regenerate_smoke_fixtures,
)

# Re-export __all__ so ``from vibecomfy.fixtures import *`` works.
__all__ = _smoke_all

if __name__ == "__main__":
    from vibecomfy.testing._fixtures_smoke import _main
    raise SystemExit(_main())
