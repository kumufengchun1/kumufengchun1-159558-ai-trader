from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ats.db.repository import Repository


@dataclass(frozen=True)
class ExperimentRecord:
    experiment_id: str
    source_type: str
    source_run_id: int
    target_symbol: str
    experiment_name: str
    status: str
    started_at: str
    finished_at: str | None
    git_commit: str
    data_version: str | None
    feature_version: str | None
    label_version: str | None
    model_name: str | None
    model_version: str | None
    strategy_name: str | None
    strategy_version: str | None
    parameters: dict[str, Any]
    metadata: dict[str, Any]
    metrics: dict[str, dict[str, float | None]]
    created_at: str


class ExperimentTracker:
    """Registers completed model and backtest runs as reproducible experiment records."""

    def __init__(
        self,
        repo: Repository,
        output_dir: Path | None = Path("data/experiments"),
        repo_root: Path | None = None,
    ):
        self.repo = repo
        self.output_dir = output_dir
        self.repo_root = (repo_root or Path.cwd()).resolve()

    def register_model_run(
        self,
        run_id: int,
        *,
        parameters: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExperimentRecord:
        row = self.repo.get_model_run(run_id)
        if row is None:
            raise ValueError(f"model run {run_id} does not exist")
        metric_rows = self.repo.get_model_metrics(run_id)
        return self._register(
            experiment_id=f"EXP-MODEL-{run_id:06d}",
            source_type="model",
            source_run_id=run_id,
            target_symbol=row["target_symbol"],
            experiment_name=f'{row["model_name"]}:{row["model_version"]}',
            status=row["status"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            feature_version=row["feature_version"],
            label_version=row["label_version"],
            model_name=row["model_name"],
            model_version=row["model_version"],
            strategy_name=None,
            strategy_version=None,
            parameters=parameters or {},
            metadata={
                "train_start": row["train_start"],
                "train_end": row["train_end"],
                "test_start": row["test_start"],
                "test_end": row["test_end"],
                "train_rows": row["train_rows"],
                "test_rows": row["test_rows"],
                "message": row["message"],
                **(metadata or {}),
            },
            metric_rows=metric_rows,
        )

    def register_backtest_run(
        self,
        run_id: int,
        *,
        parameters: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExperimentRecord:
        row = self.repo.get_backtest_run(run_id)
        if row is None:
            raise ValueError(f"backtest run {run_id} does not exist")
        metric_rows = self.repo.get_backtest_metrics(run_id)
        default_parameters = {
            "min_train_rows": row["min_train_rows"],
            "rebalance_rows": row["rebalance_rows"],
            "transaction_cost_bps": row["transaction_cost_bps"],
            "slippage_bps": row["slippage_bps"],
        }
        return self._register(
            experiment_id=f"EXP-BACKTEST-{run_id:06d}",
            source_type="backtest",
            source_run_id=run_id,
            target_symbol=row["target_symbol"],
            experiment_name=f'{row["strategy_name"]}:{row["strategy_version"]}',
            status=row["status"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            feature_version=row["feature_version"],
            label_version=row["label_version"],
            model_name=row["model_name"],
            model_version=row["model_version"],
            strategy_name=row["strategy_name"],
            strategy_version=row["strategy_version"],
            parameters={**default_parameters, **(parameters or {})},
            metadata={
                "start_date": row["start_date"],
                "end_date": row["end_date"],
                "message": row["message"],
                **(metadata or {}),
            },
            metric_rows=metric_rows,
        )

    def _register(self, *, metric_rows: list, **values: Any) -> ExperimentRecord:
        created_at = datetime.now(UTC).isoformat()
        metrics: dict[str, dict[str, float | None]] = {}
        database_metrics: list[tuple[str, float | None, str]] = []
        for row in metric_rows:
            sample_name = str(row["sample_name"])
            metric_name = str(row["metric_name"])
            metric_value = row["metric_value"]
            metrics.setdefault(sample_name, {})[metric_name] = metric_value
            database_metrics.append((metric_name, metric_value, sample_name))

        record = ExperimentRecord(
            **values,
            git_commit=_git_commit(self.repo_root),
            data_version=self.repo.latest_price_date(values["target_symbol"]),
            metrics=metrics,
            created_at=created_at,
        )
        payload = asdict(record)
        database_values = (
            record.experiment_id,
            record.source_type,
            record.source_run_id,
            record.target_symbol,
            record.experiment_name,
            record.status,
            record.started_at,
            record.finished_at,
            record.git_commit,
            record.data_version,
            record.feature_version,
            record.label_version,
            record.model_name,
            record.model_version,
            record.strategy_name,
            record.strategy_version,
            json.dumps(record.parameters, ensure_ascii=False, sort_keys=True),
            json.dumps(record.metadata, ensure_ascii=False, sort_keys=True),
            record.created_at,
        )
        self.repo.upsert_experiment(database_values, database_metrics)
        self._write_manifest(payload)
        return record

    def _write_manifest(self, payload: dict[str, Any]) -> None:
        if self.output_dir is None:
            return
        self.output_dir.mkdir(parents=True, exist_ok=True)
        destination = self.output_dir / f'{payload["experiment_id"]}.json'
        destination.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _git_commit(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return "unknown"
    return result.stdout.strip() or "unknown"
