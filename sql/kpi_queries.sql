/* ==========================================================================
   FILE 3/4 - 03_kpi_queries.sql
   All KPIs used in the report + dashboard.  ANSI SQL = works in
   MySQL 8, PostgreSQL 13+ and SQLite 3.25+ (window functions needed).
   ========================================================================== */
USE careflow;

/* ---- Q1  Overall KPI card ---------------------------------------------- */
SELECT COUNT(DISTINCT case_id)                       AS cases,
       COUNT(*)                                      AS events,
       COUNT(DISTINCT activity)                      AS activities,
       ROUND(AVG(los_hours),2)                       AS avg_los_h,
       ROUND(SUM(total_cost_inr),0)                  AS total_cost_inr,
       ROUND(AVG(total_cost_inr),0)                  AS avg_cost_per_case,
       SUM(is_long_stay)                             AS long_stay_cases,
       ROUND(100.0*SUM(is_long_stay)/COUNT(*),2)     AS long_stay_pct
FROM fact_case;

/* ---- Q2  Directly-Follows Graph (process discovery at SQL level) ------- */
WITH ordered AS (
    SELECT case_id, event_index, activity,
           LEAD(activity) OVER (PARTITION BY case_id ORDER BY event_index) AS next_activity
    FROM fact_event
)
SELECT activity AS source_activity,
       next_activity AS target_activity,
       COUNT(*) AS edge_count,
       ROUND(100.0*COUNT(*)/(SELECT COUNT(*) FROM fact_event WHERE event_index > 0),2) AS edge_pct
FROM ordered
WHERE next_activity IS NOT NULL
GROUP BY activity, next_activity
HAVING COUNT(*) >= 3
ORDER BY edge_count DESC;

/* ---- Q3  Pathway variants (trace variants) ----------------------------- */
WITH trace AS (
    SELECT case_id, GROUP_CONCAT(activity, ' -> ') AS variant   -- PG: string_agg(activity,' -> ')
    FROM (SELECT case_id, event_index, activity FROM fact_event ORDER BY case_id, event_index) t
    GROUP BY case_id
)
SELECT variant, COUNT(*) AS cases,
       ROUND(100.0*COUNT(*)/(SELECT COUNT(DISTINCT case_id) FROM fact_event),2) AS pct_of_cases,
       RANK() OVER (ORDER BY COUNT(*) DESC) AS variant_rank
FROM trace GROUP BY variant ORDER BY cases DESC;

/* ---- Q4  BOTTLENECKS : waiting time per activity ----------------------- */
SELECT activity,
       COUNT(*)                          AS occurrences,
       ROUND(AVG(wait_minutes),1)        AS avg_wait_min,
       ROUND(SUM(wait_minutes)/60,1)     AS total_wait_hours,
       ROUND(AVG(service_minutes),1)     AS avg_service_min,
       ROUND(MAX(wait_minutes),1)        AS worst_wait_min
FROM fact_event
GROUP BY activity
ORDER BY avg_wait_min DESC;

/* ---- Q5  REWORK / repeated activities ---------------------------------- */
SELECT activity,
       SUM(is_rework)                                    AS rework_events,
       ROUND(100.0*SUM(is_rework)/COUNT(*),2)            AS rework_pct
FROM fact_event
GROUP BY activity
HAVING COUNT(*) > 50
ORDER BY rework_pct DESC;

/* ---- Q6  Department cost + volume -------------------------------------- */
SELECT department,
       COUNT(*)                        AS events,
       COUNT(DISTINCT case_id)         AS cases,
       ROUND(SUM(cost_inr),0)          AS total_cost_inr,
       ROUND(AVG(cost_inr),0)          AS avg_cost_per_event,
       ROUND(AVG(service_minutes),1)   AS avg_service_min
FROM fact_event
GROUP BY department
ORDER BY total_cost_inr DESC;

/* ---- Q7  Resource workload -------------------------------------------- */
SELECT resource, department, COUNT(*) AS events_handled,
       ROUND(SUM(service_minutes)/60,1) AS busy_hours,
       ROUND(AVG(wait_minutes),1)       AS avg_wait_created
FROM fact_event
WHERE resource IS NOT NULL
GROUP BY resource, department
ORDER BY busy_hours DESC
LIMIT 15;

/* ---- Q8  Hospital load heat-map : weekday x hour ---------------------- */
SELECT CASE DAYOFWEEK(event_timestamp) WHEN 2 THEN 'Mon' WHEN 3 THEN 'Tue' WHEN 4 THEN 'Wed'
            WHEN 5 THEN 'Thu' WHEN 6 THEN 'Fri' WHEN 7 THEN 'Sat' ELSE 'Sun' END AS weekday,
       HOUR(event_timestamp) AS hour_of_day,          -- SQLite: strftime('%H',event_timestamp)
       COUNT(*) AS events
FROM fact_event
GROUP BY 1,2
ORDER BY events DESC;

/* ---- Q9  Length-of-stay buckets --------------------------------------- */
SELECT CASE WHEN los_hours < 6  THEN '01 < 6 h'
            WHEN los_hours < 12 THEN '02 6-12 h'
            WHEN los_hours < 18 THEN '03 12-18 h'
            WHEN los_hours < 24 THEN '04 18-24 h'
            ELSE                      '05 > 24 h (long stay)' END AS los_bucket,
       COUNT(*) AS cases, ROUND(AVG(total_cost_inr),0) AS avg_cost_inr
FROM fact_case GROUP BY los_bucket ORDER BY los_bucket;

/* ---- Q10 Conformance proxy : share of cases on a "happy path" ---------- */
WITH trace AS (SELECT case_id, COUNT(*) AS n, GROUP_CONCAT(activity,' -> ') AS variant
               FROM (SELECT case_id,event_index,activity FROM fact_event ORDER BY case_id,event_index) t
               GROUP BY case_id),
     happy AS (SELECT variant FROM trace GROUP BY variant ORDER BY COUNT(*) DESC LIMIT 5)
SELECT COUNT(*) AS total_cases,
       SUM(CASE WHEN variant IN (SELECT variant FROM happy) THEN 1 ELSE 0 END) AS cases_on_top5_variant,
       ROUND(100.0*SUM(CASE WHEN variant IN (SELECT variant FROM happy) THEN 1 ELSE 0 END)/COUNT(*),2) AS conformance_pct
FROM trace;

/* ---- Q11 Long-stay driver check : does triage level matter? ------------ */
SELECT triage_level, COUNT(*) AS cases, ROUND(AVG(los_hours),2) AS avg_los_h,
       ROUND(AVG(total_cost_inr),0) AS avg_cost, SUM(is_long_stay) AS long_stay
FROM fact_case GROUP BY triage_level ORDER BY triage_level;

/* ---- Q12 Waiting time by shift (derived) ------------------------------ */
SELECT CASE WHEN HOUR(event_timestamp) < 12 THEN 'Morning'
            WHEN HOUR(event_timestamp) < 17 THEN 'Afternoon'
            WHEN HOUR(event_timestamp) < 21 THEN 'Evening'
            ELSE 'Night' END AS shift,
       COUNT(*) AS events, ROUND(AVG(wait_minutes),1) AS avg_wait_min
FROM fact_event GROUP BY shift ORDER BY avg_wait_min DESC;
