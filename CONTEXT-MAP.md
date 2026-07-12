# Context Map

## Contexts

- [Capitol Gains Landing](./landing/CONTEXT.md) — marketing page converting
  visitors into email subscribers for trade alerts
- Congress tracker (`congress/`, `docs/trades.html`) — pipeline and site for
  official STOCK Act disclosures; no CONTEXT.md yet (conventions live in
  CLAUDE.md and congress/README.md)
- World Cup predictor (`predictor/`, `docs/index.html`) — match forecasting;
  no CONTEXT.md yet (conventions live in CLAUDE.md)

## Relationships

- **Congress tracker → Landing**: the tracker's generated data
  (`docs/data/congress-trades.json`) is the sole source for the landing
  page's disclosure feed and stats; the landing never fabricates rows
  (see landing/docs/adr/0001).
