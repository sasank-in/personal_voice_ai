#!/usr/bin/env bash
# Checks a running stack over HTTPS. Usage: deploy/smoke-test.sh https://localhost:8443
set -euo pipefail

base="$1"
failures=0

# -k because a local stack uses Caddy's own certificate authority.
check() {
  local name="$1" expected="$2" actual="$3"
  if [[ "$actual" == "$expected" ]]; then
    echo "PASS $name"
  else
    echo "FAIL $name: expected $expected, got $actual"
    failures=$((failures + 1))
  fi
}

status() {
  curl -ks -o /dev/null -w '%{http_code}' "$@"
}

headers() {
  curl -ks -D - -o /dev/null "$1" | tr -d '\r' | tr '[:upper:]' '[:lower:]'
}

check "API health through the proxy" 200 "$(status "$base/api/v1/health")"
check "frontend page loads" 200 "$(status "$base/")"
check "login is required" 401 "$(status "$base/api/v1/me")"
check "request from a foreign origin is refused" 403 \
  "$(status -X POST -H 'Origin: https://evil.example' "$base/api/v1/auth/logout")"
check "request from the site's own origin is allowed" 204 \
  "$(status -X POST -H "Origin: $base" "$base/api/v1/auth/logout")"
oversized="$(mktemp)"
trap 'rm -f "$oversized"' EXIT
head -c 25000000 /dev/zero > "$oversized"
check "oversized upload is refused" 413 \
  "$(status -X POST -H 'Content-Type: multipart/form-data; boundary=x' --data-binary "@$oversized" "$base/api/v1/voices")"

page_headers="$(headers "$base/")"
for header in content-security-policy strict-transport-security x-content-type-options x-frame-options; do
  if grep -q "^$header:" <<<"$page_headers"; then
    echo "PASS header $header"
  else
    echo "FAIL header $header is missing"
    failures=$((failures + 1))
  fi
done

if [[ "$failures" -gt 0 ]]; then
  echo "$failures checks failed"
  exit 1
fi
echo "All checks passed"
