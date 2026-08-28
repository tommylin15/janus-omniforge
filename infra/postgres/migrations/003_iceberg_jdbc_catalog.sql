\set ON_ERROR_STOP on

-- Apache Iceberg JDBC catalog schema (V1).  Keep it in the catalog schema so
-- the catalog role cannot access control-plane tables by default.
CREATE SCHEMA IF NOT EXISTS catalog;

CREATE TABLE IF NOT EXISTS catalog.iceberg_tables (
    catalog_name varchar(255) NOT NULL,
    table_namespace varchar(255) NOT NULL,
    table_name varchar(255) NOT NULL,
    metadata_location varchar(1000),
    previous_metadata_location varchar(1000),
    iceberg_type varchar(10),
    PRIMARY KEY (catalog_name, table_namespace, table_name)
);

CREATE TABLE IF NOT EXISTS catalog.iceberg_namespace_properties (
    catalog_name varchar(255) NOT NULL,
    namespace varchar(255) NOT NULL,
    property_key varchar(255) NOT NULL,
    property_value varchar(1000),
    PRIMARY KEY (catalog_name, namespace, property_key)
);

ALTER TABLE catalog.iceberg_tables OWNER TO janus_catalog;
ALTER TABLE catalog.iceberg_namespace_properties OWNER TO janus_catalog;
GRANT USAGE ON SCHEMA catalog TO janus_catalog;
GRANT SELECT, INSERT, UPDATE, DELETE ON catalog.iceberg_tables TO janus_catalog;
GRANT SELECT, INSERT, UPDATE, DELETE ON catalog.iceberg_namespace_properties TO janus_catalog;

-- PyIceberg SqlCatalog 0.11 emits unqualified table names. Keep the physical
-- catalog isolated while exposing only updatable compatibility views in public.
CREATE OR REPLACE VIEW public.iceberg_tables AS
SELECT catalog_name, table_namespace, table_name, metadata_location, previous_metadata_location
FROM catalog.iceberg_tables;
CREATE OR REPLACE VIEW public.iceberg_namespace_properties AS
SELECT catalog_name, namespace, property_key, property_value
FROM catalog.iceberg_namespace_properties;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.iceberg_tables TO janus_catalog;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.iceberg_namespace_properties TO janus_catalog;

INSERT INTO control.schema_migrations(version) VALUES ('003_iceberg_jdbc_catalog')
ON CONFLICT (version) DO NOTHING;
