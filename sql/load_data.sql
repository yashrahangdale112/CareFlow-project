/* ==========================================================================
   FILE 2/4 - 02_load_data.sql   Load the CSV files into the star schema
   Put the CSVs in a folder MySQL may read, e.g. /var/lib/mysql-files/
   ========================================================================== */
USE careflow;

/* 1) clean slate (order matters because of the foreign keys) */
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE fact_event;
TRUNCATE TABLE fact_case;
TRUNCATE TABLE dim_patient;
SET FOREIGN_KEY_CHECKS = 1;

/* 2) patients */
LOAD DATA LOCAL INFILE 'data/raw/case_attributes.csv'
INTO TABLE dim_patient
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(@case_id, @patient_id, age, gender, @triage, @adm, @path, @los, @cost, @n)
SET patient_id = @patient_id;

/* 3) cases */
LOAD DATA LOCAL INFILE 'data/raw/case_attributes.csv'
INTO TABLE fact_case
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(case_id, patient_id, age, gender, triage_level, admission_type, pathway,
 los_hours, total_cost_inr, n_events)
SET is_long_stay = IF(los_hours > 24, 1, 0);

/* 4) activities + departments (build the mini dimensions from the events) */
INSERT IGNORE INTO dim_activity (activity)
SELECT DISTINCT activity FROM fact_event_stage_tmp;   -- or load events first, see below

/* 5) the event log itself */
LOAD DATA LOCAL INFILE 'data/raw/event_log.csv'
INTO TABLE fact_event
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(case_id, activity, @ts, resource, department, wait_minutes, service_minutes, cost_inr)
SET event_timestamp = STR_TO_DATE(@ts, '%Y-%m-%d %H:%i:%s.%f');

/* 6) fill the small dimensions from what we just loaded */
INSERT IGNORE INTO dim_department (department) SELECT DISTINCT department FROM fact_event WHERE department IS NOT NULL;
INSERT IGNORE INTO dim_resource (resource, department) SELECT DISTINCT resource, MIN(department) FROM fact_event WHERE resource IS NOT NULL GROUP BY resource;
INSERT IGNORE INTO dim_activity (activity) SELECT DISTINCT activity FROM fact_event;
INSERT IGNORE INTO dim_date (date_key, day_name, month_name, year_no, quarter_no, is_weekend)
SELECT DISTINCT DATE(event_timestamp), DAYNAME(event_timestamp), MONTHNAME(event_timestamp),
       YEAR(event_timestamp), QUARTER(event_timestamp),
       IF(DAYOFWEEK(event_timestamp) IN (1,7), 1, 0)
FROM fact_event;

/* 7) rebuild event_index (position inside each case) */
SET @r = 0; SET @c = '';
UPDATE fact_event e
JOIN (SELECT event_id, ROW_NUMBER() OVER (PARTITION BY case_id ORDER BY event_timestamp) - 1 AS rn FROM fact_event) x
  ON x.event_id = e.event_id
SET e.event_index = x.rn;

/* --------- PostgreSQL version of the same load -------------------------
\copy dim_patient(patient_id,age,gender)        FROM 'data/raw/case_attributes.csv' CSV HEADER
\copy fact_case   FROM 'data/raw/case_attributes.csv' CSV HEADER          -- then UPDATE is_long_stay
\copy fact_event(case_id,activity,event_timestamp,resource,department,wait_minutes,service_minutes,cost_inr)
      FROM 'data/raw/event_log.csv' CSV HEADER
------------------------------------------------------------------------- */
