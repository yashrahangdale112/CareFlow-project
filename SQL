/* FILE 4/4 - 04_views.sql : save the heavy CTEs as reusable views */
USE careflow;
CREATE OR REPLACE VIEW v_dfg_edges AS
SELECT case_id, activity AS source_activity, event_index,
       LEAD(activity) OVER (PARTITION BY case_id ORDER BY event_index) AS target_activity
FROM fact_event;

CREATE OR REPLACE VIEW v_case_trace AS
SELECT case_id, GROUP_CONCAT(activity, ' -> ') AS variant
FROM (SELECT case_id, event_index, activity FROM fact_event ORDER BY case_id, event_index) t
GROUP BY case_id;

CREATE OR REPLACE VIEW v_bottleneck AS
SELECT activity, COUNT(*) AS occurrences, ROUND(AVG(wait_minutes),1) AS avg_wait_min,
       ROUND(AVG(service_minutes),1) AS avg_service_min
FROM fact_event GROUP BY activity;

CREATE OR REPLACE VIEW v_powerbi_export AS          -- flat table for Power BI / Tableau
SELECT e.case_id, e.event_index, e.activity, e.event_timestamp, e.resource, e.department,
       e.wait_minutes, e.service_minutes, e.cost_inr, e.is_rework,
       c.age, c.gender, c.triage_level, c.admission_type, c.pathway,
       c.los_hours, c.total_cost_inr, c.is_long_stay
FROM fact_event e JOIN fact_case c USING (case_id);
