"""Retrieval-eval suite: retrieval_eval_runs table + judge purpose + cert gate pointer.

Backs `docs/contracts/retrieval-eval-suite.md`:
  1. CREATE TABLE retrieval_eval_runs, mirroring safety_suite_runs (ADR-0004).
  2. Widen the `purpose` CHECK on model_routes AND safety_suite_runs to include
     'retrieval_eval_judge' (the Ragas-style judge route), keeping the DB in sync with
     RoutePurpose / model-route.schema.json.
  3. Add model_routes.retrieval_eval_run_id (+ FK) — the second-gate pointer alongside the
     existing safety_suite_run_id, so route certification can require BOTH a passing safety run
     and a passing retrieval-eval run.

Revision ID: 0003_retrieval_eval_runs
Revises: 0002_rls_and_app_roles
Create Date: 2026-05-29
"""

# Created by: T-009 Phase-A

from __future__ import annotations

from alembic import op

revision = "0003_retrieval_eval_runs"
down_revision = "0002_rls_and_app_roles"
branch_labels = None
depends_on = None

# Purpose value sets (kept in sync with app/domain/models/model_route.py:RoutePurpose and
# docs/schemas/model-route.schema.json).
_OLD_PURPOSES = "'query_analyzer','compose','verifier_judge','embedding'"
_NEW_PURPOSES = "'query_analyzer','compose','verifier_judge','embedding','retrieval_eval_judge'"


def _drop_purpose_check(table: str) -> None:
    """Drop the column CHECK on `purpose` by catalog lookup, not by assuming its auto-name.

    Postgres names an inline column CHECK `<table>_purpose_check`, but rather than rely on that
    (a wrong guess would silently leave a stale constraint that rejects the new value), we find
    and drop every CHECK constraint on `table` whose definition references `purpose`. On both
    target tables that is exactly the one enum constraint.
    """
    op.execute(
        f"""
        DO $$
        DECLARE conname text;
        BEGIN
            FOR conname IN
                SELECT c.conname FROM pg_constraint c
                WHERE c.conrelid = '{table}'::regclass AND c.contype = 'c'
                  AND pg_get_constraintdef(c.oid) ILIKE '%purpose%'
            LOOP
                EXECUTE format('ALTER TABLE {table} DROP CONSTRAINT %I', conname);
            END LOOP;
        END $$;
        """
    )


def upgrade() -> None:
    # 1. retrieval_eval_runs — platform table (no RLS), mirrors safety_suite_runs. route_id is
    #    stored denormalized (like safety_suite_runs stores provider/model); the integrity link is
    #    the one-way model_routes.retrieval_eval_run_id pointer added below.
    op.execute(
        """
        CREATE TABLE retrieval_eval_runs (
            retrieval_eval_run_id text PRIMARY KEY,
            route_id              text NOT NULL,
            purpose               text NOT NULL CHECK (purpose IN ('embedding','rerank')),
            config_label          text CHECK (config_label IN ('dense_only','hybrid','hybrid_rerank')),
            gold_set_tenant_id    text NOT NULL,
            gold_set_version      text NOT NULL,
            case_count            integer NOT NULL CHECK (case_count >= 0),
            scores                jsonb NOT NULL,
            passed                boolean NOT NULL,
            is_first_run          boolean NOT NULL DEFAULT false,
            judge_applied         boolean NOT NULL DEFAULT false,
            regressions           jsonb,
            initiated_by          text NOT NULL REFERENCES users(user_id),
            started_at            timestamptz NOT NULL,
            finished_at           timestamptz NOT NULL,
            created_at            timestamptz NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        "CREATE INDEX idx_retrieval_eval_purpose_passed "
        "ON retrieval_eval_runs(purpose, passed, finished_at DESC);"
    )

    # 2. Widen the purpose CHECK on both tables: drop the existing one (by catalog lookup) and
    #    add a named, widened replacement.
    for table in ("model_routes", "safety_suite_runs"):
        _drop_purpose_check(table)
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_purpose_check "
            f"CHECK (purpose IN ({_NEW_PURPOSES}));"
        )

    # 3. Second-gate pointer on model_routes.
    op.execute("ALTER TABLE model_routes ADD COLUMN retrieval_eval_run_id text;")
    op.execute(
        """
        ALTER TABLE model_routes
            ADD CONSTRAINT model_routes_retrieval_eval_run_id_fkey
            FOREIGN KEY (retrieval_eval_run_id)
            REFERENCES retrieval_eval_runs(retrieval_eval_run_id);
        """
    )


def downgrade() -> None:
    # Reverse order. Exists for symmetry; production is forward-only (db-schema.md §Migrations).
    op.execute(
        "ALTER TABLE IF EXISTS model_routes "
        "DROP CONSTRAINT IF EXISTS model_routes_retrieval_eval_run_id_fkey;"
    )
    op.execute("ALTER TABLE IF EXISTS model_routes DROP COLUMN IF EXISTS retrieval_eval_run_id;")
    for table in ("model_routes", "safety_suite_runs"):
        _drop_purpose_check(table)
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_purpose_check "
            f"CHECK (purpose IN ({_OLD_PURPOSES}));"
        )
    op.execute("DROP TABLE IF EXISTS retrieval_eval_runs;")
