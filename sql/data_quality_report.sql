SELECT
  COUNT(*) AS total_rows,
  SUM(CASE WHEN matched = 1 THEN 1 ELSE 0 END) AS matched_rows,
  ROUND(100.0 * SUM(CASE WHEN matched = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS match_rate_pct,
  SUM(CASE WHEN data_quality_flag = 'ok' THEN 1 ELSE 0 END) AS ok_rows,
  ROUND(100.0 * SUM(CASE WHEN data_quality_flag = 'ok' THEN 1 ELSE 0 END) / COUNT(*), 2) AS ok_rate_pct,
  SUM(CASE WHEN uu_lowest_ask_usd IS NULL THEN 1 ELSE 0 END) AS missing_uu_ask_rows,
  SUM(CASE WHEN uu_highest_bid_usd IS NULL THEN 1 ELSE 0 END) AS missing_uu_bid_rows,
  SUM(CASE WHEN cs_highest_bid_usd IS NULL THEN 1 ELSE 0 END) AS missing_cs_bid_rows,
  SUM(CASE WHEN instant_exit_margin_pct < 0 THEN 1 ELSE 0 END) AS negative_exit_margin_rows
FROM features;
