#!/bin/bash
# Wrapper to run megaplan CLI from arnold-v2 without module shadowing.
# The arnold-v2 project has a megaplan/ package that shadows the CLI tool.
# We work around this by temporarily renaming it during megaplan operations.

PROJ_DIR="/Users/peteromalley/Documents/arnold-v2"
SHADOW_DIR="$PROJ_DIR/megaplan"
BACKUP_DIR="$PROJ_DIR/_megaplan_sdk"

# Move conflicting dir out of the way
if [ -d "$SHADOW_DIR" ]; then
    rm -rf "$BACKUP_DIR"
    mv "$SHADOW_DIR" "$BACKUP_DIR"
fi

# Run the actual megaplan command
cd "$PROJ_DIR"
uv run --project /Users/peteromalley/Documents/megaplan python -m megaplan "$@"
EXIT_CODE=$?

# Restore the dir
if [ -d "$BACKUP_DIR" ]; then
    mv "$BACKUP_DIR" "$SHADOW_DIR"
fi

exit $EXIT_CODE
