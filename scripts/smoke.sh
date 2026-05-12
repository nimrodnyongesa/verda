#!/usr/bin/env bash
# Verda — end-to-end smoke test.
# Walks the full Authorization Code + PKCE flow against the running
# Keycloak / backend / frontend stack, exactly the way a browser would.
#
# Usage:
#   make stack        # one-time, brings everything up
#   make smoke        # this script
#
# Exits non-zero on any step that fails. Useful as a CI check + as a
# 30-second sanity-check for an operator before a demo.
set -euo pipefail

USER="${WAKILI_DEMO_USER:-advocate}"
PASS="${WAKILI_DEMO_PASSWORD:-advocate}"
KC="${WAKILI_KEYCLOAK_ISSUER:-http://localhost:8080/realms/wakili}"
APP="${WAKILI_APP_URL:-http://localhost:3000}"
API="${WAKILI_INTERNAL_API_BASE:-http://127.0.0.1:8765}"

CJ=$(mktemp)              # frontend cookies (state + session)
KC_CJ=$(mktemp)           # keycloak cookies
TMP=$(mktemp -d)
trap 'rm -rf "$CJ" "$KC_CJ" "$TMP"' EXIT

step() { printf "▸ %s\n" "$*"; }
ok()   { printf "  ✓ %s\n" "$*"; }
fail() { printf "  ✗ %s\n" "$*"; exit 1; }

step "1/8 — preflight"
curl -sf "$KC/.well-known/openid-configuration" >/dev/null \
  && ok "Keycloak discovery reachable" \
  || fail "Keycloak not reachable at $KC"
curl -sf "$API/api/health" >/dev/null \
  && ok "backend healthy" \
  || fail "backend not reachable at $API"
curl -sf "$APP/api/auth/providers" >/dev/null \
  && ok "frontend reachable" \
  || fail "frontend not reachable at $APP"

step "2/8 — anonymous request must be 401"
status=$(curl -s -o /dev/null -w "%{http_code}" "$API/api/cases")
[[ "$status" == "401" ]] && ok "anon /api/cases → 401" || fail "expected 401 from anon, got $status"

step "3/8 — /api/auth/login → state cookie + Keycloak redirect"
curl -s -c "$CJ" -o /dev/null -D "$TMP/h1" "$APP/api/auth/login?provider=keycloak"
LOC=$(grep -i '^location:' "$TMP/h1" | head -1 | sed 's/^[^h]*//' | tr -d '\r')
[[ "$LOC" == http://localhost:8080* ]] && ok "redirected to Keycloak with PKCE state" || fail "unexpected redirect: $LOC"
grep -q wakili.oauth.state "$CJ" && ok "state cookie set" || fail "state cookie missing"

step "4/8 — submit credentials to Keycloak"
curl -s -c "$KC_CJ" -L -o "$TMP/login.html" "$LOC"
ACTION=$(python3 -c "
import re, html
h = open('$TMP/login.html').read()
m = re.search(r'<form[^>]*id=\"kc-form-login\"[^>]*action=\"([^\"]+)\"', h) or re.search(r'<form[^>]*action=\"([^\"]+)\"', h)
print(html.unescape(m.group(1)) if m else '')
")
[[ -n "$ACTION" ]] || fail "couldn't find Keycloak login form"
curl -s -b "$KC_CJ" -c "$KC_CJ" -D "$TMP/h2" -o "$TMP/post.html" \
  -X POST "$ACTION" \
  --data-urlencode "username=$USER" \
  --data-urlencode "password=$PASS" \
  --data-urlencode "credentialId="
CALLBACK=$(grep -i '^location:' "$TMP/h2" | head -1 | sed 's/^[^h]*//' | tr -d '\r')
[[ "$CALLBACK" == *"$APP/api/auth/callback"* ]] && ok "Keycloak issued auth code → callback" || fail "no callback redirect: $CALLBACK"

step "5/8 — exchange code for session at /api/auth/callback"
curl -s -b "$CJ" -c "$CJ" -D "$TMP/h3" -o "$TMP/cb.html" "$CALLBACK"
status=$(head -1 "$TMP/h3" | awk '{print $2}')
[[ "$status" == "307" ]] && ok "callback set session cookie" || fail "callback returned $status"
grep -q wakili.session "$CJ" && ok "wakili.session cookie set" || fail "session cookie missing"

step "6/8 — /api/auth/me reports the signed-in user"
me=$(curl -sf -b "$CJ" "$APP/api/auth/me")
echo "  $me"
echo "$me" | grep -q '"user":{' && ok "/api/auth/me has user" || fail "/api/auth/me missing user: $me"

step "7/8 — /api/be/cases via cookie → proxy → Bearer → backend"
status=$(curl -s -o /tmp/cases.json -w "%{http_code}" -b "$CJ" "$APP/api/be/cases")
[[ "$status" == "200" ]] && ok "/api/be/cases → 200" || fail "/api/be/cases → $status"
who=$(curl -sf -b "$CJ" "$APP/api/be/auth/whoami")
echo "  whoami: $who"
echo "$who" | grep -q '"anonymous":false' && ok "backend confirms non-anon user" || fail "whoami did not confirm user: $who"

step "8/8 — POST /api/be/cases creates a case stamped with the caller as owner"
created=$(curl -s -X POST -b "$CJ" -H 'content-type: application/json' \
  --data '{"title":"Smoke-test case","jurisdiction":"ke","legal_track":"article_22_petition","description":"created by scripts/smoke.sh"}' \
  "$APP/api/be/cases")
case_id=$(python3 -c "import json,sys;print(json.load(sys.stdin)['case']['id'])" <<< "$created")
owner=$(python3 -c "import json,sys;print(json.load(sys.stdin)['case']['metadata'].get('owner_sub',''))" <<< "$created")
echo "  case#$case_id  owner_sub=$owner"
[[ -n "$case_id" && -n "$owner" ]] && ok "case#$case_id stamped with owner $owner" || fail "create did not stamp owner"

# Confirm the new IAM endpoint exposes a permission set for this user.
perms=$(curl -sf -b "$CJ" "$APP/api/be/auth/permissions")
echo "$perms" | grep -q '"permissions":' && ok "/auth/permissions returned permission set" \
  || fail "/auth/permissions response did not include permissions: $perms"

echo ""
echo "✓ all 8 stages green — sign-in + IAM works end-to-end."
