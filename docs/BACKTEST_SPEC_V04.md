# ATS V0.4 Walk-Forward Backtest Specification

## Purpose

V0.4 measures whether the V0.3 logistic baseline has value on data that was not used to
fit each prediction. It is a research backtest, not a promise of future performance.

## Time protocol

- Sort all joined feature and label rows by `feature_date`.
- Use an expanding training window.
- Require at least 120 historical labeled sessions before the first prediction.
- Retrain every 20 predicted sessions.
- Each prediction block is strictly later than its training data.
- No random train/test shuffle is permitted.

## Strategy

- Long 159558 when `probability_up >= 0.55`.
- Otherwise hold cash.
- Short selling is disabled in V0.4.
- Position size is either 0% or 100%; sizing models are deferred.

## Costs

- Transaction cost: 3 basis points per one-way position change.
- Slippage: 2 basis points per one-way position change.
- Total modeled one-way cost: 5 basis points.
- Cost is charged on absolute turnover, including entry and exit.

## Stored outputs

- One `backtest_runs` record per execution.
- Daily probabilities, positions, turnover, costs, returns, equity, and training window.
- Strategy and buy-and-hold benchmark metrics.

## Metrics

- Total return
- CAGR
- Annualized volatility
- Sharpe ratio without a risk-free-rate adjustment
- Maximum drawdown
- Positive-day rate
- Strategy exposure
- Turnover
- Position-change count
- Win rate while invested

## Known limitations

- The model is still logistic regression only.
- Costs are simplified and do not yet include minimum commission or liquidity impact.
- The label uses close-to-close adjusted return; intraday execution is not modeled.
- Survivorship and source-data revisions remain possible.
