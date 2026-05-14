SELECT
  market_hash_name,
  recommendation_label,
  ROUND(cs_liquidity_score, 3) AS cs_liquidity_score,
  cs_vol24h,
  cs_bid_depth,
  uu_listings,
  uu_bid_depth,
  ROUND(instant_exit_margin_pct * 100, 2) AS instant_exit_margin_pct,
  ROUND(opportunity_score, 3) AS opportunity_score
FROM features
WHERE recommendation_label != 'avoid'
ORDER BY cs_liquidity_score DESC, opportunity_score DESC
LIMIT 20;
