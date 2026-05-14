SELECT
  recommendation_label,
  COUNT(*) AS row_count,
  ROUND(AVG(opportunity_score), 3) AS avg_opportunity_score,
  ROUND(AVG(instant_exit_margin_pct) * 100, 2) AS avg_instant_exit_margin_pct,
  ROUND(AVG(risk_score), 3) AS avg_risk_score
FROM features
GROUP BY recommendation_label
ORDER BY row_count DESC;
