#!/usr/bin/env bash
# Run by the shared nandi-conda package workflow before rattler-build.
# recipe/recipe.yaml reads STATIC_VERSION: 0.1.<commit count>, which needs full history.
set -euo pipefail
git fetch -q --unshallow || true
echo "STATIC_VERSION=0.1.$(git rev-list --count HEAD)" >> "$GITHUB_ENV"
