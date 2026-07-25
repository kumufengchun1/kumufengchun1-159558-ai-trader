# ATS V0.4 — Walk-Forward Backtesting

ATS V0.4 extends the verified V0.2 data/feature platform and the V0.3 label/model layer
with an auditable, expanding-window out-of-sample backtest.

## New in V0.4

- Expanding walk-forward training and prediction
- Retraining every 20 predicted sessions
- Long/cash strategy using a 55% probability threshold
- Transaction cost and slippage modeling
- Strategy and buy-and-hold equity series
- CAGR, volatility, Sharpe, drawdown, turnover, exposure, trade count, and win rate
- Persistent `backtest_runs`, `backtest_metrics`, and `backtest_daily` tables
- Backtest status reporting in GitHub Actions
- Regression tests for storage, costs, and performance calculations

See `docs/BACKTEST_SPEC_V04.md` for the exact protocol and limitations.

## Local checks

```bash
python -m pip install -r requirements-dev.txt
ruff check ats scripts tests
python -m pytest
```

## Daily workflow

The daily workflow now runs:

1. Market update
2. Feature construction and adjustment audit
3. Data and feature reports
4. Baseline training
5. Model report
6. Walk-forward backtest
7. Backtest report
8. Database commit

V0.4 remains a research system. Its results must not be treated as guaranteed returns or
personalized investment advice.

## V0.5 calibrated ensemble

V0.5 adds three-model probability ensembling, chronological sigmoid calibration, calibration
Brier-based model weights, model agreement, and long-only position tiers. The daily workflow
now trains both the logistic baseline and the calibrated ensemble, then prints the latest
ensemble decision before running the existing V0.4 walk-forward backtest.

Run locally:

```bash
python -m scripts.train_ensemble
python -m scripts.report_ensemble_status
```

See `docs/ENSEMBLE_SPEC_V05.md` for the full leakage and position-sizing rules.

## V0.6 Web Dashboard

V0.6 adds a read-only FastAPI dashboard for desktop and mobile access.

Run locally:

```bash
pip install -r requirements.txt
python -m scripts.run_web
```

Open `http://localhost:8000`. The included `Dockerfile` and `render.yaml` support deployment to
Render. GitHub Actions remains responsible for updating `data/market.db`; the web application
only reads and presents the latest committed results.
