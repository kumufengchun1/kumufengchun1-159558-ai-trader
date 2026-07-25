# Changelog

## 0.7.0

- Add persistent `experiments` and `experiment_metrics` tables.
- Add deterministic model and backtest experiment identifiers.
- Capture Git commit, data version, configuration, metadata, and normalized metrics.
- Export experiment manifests to `data/experiments/`.
- Register baseline, ensemble, and walk-forward runs automatically.
- Add an experiment registry reporting command and daily workflow step.
- Add idempotency and parameter-capture tests.
