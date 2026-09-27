\set ON_ERROR_STOP on
SET ROLE janus_control;

CREATE TABLE IF NOT EXISTS control.liquid_500_versions (
    version bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    week_start date NOT NULL,
    effective_from timestamptz NOT NULL UNIQUE,
    reason text NOT NULL CHECK (btrim(reason) <> ''),
    actor text NOT NULL CHECK (btrim(actor) <> ''),
    source_snapshot jsonb NOT NULL CHECK (jsonb_typeof(source_snapshot) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS control.liquid_500_members (
    version bigint NOT NULL REFERENCES control.liquid_500_versions(version) ON DELETE RESTRICT,
    rank integer NOT NULL CHECK (rank BETWEEN 1 AND 500),
    symbol text NOT NULL REFERENCES control.stock_master(symbol) ON DELETE RESTRICT,
    volume_shares bigint,
    turnover_twd numeric(24,2),
    manual_override boolean NOT NULL DEFAULT false,
    PRIMARY KEY (version, symbol),
    UNIQUE (version, rank),
    CHECK (volume_shares IS NULL OR volume_shares >= 0),
    CHECK (turnover_twd IS NULL OR turnover_twd >= 0)
);

GRANT SELECT, INSERT ON control.liquid_500_versions, control.liquid_500_members TO janus_web_control;
GRANT USAGE, SELECT ON SEQUENCE control.liquid_500_versions_version_seq TO janus_web_control;
GRANT SELECT ON control.liquid_500_versions, control.liquid_500_members TO janus_private_api;
INSERT INTO control.schema_migrations(version) VALUES ('032_liquid_500') ON CONFLICT DO NOTHING;
RESET ROLE;
