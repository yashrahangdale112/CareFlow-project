/* ==========================================================================
   CareFlow : Clinical Pathway Process Mining
   FILE 1/4 - 01_schema.sql      Star schema for a hospital event log
   Target: MySQL 8.x  (PostgreSQL variant at the bottom of this file)
   ========================================================================== */

DROP DATABASE IF EXISTS careflow;
CREATE DATABASE careflow CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE careflow;

/* ---------------------- DIMENSION TABLES --------------------------------- */
CREATE TABLE dim_patient (
    patient_id   VARCHAR(20) NOT NULL,
    age          INT,
    gender       VARCHAR(10),
    PRIMARY KEY (patient_id)
) ENGINE=InnoDB;

CREATE TABLE dim_activity (
    activity       VARCHAR(60) NOT NULL,
    activity_group VARCHAR(40),          -- Front Office / Clinical / Lab / Discharge
    PRIMARY KEY (activity)
) ENGINE=InnoDB;

CREATE TABLE dim_department (
    department VARCHAR(40) NOT NULL,
    PRIMARY KEY (department)
) ENGINE=InnoDB;

CREATE TABLE dim_resource (
    resource   VARCHAR(40) NOT NULL,
    department VARCHAR(40),
    PRIMARY KEY (resource)
) ENGINE=InnoDB;

CREATE TABLE dim_date (
    date_key   DATE NOT NULL,            -- 2026-07-06
    day_name   VARCHAR(10),              -- Monday
    month_name VARCHAR(10),              -- July
    year_no    INT,
    quarter_no INT,
    is_weekend TINYINT(1) DEFAULT 0,
    PRIMARY KEY (date_key)
) ENGINE=InnoDB;

/* ---------------------- FACT TABLES -------------------------------------- */
/* One row per patient journey (case) */
CREATE TABLE fact_case (
    case_id        VARCHAR(20) NOT NULL,
    patient_id     VARCHAR(20),
    triage_level   INT,
    admission_type VARCHAR(30),
    pathway        VARCHAR(60),
    los_hours      DECIMAL(10,2),        -- length of stay = KPI target
    total_cost_inr DECIMAL(12,2),
    n_events       INT,
    is_long_stay   TINYINT(1) DEFAULT 0, -- 1 = LOS > 24 h  (ML label)
    PRIMARY KEY (case_id),
    KEY ix_case_patient (patient_id),
    KEY ix_case_pathway (pathway),
    CONSTRAINT fk_case_patient FOREIGN KEY (patient_id) REFERENCES dim_patient(patient_id)
) ENGINE=InnoDB;

/* One row per EVENT  ->  this is the process-mining event log.
   NOTE: 'timestamp' is a reserved word in MySQL, so the column is
   named event_timestamp. Keep this rule for every SQL engine.          */
CREATE TABLE fact_event (
    event_id        BIGINT NOT NULL AUTO_INCREMENT,
    case_id         VARCHAR(20) NOT NULL,
    event_index     INT NOT NULL,        -- 0,1,2 ... position inside the case
    activity        VARCHAR(60) NOT NULL,
    event_timestamp DATETIME    NOT NULL,
    resource        VARCHAR(40) NULL,
    department      VARCHAR(40) NULL,
    wait_minutes    DECIMAL(10,2) DEFAULT 0,
    service_minutes DECIMAL(10,2) DEFAULT 0,
    cost_inr        DECIMAL(12,2) DEFAULT 0,
    is_rework       TINYINT(1)    DEFAULT 0,
    PRIMARY KEY (event_id),
    UNIQUE KEY ux_case_event (case_id, event_index),
    KEY ix_event_case (case_id),
    KEY ix_event_activity (activity),
    KEY ix_event_ts (event_timestamp),
    CONSTRAINT fk_event_case     FOREIGN KEY (case_id)    REFERENCES fact_case(case_id),
    CONSTRAINT fk_event_activity FOREIGN KEY (activity)   REFERENCES dim_activity(activity)
) ENGINE=InnoDB;

/* ---------------------- POSTGRESQL VARIANT -------------------------------
CREATE DATABASE careflow;
\c careflow
CREATE TABLE fact_event (
    event_id        BIGSERIAL PRIMARY KEY,
    case_id         VARCHAR(20) NOT NULL,
    event_index     INT NOT NULL,
    activity        VARCHAR(60) NOT NULL,
    event_timestamp TIMESTAMP   NOT NULL,
    resource        VARCHAR(40),
    department      VARCHAR(40),
    wait_minutes    NUMERIC(10,2) DEFAULT 0,
    service_minutes NUMERIC(10,2) DEFAULT 0,
    cost_inr        NUMERIC(12,2) DEFAULT 0,
    is_rework       BOOLEAN DEFAULT FALSE,
    CONSTRAINT ux_case_event UNIQUE (case_id, event_index)
);
CREATE INDEX ix_event_case     ON fact_event(case_id);
CREATE INDEX ix_event_activity ON fact_event(activity);
CREATE INDEX ix_event_ts       ON fact_event(event_timestamp);
   ------------------------------------------------------------------------ */
