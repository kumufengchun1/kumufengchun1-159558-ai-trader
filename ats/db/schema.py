SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS assets (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    market TEXT NOT NULL,
    timezone TEXT NOT NULL,
    currency TEXT NOT NULL,
    required INTEGER NOT NULL,
    note TEXT
);

CREATE TABLE IF NOT EXISTS daily_prices (
    asset_symbol TEXT NOT NULL REFERENCES assets(symbol),
    trading_date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL NOT NULL,
    adj_close REAL,
    volume REAL,
    provider TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    is_cached INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (asset_symbol, trading_date)
);

CREATE INDEX IF NOT EXISTS idx_prices_symbol_date
ON daily_prices(asset_symbol, trading_date);

CREATE TABLE IF NOT EXISTS update_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    assets_total INTEGER NOT NULL DEFAULT 0,
    assets_updated INTEGER NOT NULL DEFAULT 0,
    assets_failed INTEGER NOT NULL DEFAULT 0,
    message TEXT
);

CREATE TABLE IF NOT EXISTS provider_failures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES update_runs(id),
    asset_symbol TEXT NOT NULL,
    provider TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    error TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS data_quality (
    run_id INTEGER NOT NULL REFERENCES update_runs(id),
    asset_symbol TEXT NOT NULL,
    latest_date TEXT,
    row_count INTEGER NOT NULL,
    status TEXT NOT NULL,
    details TEXT,
    PRIMARY KEY (run_id, asset_symbol)
);

CREATE TABLE IF NOT EXISTS feature_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_symbol TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    target_rows INTEGER NOT NULL DEFAULT 0,
    feature_rows INTEGER NOT NULL DEFAULT 0,
    message TEXT
);

CREATE TABLE IF NOT EXISTS alignment_map (
    target_symbol TEXT NOT NULL,
    target_date TEXT NOT NULL,
    source_symbol TEXT NOT NULL,
    source_date TEXT,
    lag_calendar_days INTEGER,
    alignment_rule TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    PRIMARY KEY (target_symbol, target_date, source_symbol)
);

CREATE INDEX IF NOT EXISTS idx_alignment_target_date
ON alignment_map(target_symbol, target_date);

CREATE TABLE IF NOT EXISTS feature_values (
    target_symbol TEXT NOT NULL,
    feature_date TEXT NOT NULL,
    feature_name TEXT NOT NULL,
    value REAL,
    source_symbol TEXT,
    source_date TEXT,
    feature_version TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    PRIMARY KEY (target_symbol, feature_date, feature_name, feature_version)
);

CREATE INDEX IF NOT EXISTS idx_features_target_date
ON feature_values(target_symbol, feature_date);

CREATE TABLE IF NOT EXISTS adjustment_audit (
    asset_symbol TEXT NOT NULL,
    trading_date TEXT NOT NULL,
    close_to_adj_ratio REAL,
    prior_ratio REAL,
    ratio_change REAL,
    raw_return REAL,
    adjusted_return REAL,
    status TEXT NOT NULL,
    details TEXT,
    audited_at TEXT NOT NULL,
    PRIMARY KEY (asset_symbol, trading_date)
);
"""

# V0.3 schema is appended separately so existing databases migrate in place.
MODEL_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS label_values (
    target_symbol TEXT NOT NULL,
    label_date TEXT NOT NULL,
    label_name TEXT NOT NULL,
    value REAL,
    horizon_sessions INTEGER NOT NULL,
    label_version TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    PRIMARY KEY (target_symbol, label_date, label_name, label_version)
);

CREATE INDEX IF NOT EXISTS idx_labels_target_date
ON label_values(target_symbol, label_date);

CREATE TABLE IF NOT EXISTS model_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_symbol TEXT NOT NULL,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    feature_version TEXT NOT NULL,
    label_version TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    train_start TEXT,
    train_end TEXT,
    test_start TEXT,
    test_end TEXT,
    train_rows INTEGER NOT NULL DEFAULT 0,
    test_rows INTEGER NOT NULL DEFAULT 0,
    message TEXT
);

CREATE TABLE IF NOT EXISTS model_metrics (
    model_run_id INTEGER NOT NULL REFERENCES model_runs(id),
    metric_name TEXT NOT NULL,
    metric_value REAL,
    sample_name TEXT NOT NULL,
    PRIMARY KEY (model_run_id, metric_name, sample_name)
);

CREATE TABLE IF NOT EXISTS model_coefficients (
    model_run_id INTEGER NOT NULL REFERENCES model_runs(id),
    feature_name TEXT NOT NULL,
    coefficient REAL NOT NULL,
    PRIMARY KEY (model_run_id, feature_name)
);

CREATE TABLE IF NOT EXISTS predictions (
    model_run_id INTEGER NOT NULL REFERENCES model_runs(id),
    target_symbol TEXT NOT NULL,
    prediction_date TEXT NOT NULL,
    probability_up REAL NOT NULL,
    predicted_class INTEGER NOT NULL,
    actual_class INTEGER,
    actual_return REAL,
    sample_name TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    PRIMARY KEY (model_run_id, prediction_date, sample_name)
);

CREATE INDEX IF NOT EXISTS idx_predictions_target_date
ON predictions(target_symbol, prediction_date);

CREATE TABLE IF NOT EXISTS decision_journal (
    target_symbol TEXT NOT NULL,
    decision_date TEXT NOT NULL,
    model_run_id INTEGER NOT NULL REFERENCES model_runs(id),
    probability_up REAL NOT NULL,
    signal TEXT NOT NULL,
    confidence REAL NOT NULL,
    actual_return REAL,
    outcome TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (target_symbol, decision_date, model_run_id)
);
"""

