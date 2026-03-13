#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   scripts/resolve_conflicts_local.sh <target-branch>
# Example:
#   scripts/resolve_conflicts_local.sh main

TARGET_BRANCH="${1:-main}"

echo "[1/6] Fetching latest refs..."
git fetch origin

echo "[2/6] Rebasing current branch onto origin/${TARGET_BRANCH}..."
git rebase "origin/${TARGET_BRANCH}" || true

if git diff --name-only --diff-filter=U | grep -q .; then
  echo "[3/6] Auto-resolving known UI/API conflict files with current branch versions..."
  for f in \
    app/routers/api.py \
    app/static/admin.js \
    app/static/styles.css \
    app/templates/base.html \
    app/templates/index.html \
    app/templates/login.html
  do
    if git ls-files -u -- "$f" | grep -q .; then
      git checkout --ours -- "$f"
      git add "$f"
      echo "  - resolved: $f"
    fi
  done

  echo "[4/6] Continue rebase..."
  git rebase --continue || true
fi

if git diff --name-only --diff-filter=U | grep -q .; then
  echo "[5/6] Remaining unresolved files:"
  git diff --name-only --diff-filter=U
  echo "Resolve manually, then run: git add <files> && git rebase --continue"
  exit 1
fi

echo "[6/6] Done. Push with force-with-lease:"
echo "git push --force-with-lease"
