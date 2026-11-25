\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;
SET LOCAL lock_timeout = '5s';

-- 公共個股 AI / 確定性洞察 v2 快照表：僅存同股同截止日公共分析，嚴禁含任何私人帳本欄位。
CREATE TABLE IF NOT EXISTS control.stock_insight_v2_snapshots (
    canonical_symbol varchar(16) NOT NULL,
    as_of_date date NOT NULL,
    price_as_of_date date NOT NULL,
    session text NOT NULL CHECK (session IN ('pre_market', 'post_market', 'holiday')),
    facts_events_hash varchar(128) NOT NULL,
    prompt_version varchar(64) NOT NULL,
    model_id varchar(128),
    mode text NOT NULL CHECK (mode IN ('ai_synthesis', 'deterministic_fallback')),
    review_status text NOT NULL CHECK (review_status IN ('OK', 'WARN', 'REVIEW')),
    source_status text NOT NULL CHECK (source_status IN ('available', 'stale', 'partial', 'not_covered')),
    payload_json jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (canonical_symbol, as_of_date, session)
);

CREATE INDEX IF NOT EXISTS stock_insight_v2_cache_lookup_idx
    ON control.stock_insight_v2_snapshots(canonical_symbol, facts_events_hash, prompt_version);

REVOKE ALL ON control.stock_insight_v2_snapshots FROM PUBLIC;
GRANT SELECT ON control.stock_insight_v2_snapshots TO janus_private_api, janus_web_control;

-- PHASE: acceptance
SELECT to_regclass('control.stock_insight_v2_snapshots') IS NOT NULL,
       has_table_privilege('janus_private_api', 'control.stock_insight_v2_snapshots', 'SELECT'),
       has_table_privilege('janus_web_control', 'control.stock_insight_v2_snapshots', 'SELECT'),
       NOT has_table_privilege('janus_public_api', 'control.stock_insight_v2_snapshots', 'SELECT');

INSERT INTO control.schema_migrations(version)
VALUES ('081_ai_stock_insight_v2') ON CONFLICT DO NOTHING;
RESET ROLE;
COMMIT;
