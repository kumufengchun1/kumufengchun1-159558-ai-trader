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
