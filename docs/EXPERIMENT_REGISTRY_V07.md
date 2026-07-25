# Experiment Registry V0.7

V0.7 adds a persistent registry that links model and backtest results to their source run,
configuration, metrics, data version, and Git commit.

## Stored objects

Each experiment is stored in SQLite tables:

- `experiments`: identity, source run, versions, parameters, metadata, and provenance.
- `experiment_metrics`: normalized metrics grouped by sample or series.

A JSON manifest is also written to `data/experiments/` for review and version control.

## Experiment identifiers

Identifiers are deterministic for a database run:

- `EXP-MODEL-000001`
- `EXP-BACKTEST-000001`

Registering the same source run again updates the existing record rather than creating a
duplicate.

## Automatic registration

The daily pipeline registers experiments after these successful commands:

```bash
python -m scripts.train_baseline
python -m scripts.train_ensemble
python -m scripts.run_backtest
```

Inspect the ten most recent records with:

```bash
python -m scripts.report_experiments
```

## Provenance fields

The registry captures:

- target symbol;
- model, strategy, feature, and label versions;
- train/test or backtest date ranges;
- run parameters and additional metadata;
- metrics by sample or series;
- latest target price date as `data_version`;
- current Git commit when available.

`git_commit` is recorded as `unknown` when the code is not running inside a Git checkout.
