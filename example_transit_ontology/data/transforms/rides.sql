-- TRANSIT (example) — the rides pipeline: boarding events -> one row per (line_code, service_month).
--
-- TWO impurities are resolved here, and both are DECLARED in rides.yaml rather than left implicit:
--   1. the raw feed carries a free-text line_label; the line CODE is resolved through the register,
--      never derived from the label by string surgery
--   2. duration arrives in seconds; the ontology's unit is minutes
SELECT
    r.line_code                                  AS line_code,
    date_trunc('month', CAST(e.boarded_at AS date)) AS service_month,
    COUNT(*)                                     AS ride_count,
    SUM(e.duration_secs) / 60.0                  AS ride_minutes
FROM transit_raw.ride_events_raw AS e
JOIN transit.line_register AS r
  ON e.line_label = r.line_label
GROUP BY
    r.line_code,
    date_trunc('month', CAST(e.boarded_at AS date))
