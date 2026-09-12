-- TRANSIT (example) — the line register, loaded from the declared lookup.
-- The register is the SOURCE OF TRUTH for which line codes exist. It is looked up, never built:
-- no query may assemble a line code from parts (see MAC008 / check_no_fabricated_identifiers).
SELECT
    line_code,
    line_label,
    mode
FROM transit_raw.line_lookup
