PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

CREATE TABLE curated_columns (
            id INTEGER PRIMARY KEY,
            source_table TEXT NOT NULL,
            source_column TEXT NOT NULL,
            alias TEXT NOT NULL,
            description TEXT,
            data_type TEXT NOT NULL,
            is_aggregatable INTEGER NOT NULL DEFAULT 0,
            is_groupable INTEGER NOT NULL DEFAULT 1,
            default_aggregation TEXT,
            formula TEXT,
            created_at TIMESTAMP
        );

INSERT INTO curated_columns VALUES(1,'example_dataset.dim_example','id','Example ID','Primary key','STRING',0,1,NULL,NULL,'2026-01-01T00:00:00');
INSERT INTO curated_columns VALUES(2,'example_dataset.fact_example','amount','Revenue Amount','Net revenue in EUR','FLOAT64',1,0,'SUM',NULL,'2026-01-01T00:00:00');
INSERT INTO curated_columns VALUES(3,'example_dataset.dim_example','created_date','Created Date','Date the record was created','DATE',0,1,NULL,NULL,'2026-01-01T00:00:00');

CREATE TABLE join_definitions (
            id INTEGER PRIMARY KEY,
            left_table TEXT NOT NULL,
            left_column TEXT NOT NULL,
            right_table TEXT NOT NULL,
            right_column TEXT NOT NULL,
            join_type TEXT NOT NULL DEFAULT 'LEFT',
            cardinality TEXT NOT NULL DEFAULT 'many_to_one',
            created_at TIMESTAMP,
            extra_conditions TEXT
        );

INSERT INTO join_definitions VALUES(1,'example_dataset.fact_example','id','example_dataset.dim_example','id','LEFT','many_to_one','2026-01-01T00:00:00',NULL);

CREATE TABLE IF NOT EXISTS "kpi_documentation" (
  "metric_kpi" TEXT,
  "short_explanation" TEXT,
  "data_explanation" TEXT,
  "columns_used" TEXT,
  "filters_used" TEXT,
  "calculation" TEXT,
  "note" TEXT,
  "category" TEXT
);

INSERT INTO kpi_documentation VALUES('Example KPI','Short explanation of the KPI','Where the data comes from','column_a, column_b','status = active','SUM(amount)','Example note','Revenue');

CREATE TABLE concepts (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO concepts VALUES(1,'Example Concept','Description of what this concept means','2026-01-01T00:00:00');

COMMIT;
