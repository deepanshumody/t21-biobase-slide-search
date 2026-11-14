#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

if [[ "$(git branch --show-current)" != "main" ]]; then
  printf '%s\n' 'Refusing to publish: the current branch must be main.' >&2
  exit 1
fi
if [[ -n "$(git status --porcelain)" ]]; then
  printf '%s\n' 'Refusing to publish: commit or resolve the local changes first.' >&2
  exit 1
fi
if git remote get-url origin >/dev/null 2>&1; then
  printf '%s\n' 'An origin remote already exists. Inspect it before publishing again.' >&2
  exit 1
fi

python3 scripts/verify_repository_artifacts.py
gh repo create t21-biobase-slide-search \
  --private \
  --source . \
  --remote origin \
  --push \
  --description 'Team T21: Biobase organ classification, slide retrieval baseline, and reproducible evaluation.'
gh repo edit --default-branch main
gh repo view --json url,isPrivate,defaultBranchRef
