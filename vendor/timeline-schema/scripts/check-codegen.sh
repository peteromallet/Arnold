#!/usr/bin/env bash
# CI gate: re-run codegen and assert no diff in generated artifacts.
set -euo pipefail

PKG_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PKG_ROOT"

if [ ! -d node_modules ]; then
    echo "node_modules missing; run 'npm install' in $PKG_ROOT first" >&2
    exit 2
fi

npm run build:ts --silent
node typescript/dist/scripts/emit-json-schema.js
python scripts/gen_python_types.py

GENERATED=(
    "python/banodoco_timeline_schema/timeline.schema.json"
    "python/banodoco_timeline_schema/generated.py"
)

dirty=0
for f in "${GENERATED[@]}"; do
    if ! git -C "$PKG_ROOT" diff --exit-code --quiet -- "$f" 2>/dev/null; then
        echo "stale generated file: $f" >&2
        dirty=1
    fi
done

if [ "$dirty" -ne 0 ]; then
    echo "codegen drift detected; commit the regenerated files" >&2
    exit 1
fi

echo "codegen clean"
