\set ON_ERROR_STOP on

SET ROLE janus_control;
SET search_path TO control, public;

DO $migration$
DECLARE
    existing_value jsonb;
    merged_holidays jsonb;
BEGIN
    IF EXISTS (
        SELECT 1 FROM control.schema_migrations
        WHERE version = '029_twse_2026_holiday_overrides'
    ) THEN
        RETURN;
    END IF;

    SELECT value_json
      INTO existing_value
      FROM control.admin_settings
     WHERE setting_key = 'schedule'
     FOR UPDATE;

    IF existing_value IS NULL THEN
        RAISE EXCEPTION 'schedule admin setting is required before applying TWSE holiday overrides';
    END IF;

    SELECT jsonb_agg(day ORDER BY day)
      INTO merged_holidays
      FROM (
        SELECT DISTINCT day
          FROM (
            SELECT value AS day
              FROM jsonb_array_elements_text(
                  COALESCE(existing_value->'holiday_overrides', '[]'::jsonb)
              ) AS current(value)
            UNION ALL
            SELECT day
              FROM (VALUES
                ('2026-01-01'),
                ('2026-02-12'),
                ('2026-02-13'),
                ('2026-02-15'),
                ('2026-02-16'),
                ('2026-02-17'),
                ('2026-02-18'),
                ('2026-02-19'),
                ('2026-02-20'),
                ('2026-02-27'),
                ('2026-02-28'),
                ('2026-04-03'),
                ('2026-04-04'),
                ('2026-04-05'),
                ('2026-04-06'),
                ('2026-05-01'),
                ('2026-06-19'),
                ('2026-09-25'),
                ('2026-09-28'),
                ('2026-10-09'),
                ('2026-10-10'),
                ('2026-10-25'),
                ('2026-10-26'),
                ('2026-12-25')
              ) AS official(day)
          ) AS combined
      ) AS deduplicated;

    UPDATE control.admin_settings
       SET value_json = jsonb_set(existing_value, '{holiday_overrides}', merged_holidays, true),
           version = version + 1,
           updated_at = now(),
           updated_by = 'migration-029-twse-2026-calendar'
     WHERE setting_key = 'schedule';

    INSERT INTO control.admin_audit(
        action, resource, resource_key, actor, detail_json, created_at
    ) VALUES (
        'update',
        'setting',
        'schedule',
        'migration-029-twse-2026-calendar',
        jsonb_build_object(
            'reason', 'repair dev Pilot trading-day correction from official TWSE 2026 holiday schedule',
            'holiday_override_count', jsonb_array_length(merged_holidays),
            'preserved_existing_overrides', true
        ),
        now()
    );

    INSERT INTO control.schema_migrations(version)
    VALUES ('029_twse_2026_holiday_overrides');
END
$migration$;

RESET ROLE;
