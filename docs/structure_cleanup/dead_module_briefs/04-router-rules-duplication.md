# Dead Module Audit 04: Router Rules Duplication

Audit `vibecomfy/router/_rules.py` versus `vibecomfy/router_rules.py`.

Check:
- content equality
- imports from each path
- public docs/references
- best stable path to keep
- exact code/doc changes if deduplicating

Return a conservative action.
