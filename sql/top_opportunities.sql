SELECT
  rank,
  market_hash_name,
  recommendation_label,
  ROUND(opportunity_score, 3) AS opportunity_score,
  ROUND(instant_exit_margin_pct * 100, 2) AS instant_exit_margin_pct,
  ROUND(risk_score, 3) AS risk_score,
  ROUND(cs_highest_bid_usd, 2) AS cs_highest_bid_usd,
  ROUND(uu_lowest_ask_usd, 2) AS uu_lowest_ask_usd,
  cs_vol24h,
  uu_listings,
  recommendation_reason
FROM recommendations
WHERE recommendation_label IN ('strong_candidate', 'watchlist')
ORDER BY opportunity_score DESC, instant_exit_margin_pct DESC
LIMIT 20;
