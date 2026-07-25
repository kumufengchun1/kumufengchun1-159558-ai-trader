# ATS V0.6 Web Dashboard

## Goal

Provide a mobile-friendly read-only dashboard backed directly by `data/market.db`.
The web process never downloads market data and never trains a model. GitHub Actions remains
the only writer; the dashboard only presents committed results.

## Routes

- `/` dashboard
- `/health` deployment health check
- `/api/dashboard` machine-readable snapshot

## Panels

- latest calibrated ensemble decision
- probability, confidence, agreement, and suggested research position
- latest data/model/backtest run status
- walk-forward strategy and benchmark equity curves
- core backtest metrics
- ensemble component weights
- latest data quality status for every asset

## Deployment

The repository includes a Dockerfile and `render.yaml`. Render can deploy the service directly
from GitHub. Because the SQLite database is committed by the daily workflow, each successful
push triggers a dashboard refresh through Render auto-deploy.

## Safety boundary

This remains a research dashboard. It does not connect to a broker, place orders, or represent
personalized investment advice.
