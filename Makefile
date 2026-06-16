.PHONY: dev worker test safety lint typecheck migrate up down install retrieval-eval-run \
	check-docs-index verify-enums check-safety-coverage codegen codegen-check

install:
	(cd backend && uv sync)
	(cd web && npm install)

dev:
	docker compose -f infrastructure/docker-compose.yml up -d
	(cd backend && uv run uvicorn app.main:app --reload --port 8000) &
	(cd backend && uv run arq app.workers.retention_worker.WorkerSettings) &
	(cd web && npm run dev)

# Retention worker (arq). Standalone runner for local verification / observing the sweep.
# Needs the compose deps up (`make up`) + migrations (`make migrate`); see docs/runbooks/retention-worker.md.
worker:
	(cd backend && uv run arq app.workers.retention_worker.WorkerSettings)

test:
	(cd backend && uv run pytest -q)
	@echo "web: no JS unit tests configured yet (UI migrated to Vite/TanStack)"

safety:
	pytest tests/safety -v

lint:
	(cd backend && uv run ruff check . && uv run mypy app)
	(cd web && npm run lint)

typecheck: lint

migrate:
	(cd backend && uv run alembic upgrade head)

up:
	docker compose -f infrastructure/docker-compose.yml up -d

down:
	docker compose -f infrastructure/docker-compose.yml down

# Retrieval-eval operator run (T-009 Phase-A). Offline + free by default; flags add DB/owner steps.
#   make retrieval-eval-run                                   # offline metrics report (no spend)
#   make retrieval-eval-run GOLD_SET=t/v ROUTE_ID=r CONFIG=hybrid
#   make retrieval-eval-run PERSIST=1                         # also write the run row (needs DB)
#   make retrieval-eval-run PERSIST=1 ATTACH=1 SAFETY_RUN_ID=ssr_x  # owner: link both cert gates
#   make retrieval-eval-run ESTABLISH_BASELINE=1             # owner: pin a passing run as baseline
#   make retrieval-eval-run LIVE=1 COLLECTION=chunks_candidate     # paid live run (founder/infra)
#   RETRIEVAL_EVAL_RUN_JUDGE=1 make retrieval-eval-run JUDGE=1     # paid LLM-judge path (gated)
GOLD_SET ?= tenant_smoke/2026-05-29.1
ROUTE_ID ?= embedding_openai_large@2026-05-29.1
CONFIG ?= dense_only

retrieval-eval-run:
	(cd backend && uv run python ../scripts/run_retrieval_eval.py \
		--gold-set $(GOLD_SET) --route-id $(ROUTE_ID) --config $(CONFIG) \
		$(if $(LIVE),,--offline) \
		$(if $(COLLECTION),--collection $(COLLECTION),) \
		$(if $(PERSIST),--persist,) \
		$(if $(ATTACH),--attach,) \
		$(if $(SAFETY_RUN_ID),--safety-run-id $(SAFETY_RUN_ID),) \
		$(if $(ESTABLISH_BASELINE),--establish-baseline,) \
		$(if $(JUDGE),--judge,))

# REC-003: fail if docs/{adr,contracts,schemas}/ drifts from docs/DOCS_INDEX.md. Stdlib only.
check-docs-index:
	python3 scripts/check_docs_index.py

# Enum-parity gate: fail if the AnswerMode / ProgressVariant.stage enum mirrors drift across
# docs/schemas, docs/api/openapi.yaml, and the backend Pydantic Literal. Requires PyYAML.
verify-enums:
	python3 scripts/verify_openapi_enums.py

# Safety-config coverage report (T-007 aid): which sensitivity/riskFlag rules + Greek variants are
# present vs missing. Exits non-zero only when an English rule is missing. Requires PyYAML.
check-safety-coverage:
	python3 scripts/check_safety_coverage.py

# REC-009 (scaffold): regenerate / drift-check the schema-derived artifacts. Tools run ephemerally
# (uvx / pnpm dlx) — no manifest changes, network egress only. No artifacts are generated yet; see
# scripts/codegen/README.md for the enable procedure.
codegen:
	scripts/codegen/generate.sh

codegen-check:
	scripts/codegen/generate.sh --check
