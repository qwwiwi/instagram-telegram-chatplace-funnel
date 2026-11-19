#!/usr/bin/env bash
# Local checks (no CI): python syntax, bash syntax, offline tests, generic secret/private-path scan.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "python syntax"
find . -name '*.py' -not -path './.git/*' -not -path '*/.venv/*' -print0 | xargs -0 -n1 python3 -m py_compile

echo "bash syntax"
find . -name '*.sh' -not -path './.git/*' -not -path '*/.venv/*' -print0 | xargs -0 -n1 bash -n

echo "tests"
python3 -m unittest discover -s tests

echo "secret scan"
# Token-like strings, absolute home paths, private keys. Fake values in .env.example contain "FAKE" or "your_".
PATTERN='(sk-[A-Za-z0-9]{20,}|[0-9]{8,10}:AA[A-Za-z0-9_-]{30,}|eyJhbGci|BEGIN [A-Z ]*PRIVATE KEY|/Use[r]s/[a-z]|/hom[e]/[a-z]|cpk_[A-Za-z0-9]{8,})'
# This file is excluded: it contains the patterns themselves.
if git ls-files -z -- . ':!scripts/check.sh' | xargs -0 grep -nIE "$PATTERN" -- ; then
  echo "possible secret or private path found" >&2
  exit 1
fi
echo "ok"
