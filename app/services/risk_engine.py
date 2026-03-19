from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any


def _safe_float(value: Any, fallback: float = 0.0) -> float:
    try:
        parsed = float(value)
        if parsed != parsed:
            return fallback
        return parsed
    except Exception:
        return fallback


@dataclass
class RiskGuardrails:
    max_risk_per_trade: float = 0.02
    max_portfolio_heat: float = 0.06
    max_symbol_concentration: float = 0.35
    max_open_positions: int = 5
    max_daily_loss: float = 0.04
    max_drawdown: float = 0.12
    max_degraded_sources: int = 2

    @classmethod
    def from_config(cls, config: dict[str, Any] | None = None, *, max_open_positions: int | None = None) -> "RiskGuardrails":
        raw = dict(config or {})
        values = {
            "max_risk_per_trade": max(_safe_float(raw.get("max_risk_per_trade"), cls.max_risk_per_trade), 0.001),
            "max_portfolio_heat": max(_safe_float(raw.get("max_portfolio_heat"), cls.max_portfolio_heat), 0.005),
            "max_symbol_concentration": max(_safe_float(raw.get("max_symbol_concentration"), cls.max_symbol_concentration), 0.05),
            "max_open_positions": max(int(raw.get("max_open_positions") or max_open_positions or cls.max_open_positions), 1),
            "max_daily_loss": max(_safe_float(raw.get("max_daily_loss"), cls.max_daily_loss), 0.005),
            "max_drawdown": max(_safe_float(raw.get("max_drawdown"), cls.max_drawdown), 0.01),
            "max_degraded_sources": max(int(raw.get("max_degraded_sources") or cls.max_degraded_sources), 0),
        }
        return cls(**values)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TradeRiskPlan:
    approved: bool
    requested_qty: float
    approved_qty: float
    estimated_notional: float
    estimated_loss: float
    portfolio_heat_after_trade: float
    concentration_after_trade: float
    risk_budget: float
    warnings: list[str] = field(default_factory=list)
    block_reasons: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PortfolioRiskSummary:
    open_positions: int
    open_notional: float
    estimated_open_risk: float
    largest_position_pct: float
    daily_realized_pnl: float
    rolling_drawdown_pct: float
    degraded_data_runs: int
    kill_switch_armed: bool
    health_score: float
    alerts: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    by_symbol: list[dict[str, Any]] = field(default_factory=list)
    guardrails: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_trade_risk_plan(
    *,
    available_balance: float,
    price: float,
    stop_loss_price: float,
    requested_qty: float,
    risk_per_trade: float,
    current_open_notional: float,
    current_open_risk: float,
    current_symbol_notional: float,
    current_open_positions: int,
    guardrails: RiskGuardrails,
    market_meta: dict[str, Any] | None = None,
) -> TradeRiskPlan:
    market_meta = market_meta or {}
    warnings: list[str] = []
    block_reasons: list[str] = []

    available_balance = max(_safe_float(available_balance), 0.0)
    price = max(_safe_float(price), 0.0)
    stop_loss_price = max(_safe_float(stop_loss_price), 0.0)
    requested_qty = max(_safe_float(requested_qty), 0.0)
    risk_per_trade = max(_safe_float(risk_per_trade), 0.0)

    if requested_qty <= 0 or price <= 0:
        block_reasons.append("invalid_trade_request")
        return TradeRiskPlan(
            approved=False,
            requested_qty=requested_qty,
            approved_qty=0.0,
            estimated_notional=0.0,
            estimated_loss=0.0,
            portfolio_heat_after_trade=current_open_risk,
            concentration_after_trade=0.0,
            risk_budget=0.0,
            warnings=warnings,
            block_reasons=block_reasons,
            diagnostics={"available_balance": available_balance, "price": price},
        )

    health = market_meta.get("health") or {}
    anomalies = market_meta.get("anomalies") or {}
    anomaly_severity = str(anomalies.get("severity") or "ok")
    if market_meta.get("source") == "synthetic_fallback":
        warnings.append("synthetic_market_data")
    if health.get("issues"):
        warnings.extend(str(item) for item in health.get("issues") if item)
    if anomaly_severity in {"high", "critical"}:
        block_reasons.append("market_data_anomaly")

    stop_distance = abs(price - stop_loss_price)
    if stop_distance <= 0:
        stop_distance = max(price * 0.001, 0.0000001)
        warnings.append("stop_distance_fallback")

    equity_reference = max(available_balance + max(_safe_float(current_open_notional), 0.0), available_balance, price * requested_qty)
    risk_budget = equity_reference * min(max(risk_per_trade, 0.0001), guardrails.max_risk_per_trade)
    max_qty_from_risk = risk_budget / max(stop_distance, 0.0000001)
    remaining_heat_budget = max(guardrails.max_portfolio_heat * equity_reference - max(_safe_float(current_open_risk), 0.0), 0.0)
    max_qty_from_heat = remaining_heat_budget / max(stop_distance, 0.0000001)
    remaining_symbol_budget = max(guardrails.max_symbol_concentration * equity_reference - max(_safe_float(current_symbol_notional), 0.0), 0.0)
    max_qty_from_symbol = remaining_symbol_budget / max(price, 0.0000001)

    approved_qty = min(requested_qty, max_qty_from_risk, max_qty_from_heat, max_qty_from_symbol)
    approved_qty = max(approved_qty, 0.0)

    if current_open_positions >= guardrails.max_open_positions:
        block_reasons.append("max_open_positions_reached")
    if remaining_heat_budget <= 0:
        block_reasons.append("portfolio_heat_limit")
    if remaining_symbol_budget <= 0:
        block_reasons.append("symbol_concentration_limit")
    if available_balance <= 0:
        block_reasons.append("balance_unavailable")

    estimated_notional = approved_qty * price
    estimated_loss = approved_qty * stop_distance
    concentration_after_trade = (current_symbol_notional + estimated_notional) / max(equity_reference, 0.0000001)
    portfolio_heat_after_trade = (current_open_risk + estimated_loss) / max(equity_reference, 0.0000001)

    if approved_qty <= 0:
        block_reasons.append("trade_size_collapsed")
    elif approved_qty < requested_qty:
        warnings.append("qty_capped_by_risk_engine")

    approved = not block_reasons
    return TradeRiskPlan(
        approved=approved,
        requested_qty=requested_qty,
        approved_qty=round(approved_qty, 8),
        estimated_notional=round(estimated_notional, 8),
        estimated_loss=round(estimated_loss, 8),
        portfolio_heat_after_trade=round(portfolio_heat_after_trade, 8),
        concentration_after_trade=round(concentration_after_trade, 8),
        risk_budget=round(risk_budget, 8),
        warnings=warnings,
        block_reasons=block_reasons,
        diagnostics={
            "available_balance": available_balance,
            "equity_reference": round(equity_reference, 8),
            "stop_distance": round(stop_distance, 8),
            "max_qty_from_risk": round(max_qty_from_risk, 8),
            "max_qty_from_heat": round(max_qty_from_heat, 8),
            "max_qty_from_symbol": round(max_qty_from_symbol, 8),
            "market_source": market_meta.get("source"),
            "anomaly_severity": anomaly_severity,
        },
    )


