\set ON_ERROR_STOP on
SET ROLE janus_control;
SET search_path TO control;

CREATE TABLE IF NOT EXISTS coverage_membership_versions (
    coverage_tier text NOT NULL CHECK (coverage_tier IN ('market_wide','core_focus','market_macro')),
    version integer NOT NULL CHECK (version > 0),
    effective_from timestamptz NOT NULL,
    PRIMARY KEY (coverage_tier, version),
    UNIQUE (coverage_tier, effective_from)
);

INSERT INTO coverage_membership_versions(coverage_tier, version, effective_from)
SELECT coverage_tier,
       row_number() OVER (PARTITION BY coverage_tier ORDER BY effective_from),
       effective_from
FROM (SELECT DISTINCT coverage_tier, effective_from FROM coverage_memberships) snapshots
ON CONFLICT DO NOTHING;

GRANT SELECT, INSERT ON coverage_membership_versions TO janus_web_control;
INSERT INTO schema_migrations(version) VALUES ('013_membership_versions') ON CONFLICT (version) DO NOTHING;
RESET ROLE;