BACKTEST_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS backtest_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_symbol TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    strategy_version TEXT NOT NULL,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    feature_version TEXT NOT NULL,
    label_version TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    min_train_rows INTEGER NOT NULL,
    rebalance_rows INTEGER NOT NULL,
    transaction_cost_bps REAL NOT NULL,
    slippage_bps REAL NOT NULL,
    message TEXT
);

CREATE TABLE IF NOT EXISTS backtest_metrics (
    backtest_run_id INTEGER NOT NULL REFERENCES backtest_runs(id),
    metric_name TEXT NOT NULL,
    metric_value REAL,
    series_name TEXT NOT NULL,
    PRIMARY KEY (backtest_run_id, metric_name, series_name)
);

CREATE TABLE IF NOT EXISTS backtest_daily (
    backtest_run_id INTEGER NOT NULL REFERENCES backtest_runs(id),
    trading_date TEXT NOT NULL,
    probability_up REAL NOT NULL,
    position REAL NOT NULL,
    prior_position REAL NOT NULL,
    turnover REAL NOT NULL,
    gross_return REAL NOT NULL,
    transaction_cost REAL NOT NULL,
    net_return REAL NOT NULL,
    benchmark_return REAL NOT NULL,
    strategy_equity REAL NOT NULL,
    benchmark_equity REAL NOT NULL,
    train_start TEXT NOT NULL,
    train_end TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    PRIMARY KEY (backtest_run_id, trading_date)
);

CREATE INDEX IF NOT EXISTS idx_backtest_daily_run_date
ON backtest_daily(backtest_run_id, trading_date);
"""

ENSEMBLE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS ensemble_weights (
    model_run_id INTEGER NOT NULL REFERENCES model_runs(id),
    component_name TEXT NOT NULL,
    calibration_brier REAL,
    ensemble_weight REAL NOT NULL,
    PRIMARY KEY (model_run_id, component_name)
);

CREATE TABLE IF NOT EXISTS ensemble_component_predictions (
    model_run_id INTEGER NOT NULL REFERENCES model_runs(id),
    prediction_date TEXT NOT NULL,
    component_name TEXT NOT NULL,
    raw_probability REAL NOT NULL,
    calibrated_probability REAL NOT NULL,
    PRIMARY KEY (model_run_id, prediction_date, component_name)
);

CREATE TABLE IF NOT EXISTS ensemble_decisions (
    model_run_id INTEGER NOT NULL REFERENCES model_runs(id),
    target_symbol TEXT NOT NULL,
    prediction_date TEXT NOT NULL,
    probability_up REAL NOT NULL,
    agreement REAL NOT NULL,
    confidence REAL NOT NULL,
    position REAL NOT NULL,
    signal TEXT NOT NULL,
    actual_return REAL,
    outcome TEXT,
    generated_at TEXT NOT NULL,
    PRIMARY KEY (model_run_id, prediction_date)
);

CREATE INDEX IF NOT EXISTS idx_ensemble_decisions_target_date
ON ensemble_decisions(target_symbol, prediction_date);
"""
