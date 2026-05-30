"""T-009 embedding candidates: widen provider CHECK + seed candidate routes.

Adds the `bge` provider (BAAI BGE-M3) to the `provider` CHECK on model_routes + safety_suite_runs,
and seeds the two T-009 embedding candidates as `experiment` routes (per the T-009 card):
  - embedding_openai_large@2026-05-29.1  (openai:text-embedding-3-large)
  - embedding_bge_m3@2026-05-29.1        (bge:bge-m3)

These are inert, declarative metadata: nothing instantiates a provider per route, so the (not-yet-
runnable) bge route sits dormant until its benchmark is run. The actual re-embed/backfill, the
BGE-M3 runtime dependency, and Qdrant dual-index provisioning are founder-/budget-/infra-gated and
are NOT part of this migration.

Revision ID: 0004_embedding_candidates
Revises: 0003_retrieval_eval_runs
Create Date: 2026-05-29
"""

# Created by: T-009 Phase-A

from __future__ import annotations

from alembic import op

revision = "0004_embedding_candidates"
down_revision = "0003_retrieval_eval_runs"
branch_labels = None
depends_on = None

_OLD_PROVIDERS = "'anthropic','openai'"
_NEW_PROVIDERS = "'anthropic','openai','bge'"


def _drop_column_check(table: str, column: str) -> None:
    """Drop the CHECK constraint(s) on ``column`` by catalog lookup (not by assuming the name)."""
    op.execute(
        f"""
        DO $$
        DECLARE conname text;
        BEGIN
            FOR conname IN
                SELECT c.conname FROM pg_constraint c
                WHERE c.conrelid = '{table}'::regclass AND c.contype = 'c'
                  AND pg_get_constraintdef(c.oid) ILIKE '%{column}%'
            LOOP
                EXECUTE format('ALTER TABLE {table} DROP CONSTRAINT %I', conname);
            END LOOP;
        END $$;
        """
    )


def upgrade() -> None:
    for table in ("model_routes", "safety_suite_runs"):
        _drop_column_check(table, "provider")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_provider_check "
            f"CHECK (provider IN ({_NEW_PROVIDERS}));"
        )

    # Seed the two candidates as experiment routes (reuse the empty embedding prompt version).
    op.execute(
        """
        INSERT INTO model_routes (
            route_id, purpose, provider, model, prompt_version, schema_version,
            supports_prompt_cache, supports_batch, supports_json_mode,
            certification_status, created_at
        ) VALUES
          ('embedding_openai_large@2026-05-29.1', 'embedding', 'openai', 'text-embedding-3-large',
           'embedding_none@2026-05-01.1', '1.0', false, false, false, 'experiment', now()),
          ('embedding_bge_m3@2026-05-29.1', 'embedding', 'bge', 'bge-m3',
           'embedding_none@2026-05-01.1', '1.0', false, false, false, 'experiment', now())
        ON CONFLICT (route_id) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM model_routes WHERE route_id IN "
        "('embedding_openai_large@2026-05-29.1', 'embedding_bge_m3@2026-05-29.1');"
    )
    for table in ("model_routes", "safety_suite_runs"):
        _drop_column_check(table, "provider")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_provider_check "
            f"CHECK (provider IN ({_OLD_PROVIDERS}));"
        )
