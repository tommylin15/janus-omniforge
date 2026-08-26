SELECT current_database() = 'janus_control' AS database_ready,
       to_regclass('control.stock_master') IS NOT NULL AS control_ready,
       to_regnamespace('catalog') IS NOT NULL AS catalog_ready,
       to_regnamespace('publication') IS NOT NULL AS publication_ready,
       to_regnamespace('audit') IS NOT NULL AS audit_ready;