def summarize_portfolio_risk(db, user_id: int, *, lookback_days: int = 30) -> dict[str, Any]:
    from app.models import OpenPosition, TradeLog, TradeRun

    now = datetime.utcnow()
    guardrails = RiskGuardrails()
    positions = db.query(OpenPosition).filter(OpenPosition.user_id == user_id, OpenPosition.is_open.is_(True)).all()
    trades = db.query(TradeLog).filter(TradeLog.user_id == user_id).order_by(TradeLog.created_at.asc()).all()
    recent_runs = db.query(TradeRun).filter(TradeRun.user_id == user_id, TradeRun.created_at >= now - timedelta(days=lookback_days)).all()

    by_symbol_counter: Counter[str] = Counter()
    by_symbol_notional: dict[str, float] = {}
    open_notional = 0.0
    estimated_open_risk = 0.0

    for position in positions:
        symbol = str(position.symbol or "unknown")
        notional = max(_safe_float(position.entry_price) * _safe_float(position.current_qty), 0.0)
        stop_loss_price = _safe_float((position.meta_json or {}).get("stop_loss_price"), 0.0)
        if stop_loss_price > 0:
            estimated_loss = abs(_safe_float(position.entry_price) - stop_loss_price) * _safe_float(position.current_qty)
        else:
            estimated_loss = 0.0
        open_notional += notional
        estimated_open_risk += estimated_loss
        by_symbol_counter[symbol] += 1
        by_symbol_notional[symbol] = by_symbol_notional.get(symbol, 0.0) + notional

    running = 0.0
    peak = 0.0
    worst_drawdown = 0.0
    daily_realized_pnl = 0.0
    today = now.date()
    for trade in trades:
        pnl = _safe_float(trade.pnl)
        running += pnl
        peak = max(peak, running)
        if peak > 0:
            drawdown_pct = (peak - running) / peak
            worst_drawdown = max(worst_drawdown, drawdown_pct)
        if getattr(trade, "created_at", None) and trade.created_at.date() == today:
            daily_realized_pnl += pnl

    degraded_data_runs = 0
    for run in recent_runs:
        note = getattr(run, "notes", None)
        if isinstance(note, str) and ("synthetic_fallback" in note or "stale_feed" in note or "market_data_anomaly" in note):
            degraded_data_runs += 1

    total_capital_proxy = max(open_notional + max(sum(max(_safe_float(t.pnl), 0.0) for t in trades), 0.0), open_notional, 1.0)
    largest_position_pct = max((notional / total_capital_proxy for notional in by_symbol_notional.values()), default=0.0)

    alerts: list[str] = []
    suggestions: list[str] = []
    if worst_drawdown >= guardrails.max_drawdown:
        alerts.append("drawdown_limit_breached")
        suggestions.append("Reducir riesgo por trade y activar revisión manual antes de nuevas entradas.")
    if estimated_open_risk / total_capital_proxy >= guardrails.max_portfolio_heat:
        alerts.append("portfolio_heat_elevated")
        suggestions.append("Bajar exposición agregada o cerrar posiciones menos eficientes.")
    if largest_position_pct >= guardrails.max_symbol_concentration:
        alerts.append("symbol_concentration_elevated")
        suggestions.append("Diversificar símbolos para evitar dependencia en una sola posición.")
    if degraded_data_runs > guardrails.max_degraded_sources:
        alerts.append("market_data_quality_degraded")
        suggestions.append("Revisar conectividad de exchange y no operar live con fallback sintético.")
    if daily_realized_pnl < 0 and abs(daily_realized_pnl) / total_capital_proxy >= guardrails.max_daily_loss:
        alerts.append("daily_loss_limit_breached")
        suggestions.append("Activar kill switch temporal y hacer cooldown operativo.")

    health_score = 100.0
    health_score -= min(worst_drawdown * 100.0 * 1.2, 35.0)
    health_score -= min((estimated_open_risk / total_capital_proxy) * 100.0 * 1.5, 30.0)
    health_score -= min(largest_position_pct * 100.0 * 0.8, 20.0)
    health_score -= min(degraded_data_runs * 7.5, 15.0)
    health_score = max(round(health_score, 2), 0.0)

    by_symbol = []
    for symbol, notional in sorted(by_symbol_notional.items(), key=lambda item: item[1], reverse=True):
        by_symbol.append({
            "symbol": symbol,
            "open_positions": by_symbol_counter[symbol],
            "notional": round(notional, 8),
            "weight": round(notional / total_capital_proxy, 8),
        })

    summary = PortfolioRiskSummary(
        open_positions=len(positions),
        open_notional=round(open_notional, 8),
        estimated_open_risk=round(estimated_open_risk, 8),
        largest_position_pct=round(largest_position_pct, 8),
        daily_realized_pnl=round(daily_realized_pnl, 8),
        rolling_drawdown_pct=round(worst_drawdown, 8),
        degraded_data_runs=degraded_data_runs,
        kill_switch_armed=any(item in alerts for item in {"drawdown_limit_breached", "daily_loss_limit_breached", "market_data_quality_degraded"}),
        health_score=health_score,
        alerts=alerts,
        suggestions=suggestions,
        by_symbol=by_symbol,
        guardrails=guardrails.to_dict(),
    )
    return summary.to_dict()
