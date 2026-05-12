.PHONY: install backend frontend dev test build clean keycloak keycloak-down keycloak-logs keycloak-reset auth-status scrape-kenyalaw stack stack-up stack-wait stack-down stack-logs stack-reset smoke env

PY := .venv/bin/python
PIP := .venv/bin/pip

install:
	@test -d .venv || python3 -m venv .venv
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -r backend/requirements.txt 'httpx>=0.27'
	cd frontend && npm install --no-audit --no-fund

env:
	@test -f .env || cp .env.example .env
	@echo ".env present:"
	@grep -E '^(WAKILI|NEXT_PUBLIC|KEYCLOAK)' .env | sed 's/=.*/=…/'

backend:
	cd backend && PYTHONPATH=. ../$(PY) -m uvicorn wakili.main:app --host 127.0.0.1 --port 8765 --reload --reload-dir wakili

frontend:
	cd frontend && npm run dev

dev:
	@echo "Run 'make backend' in one shell and 'make frontend' in another."

test:
	cd backend && PYTHONPATH=. ../$(PY) -m unittest discover -s tests -v

build:
	cd frontend && npm run build

keycloak:
	docker compose -f infra/docker-compose.keycloak.yml up -d
	@echo "Keycloak booting at http://localhost:8080 (admin / admin)."
	@printf "Waiting for OIDC discovery"
	@for i in $$(seq 1 60); do \
	  if curl -sf http://localhost:8080/realms/wakili/.well-known/openid-configuration >/dev/null 2>&1; then \
	    echo " ready"; break; \
	  fi; \
	  printf .; sleep 2; \
	done
	@echo ""
	@echo "Realm: wakili — demo / test credentials seeded:"
	@echo "  advocate / advocate         (role: lawyer)"
	@echo "  paralegal / paralegal       (role: paralegal)"
	@echo "  nimrod / nimrod     (role: admin + lawyer)"

keycloak-down:
	docker compose -f infra/docker-compose.keycloak.yml down

keycloak-logs:
	docker compose -f infra/docker-compose.keycloak.yml logs -f keycloak

auth-status:
	@echo "Keycloak discovery:"
	@curl -sf http://localhost:8080/realms/wakili/.well-known/openid-configuration > /dev/null && echo "  ok" || echo "  (down)"
	@echo "Backend:"
	@curl -sf http://127.0.0.1:8765/api/health > /dev/null && echo "  ok" || echo "  (down)"
	@echo "Frontend /api/auth/providers:"
	@curl -sf http://localhost:3000/api/auth/providers > /dev/null && echo "  ok" || echo "  (down)"

scrape-kenyalaw:
	cd backend && PYTHONPATH=. ../$(PY) -m wakili.services.kenyalaw_scraper --pages 3 --limit 75 --delay 1.0

# Wipe the Keycloak volume so the bundled realm import runs from scratch.
# Use this if the bundled realm-wakili.json changed (new client secret,
# new mapper) and Keycloak still has the old version cached on disk.
keycloak-reset:
	docker compose -f infra/docker-compose.keycloak.yml down -v
	@$(MAKE) --no-print-directory keycloak

stack-reset: stack-down keycloak-reset stack-up stack-wait
	@echo "stack reset — fresh realm import. Now retry sign-in."

# ----------------------------------------------------------------------
# stack: one-shot end-to-end bring-up. Boots Keycloak, the FastAPI backend,
# and the Next.js frontend, all wired for SSO. The backend + frontend are
# detached via scripts/spawn.sh so they survive `make` exiting.
#
#   make stack        # boots everything
#   make stack-wait   # waits for all three to be reachable
#   make smoke        # walks the full sign-in flow end-to-end
#   make stack-logs   # tail -f all three logs
#   make stack-down   # stop everything cleanly
# ----------------------------------------------------------------------
stack: install env keycloak stack-up
	@echo ""
	@echo "Stack is up. Sign in with one of:"
	@echo "  advocate / advocate         (role: lawyer)"
	@echo "  paralegal / paralegal       (role: paralegal)"
	@echo "  nimrod / nimrod     (role: admin + lawyer)"
	@echo ""
	@echo "  Open    http://localhost:3000  →  click Sign in"
	@echo "  Verify  make smoke"
	@echo "  Logs    make stack-logs"
	@echo "  Stop    make stack-down"

stack-up:
	@echo "→ spawning backend (logs: /tmp/wakili-backend.log)"
	@pkill -9 -f 'uvicorn wakili' 2>/dev/null || true
	@bash scripts/spawn.sh backend
	@echo "→ spawning frontend (logs: /tmp/wakili-frontend.log)"
	@pkill -9 -f 'next-server' 2>/dev/null || true
	@bash scripts/spawn.sh frontend

stack-wait:
	@printf "Waiting for backend"
	@for i in $$(seq 1 30); do \
	  if curl -sf http://127.0.0.1:8765/api/health >/dev/null 2>&1; then echo " up"; break; fi; \
	  printf .; sleep 1; \
	done
	@printf "Waiting for frontend"
	@for i in $$(seq 1 120); do \
	  if curl -sf http://localhost:3000/api/auth/providers >/dev/null 2>&1; then echo " up"; break; fi; \
	  printf .; sleep 2; \
	done

stack-logs:
	@tail -f /tmp/wakili-backend.log /tmp/wakili-frontend.log

stack-down:
	-@kill -9 $$(cat /tmp/wakili-backend.pid 2>/dev/null) 2>/dev/null
	-@kill -9 $$(cat /tmp/wakili-frontend.pid 2>/dev/null) 2>/dev/null
	-@pkill -9 -f 'uvicorn wakili' 2>/dev/null
	-@pkill -9 -f 'next-server' 2>/dev/null
	-@rm -f /tmp/wakili-backend.pid /tmp/wakili-frontend.pid
	@$(MAKE) --no-print-directory keycloak-down
	@echo "stack stopped"

# Headless end-to-end verification of the running stack. Walks the actual
# OAuth code-flow against Keycloak, exercises the proxy with the resulting
# session cookie, and exits non-zero on any failure.
smoke:
	@bash scripts/smoke.sh

clean:
	rm -rf runtime backend/wakili/__pycache__ backend/wakili/**/__pycache__ backend/tests/__pycache__
	rm -rf frontend/.next
