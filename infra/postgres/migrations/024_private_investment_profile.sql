\set ON_ERROR_STOP on

-- Existing dev databases may have private.users owned by the bootstrap superuser.
GRANT REFERENCES ON private.users TO janus_control;

SET ROLE janus_control;

CREATE TABLE IF NOT EXISTS private.investment_profiles (
    user_id uuid PRIMARY KEY REFERENCES private.users(user_id) ON DELETE RESTRICT,
    risk_tolerance text NOT NULL CHECK (risk_tolerance IN ('conservative','moderate','aggressive')),
    investment_horizon text NOT NULL CHECK (investment_horizon IN ('short','medium','long')),
    primary_goal text NOT NULL CHECK (primary_goal IN ('capital_preservation','income','growth','retirement')),
    minimum_cash_ratio numeric(5,4) NOT NULL CHECK (minimum_cash_ratio BETWEEN 0 AND 1),
    ai_context_opt_in boolean NOT NULL DEFAULT false,
    version integer NOT NULL CHECK (version > 0),
    idempotency_key varchar(128) NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(user_id, idempotency_key)
);

RESET ROLE;

REVOKE REFERENCES ON private.users FROM janus_control;

GRANT SELECT, INSERT, UPDATE ON private.investment_profiles TO janus_private_api;
GRANT SELECT, DELETE ON private.investment_profiles TO janus_private_pipeline;
REVOKE ALL ON private.investment_profiles FROM PUBLIC;

INSERT INTO control.schema_migrations(version) VALUES ('024_private_investment_profile')
ON CONFLICT(version) DO NOTHING;
