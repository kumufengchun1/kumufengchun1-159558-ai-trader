from __future__ import annotations

from datetime import datetime, timezone
import math

from ats.db.repository import Repository


def _safe_return(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return current / previous - 1.0


def audit_adjustments(repo: Repository, symbols: list[str]) -> int:
    """Audit close vs adjusted-close discontinuities and suspicious raw jumps.

    This does not invent adjustment factors. It records evidence so downstream models
    can prefer adjusted returns and operators can review possible splits/distributions.
    """
    audited_at = datetime.now(timezone.utc).isoformat()
    output: list[tuple] = []
    for symbol in symbols:
        rows = repo.list_prices(symbol)
        prior_ratio = None
        prior_close = None
        prior_adj = None
        for row in rows:
            close = float(row["close"])
            adj = float(row["adj_close"]) if row["adj_close"] is not None else None
            ratio = close / adj if adj not in (None, 0) else None
            ratio_change = _safe_return(ratio, prior_ratio)
            raw_return = _safe_return(close, prior_close)
            adjusted_return = _safe_return(adj, prior_adj)

            flags: list[str] = []
            if ratio_change is not None and abs(ratio_change) >= 0.05:
                flags.append("adjustment_ratio_changed")
            if raw_return is not None and abs(raw_return) >= 0.35:
                if adjusted_return is None or abs(adjusted_return) < abs(raw_return) * 0.5:
                    flags.append("possible_corporate_action")
                else:
                    flags.append("extreme_price_move")
            if ratio is not None and (not math.isfinite(ratio) or ratio <= 0):
                flags.append("invalid_adjustment_ratio")

            status = "review" if flags else "ok"
            output.append(
                (
                    symbol,
                    row["trading_date"],
                    ratio,
                    prior_ratio,
                    ratio_change,
                    raw_return,
                    adjusted_return,
                    status,
                    ",".join(flags) if flags else "",
                    audited_at,
                )
            )
            prior_ratio = ratio
            prior_close = close
            prior_adj = adj
    return repo.upsert_adjustment_audit(output)
