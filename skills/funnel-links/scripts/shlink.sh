#!/usr/bin/env bash
# Optional: short links through a Shlink server you run yourself (https://shlink.io, open source).
# Usage:
#   shlink.sh create  <slug> <long_url> [title]
#   shlink.sh repoint <slug> <long_url>
#   shlink.sh get     <slug>
#   shlink.sh check   <slug>            # prints HTTP code + redirect target
#   shlink.sh visits  <slug> [since]    # since = 2026-01-31T12:00:00Z
# Env (never print the key): SHLINK_BASE_URL (https://go.example.com), SHLINK_API_KEY.
set -euo pipefail

: "${SHLINK_BASE_URL:?set SHLINK_BASE_URL, see .env.example}"
: "${SHLINK_API_KEY:?set SHLINK_API_KEY, see .env.example}"

API="${SHLINK_BASE_URL%/}/rest/v3"
cmd="${1:-}"
slug="${2:-}"

if [ -z "$cmd" ] || [ -z "$slug" ]; then
  echo "usage: $0 create|repoint|get|check|visits <slug> ..." >&2
  exit 2
fi

api() {
  # api <method> <path> [json body]
  local method="$1" path="$2" body="${3:-}"
  if [ -n "$body" ]; then
    curl -sS -X "$method" "$API$path" -H "X-Api-Key: $SHLINK_API_KEY" -H "Content-Type: application/json" -d "$body"
  else
    curl -sS -X "$method" "$API$path" -H "X-Api-Key: $SHLINK_API_KEY"
  fi
}

json_body() {
  python3 -c 'import json,sys; print(json.dumps(dict(zip(sys.argv[1::2], sys.argv[2::2]))))' "$@"
}

case "$cmd" in
  create)
    long_url="${3:?long_url required}"
    title="${4:-$slug}"
    body="$(json_body longUrl "$long_url" customSlug "$slug" title "$title")"
    echo "create $slug"
    api POST "/short-urls" "$body" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("shortUrl") or d)'
    ;;
  repoint)
    long_url="${3:?long_url required}"
    body="$(json_body longUrl "$long_url")"
    echo "repoint $slug"
    curl -sS -o /dev/null -w "patch %{http_code}\n" -X PATCH "$API/short-urls/$slug" \
      -H "X-Api-Key: $SHLINK_API_KEY" -H "Content-Type: application/json" -d "$body"
    ;;
  get)
    api GET "/short-urls/$slug" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("shortCode"), d.get("longUrl"), (d.get("visitsSummary") or {}).get("total"))'
    ;;
  check)
    curl -s -o /dev/null -A Mozilla -w "$slug %{http_code} %{redirect_url}\n" "${SHLINK_BASE_URL%/}/$slug"
    ;;
  visits)
    query="?itemsPerPage=1"
    if [ -n "${3:-}" ]; then query="$query&startDate=$3"; fi
    api GET "/short-urls/$slug/visits$query" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(sys.argv[1], d["visits"]["pagination"]["totalItems"])' "$slug"
    ;;
  *)
    echo "usage: $0 create|repoint|get|check|visits <slug> ..." >&2
    exit 2
    ;;
esac
