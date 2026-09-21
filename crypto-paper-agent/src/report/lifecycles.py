"""Aggregate realized slices into completed positions without changing the cash ledger.

New broker rows carry lifecycle metadata and require explicit terminal/quantity
evidence. Legacy inputs are a caller-declared closed-trade list: explicit
position_id groups slices, untagged rows remain individual closed trades.
Legacy partial rows without identity are ambiguous and must not be guessed.
"""

import math


def _positive(value):
    if isinstance(value, bool) or value is None:
        raise ValueError("Lifecycle quantity/risk must be positive finite numeric")
    try:
        number = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            "Lifecycle quantity/risk must be positive finite numeric"
        ) from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError("Lifecycle quantity/risk must be positive finite numeric")
    return number


def completed_lifecycles(trades):
    """Return complete aggregated records, preserving legacy closed-input support."""
    groups = {}
    for index, trade in enumerate(trades):
        row = dict(trade if isinstance(trade, dict) else vars(trade))
        meta = row.get("metadata") or {}
        if not isinstance(meta, dict):
            raise ValueError("Lifecycle metadata must be a mapping")
        identity = meta.get("lifecycle_id", row.get("position_id"))
        tagged = any(
            k in meta
            for k in ("lifecycle_id", "lifecycle_complete", "lifecycle_quantity")
        )
        if tagged and (not isinstance(identity, str) or not identity):
            raise ValueError("Lifecycle identity is missing")
        if identity is None and meta.get("partial_exit"):
            raise ValueError(
                "Lifecycle identity missing for legacy partial realization"
            )
        if identity is not None and (not isinstance(identity, str) or not identity):
            raise ValueError("Lifecycle identity must be a nonempty string")
        if meta.get("lifecycle_id") and row.get("position_id") not in (None, identity):
            raise ValueError("Lifecycle identities conflict")
        key = (
            (row.get("run_id"), row.get("symbol"), identity)
            if identity is not None
            else ("legacy_row", index)
        )
        groups.setdefault(key, []).append((row, meta, tagged))

    completed = []
    for group in groups.values():
        rows = [r for r, _, _ in group]
        tagged = any(tag for _, _, tag in group)
        if tagged:
            if not all(tag for _, _, tag in group):
                raise ValueError(
                    "Lifecycle mixes legacy and explicit completion records"
                )
            terminals = [m.get("lifecycle_complete") for _, m, _ in group]
            if any(type(t) is not bool for t in terminals):
                raise ValueError("Lifecycle completion must be explicit boolean")
            if sum(terminals) > 1 or (True in terminals and not terminals[-1]):
                raise ValueError("Lifecycle has duplicate or non-final terminal record")
            original = [_positive(m.get("lifecycle_quantity")) for _, m, _ in group]
            if any(
                not math.isclose(q, original[0], rel_tol=1e-10, abs_tol=1e-12)
                for q in original
            ):
                raise ValueError("Lifecycle original quantities conflict")
            quantity = sum(_positive(r.get("quantity")) for r in rows)
            ids = [r.get("trade_id") for r in rows]
            if any(i is None for i in ids) or len(set(ids)) != len(ids):
                raise ValueError("Lifecycle realization IDs missing or duplicated")
            full = math.isclose(quantity, original[0], rel_tol=1e-9, abs_tol=1e-12)
            if terminals[-1] and not full:
                raise ValueError(
                    "Lifecycle terminal quantity does not reconcile to original"
                )
            if not terminals[-1] and (full or quantity > original[0]):
                raise ValueError("Lifecycle fully realized without terminal marker")
        for name in ("symbol", "direction", "entry_time", "entry_price"):
            if any(r.get(name) != rows[0].get(name) for r in rows):
                raise ValueError(f"Lifecycle {name} conflicts between slices")
        if tagged and not terminals[-1]:
            continue
        aggregate = dict(rows[-1])
        for name in (
            "net_pnl",
            "gross_price_pnl",
            "entry_fee",
            "exit_fee",
            "funding_cashflow",
        ):
            aggregate[name] = sum(float(r.get(name, 0.0)) for r in rows)
        if all(r.get("initial_risk_usd") is not None for r in rows):
            risk = sum(_positive(r["initial_risk_usd"]) for r in rows)
            aggregate["initial_risk_usd"] = risk
            aggregate["realized_r_multiple"] = aggregate["net_pnl"] / risk
        elif len(rows) > 1:
            # Cannot infer original risk from a slice R, especially a zero-PnL slice.
            aggregate["initial_risk_usd"] = None
            aggregate["realized_r_multiple"] = None
        completed.append(aggregate)
    # Streaks follow completion, not the first partial realization of a position.
    if completed and all(r.get("exit_time") is not None for r in completed):
        completed.sort(key=lambda r: r["exit_time"])
    return completed
