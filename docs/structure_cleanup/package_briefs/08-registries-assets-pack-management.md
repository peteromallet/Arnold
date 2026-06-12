# Package Layer Audit 08: Registries, Assets, Pack Management

Audit model/asset/custom-node pack registries and node-pack management:
`registry/`, `node_packs/`, `models.py`, `model_assets.py`, `fixtures.py`, etc.

Questions:
- Which package files own tracked registry data?
- Are there generated indexes/caches under source directories?
- Are local runtime/model files kept out of the package?
- Are docs/READMEs missing for path-sensitive data?

Return safe cleanup and deferrals.
