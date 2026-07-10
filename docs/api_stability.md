# API Stability Policy

VibeComfy treats each public module's `__all__` value as that module's intentional export boundary.

Names in `__all__` are the supported import surface for downstream code and generated templates. Names omitted from `__all__`, including leading-underscore helpers, are internal implementation details unless a narrower document explicitly says otherwise.

Changes that remove or rename an exported name should be made deliberately with migration notes or compatibility aliases when existing templates, recipes, or CLI-facing workflows depend on that name.
