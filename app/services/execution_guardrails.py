from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP, ROUND_UP
from math import isfinite
from typing import Any


_DECIMAL_ZERO = Decimal("0")
_DECIMAL_ONE = Decimal("1")


def _decimal(value: Any, default: str = "0") -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value in (None, "", False):
        return Decimal(default)
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def _float_or_none(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _is_valid_number(value: Any) -> bool:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    return isfinite(numeric)


def precision_to_step(precision: int | float | None) -> Decimal:
    if precision in (None, ""):
        return _DECIMAL_ZERO
    try:
        precision_int = int(precision)
    except (TypeError, ValueError):
        return _DECIMAL_ZERO
    if precision_int < 0:
        return _DECIMAL_ZERO
    return Decimal("1").scaleb(-precision_int)


def floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= _DECIMAL_ZERO:
        return value
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def ceil_to_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= _DECIMAL_ZERO:
        return value
    return (value / step).to_integral_value(rounding=ROUND_UP) * step


def quantize_to_precision(value: Decimal, precision: int | None, rounding=ROUND_DOWN) -> Decimal:
    if precision is None or precision < 0:
        return value
    quant = precision_to_step(precision)
    if quant <= _DECIMAL_ZERO:
        return value
    return value.quantize(quant, rounding=rounding)


@dataclass
class MarketRules:
    exchange: str
    symbol: str
    market_type: str
    amount_min: float | None = None
    amount_max: float | None = None
    amount_step: float | None = None
    price_min: float | None = None
    price_max: float | None = None
    price_step: float | None = None
    price_precision: int | None = None
    amount_precision: int | None = None
    min_cost: float | None = None
    max_cost: float | None = None
    contract_size: float | None = None
    requires_cost_for_market_buy: bool = False
    qty_semantics: str = "base"
    normalized_rule_source: str = "markets|limits|precision|adapter"
    raw_exchange_rules: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionReferencePrice:
    value: float | None
    source: str
    used_fallback: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationDecision:
    is_valid: bool
    exchange: str
    symbol: str
    market_type: str
    order_type: str
    side: str
    analysis_price: float | None
    execution_reference_price: float | None
    execution_price_source: str
    raw_qty: float
    normalized_qty: float
    raw_price: float | None
    normalized_price: float | None
    amount_min: float | None
    amount_step: float | None
    price_step: float | None
    min_cost: float | None
    final_cost: float | None
    contract_size: float | None
    adjusted_for_minimums: bool
    risk_blocked: bool
    skip_reason: str | None
    market_buy_cost: float | None = None
    requires_cost_for_market_buy: bool = False
    exchange_rules_snapshot: dict[str, Any] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_PRICE_GUARDRAILS = {
    "max_price_ratio": 20.0,
    "max_price_deviation_pct": 0.35,
}


def build_validation_decision(
    *,
    exchange: str,
    symbol: str,
    market_type: str,
    order_type: str,
    side: str,
    desired_qty: float,
    desired_price: float | None,
    analysis_price: float | None,
    execution_reference: ExecutionReferencePrice,
    market_rules: MarketRules,
    risk_context: dict[str, Any] | None = None,
    connector_context: dict[str, Any] | None = None,
) -> ValidationDecision:
    risk_context = risk_context or {}
    connector_context = connector_context or {}

    diagnostics: dict[str, Any] = {
        "risk_context": risk_context,
        "connector_context": connector_context,
        "execution_reference": execution_reference.to_dict(),
    }

    raw_qty = _decimal(desired_qty)
    raw_price = _decimal(desired_price) if desired_price is not None else None
    analysis_dec = _decimal(analysis_price) if analysis_price is not None else None
    exec_price = _decimal(execution_reference.value)
    contract_size = _decimal(market_rules.contract_size or 1)

    if raw_qty <= _DECIMAL_ZERO or not _is_valid_number(desired_qty):
        return ValidationDecision(
            is_valid=False,
            exchange=exchange,
            symbol=symbol,
            market_type=market_type,
            order_type=order_type,
            side=side,
            analysis_price=analysis_price,
            execution_reference_price=execution_reference.value,
            execution_price_source=execution_reference.source,
            raw_qty=float(desired_qty or 0.0),
            normalized_qty=0.0,
            raw_price=float(desired_price) if desired_price is not None and _is_valid_number(desired_price) else None,
            normalized_price=None,
            amount_min=market_rules.amount_min,
            amount_step=market_rules.amount_step,
            price_step=market_rules.price_step,
            min_cost=market_rules.min_cost,
            final_cost=None,
            contract_size=market_rules.contract_size,
            adjusted_for_minimums=False,
            risk_blocked=False,
            skip_reason="rejected_invalid_quantity",
            requires_cost_for_market_buy=market_rules.requires_cost_for_market_buy,
            exchange_rules_snapshot=market_rules.to_dict(),
            diagnostics=diagnostics,
        )

    if exec_price <= _DECIMAL_ZERO or not _is_valid_number(execution_reference.value):
        return ValidationDecision(
            is_valid=False,
            exchange=exchange,
            symbol=symbol,
            market_type=market_type,
            order_type=order_type,
            side=side,
            analysis_price=analysis_price,
            execution_reference_price=execution_reference.value,
            execution_price_source=execution_reference.source,
            raw_qty=float(raw_qty),
            normalized_qty=0.0,
            raw_price=float(raw_price) if raw_price is not None else None,
            normalized_price=None,
            amount_min=market_rules.amount_min,
            amount_step=market_rules.amount_step,
            price_step=market_rules.price_step,
            min_cost=market_rules.min_cost,
            final_cost=None,
            contract_size=market_rules.contract_size,
            adjusted_for_minimums=False,
            risk_blocked=False,
            skip_reason="invalid_execution_reference_price",
            requires_cost_for_market_buy=market_rules.requires_cost_for_market_buy,
            exchange_rules_snapshot=market_rules.to_dict(),
            diagnostics=diagnostics,
        )

    max_ratio = float((connector_context.get("price_guardrails") or {}).get("max_price_ratio") or DEFAULT_PRICE_GUARDRAILS["max_price_ratio"])
    max_deviation_pct = float((connector_context.get("price_guardrails") or {}).get("max_price_deviation_pct") or DEFAULT_PRICE_GUARDRAILS["max_price_deviation_pct"])
    diagnostics["price_guardrails"] = {"max_price_ratio": max_ratio, "max_price_deviation_pct": max_deviation_pct}

    if analysis_dec and analysis_dec > _DECIMAL_ZERO:
        ratio = max(exec_price / analysis_dec, analysis_dec / exec_price)
        deviation_pct = abs(exec_price - analysis_dec) / analysis_dec
        diagnostics["analysis_vs_execution"] = {
            "ratio": float(ratio),
            "deviation_pct": float(deviation_pct),
        }
        if ratio >= Decimal(str(max_ratio)):
            return ValidationDecision(
                is_valid=False,
                exchange=exchange,
                symbol=symbol,
                market_type=market_type,
                order_type=order_type,
                side=side,
                analysis_price=float(analysis_dec),
                execution_reference_price=float(exec_price),
                execution_price_source=execution_reference.source,
                raw_qty=float(raw_qty),
                normalized_qty=0.0,
                raw_price=float(raw_price) if raw_price is not None else None,
                normalized_price=None,
                amount_min=market_rules.amount_min,
                amount_step=market_rules.amount_step,
                price_step=market_rules.price_step,
                min_cost=market_rules.min_cost,
                final_cost=None,
                contract_size=market_rules.contract_size,
                adjusted_for_minimums=False,
                risk_blocked=False,
                skip_reason="suspicious_price_scale_detected",
                requires_cost_for_market_buy=market_rules.requires_cost_for_market_buy,
                exchange_rules_snapshot=market_rules.to_dict(),
                diagnostics=diagnostics,
            )
        if deviation_pct >= Decimal(str(max_deviation_pct)):
            return ValidationDecision(
                is_valid=False,
                exchange=exchange,
                symbol=symbol,
                market_type=market_type,
                order_type=order_type,
                side=side,
                analysis_price=float(analysis_dec),
                execution_reference_price=float(exec_price),
                execution_price_source=execution_reference.source,
                raw_qty=float(raw_qty),
                normalized_qty=0.0,
                raw_price=float(raw_price) if raw_price is not None else None,
                normalized_price=None,
                amount_min=market_rules.amount_min,
                amount_step=market_rules.amount_step,
                price_step=market_rules.price_step,
                min_cost=market_rules.min_cost,
                final_cost=None,
                contract_size=market_rules.contract_size,
                adjusted_for_minimums=False,
                risk_blocked=False,
                skip_reason="market_price_mismatch",
                requires_cost_for_market_buy=market_rules.requires_cost_for_market_buy,
                exchange_rules_snapshot=market_rules.to_dict(),
                diagnostics=diagnostics,
            )

    amount_step = _decimal(market_rules.amount_step)
    if amount_step <= _DECIMAL_ZERO and market_rules.amount_precision is not None:
        amount_step = precision_to_step(market_rules.amount_precision)
    price_step = _decimal(market_rules.price_step)
    if price_step <= _DECIMAL_ZERO and market_rules.price_precision is not None:
        price_step = precision_to_step(market_rules.price_precision)

    normalized_qty = raw_qty
    if amount_step > _DECIMAL_ZERO:
        normalized_qty = floor_to_step(normalized_qty, amount_step)
    if market_rules.amount_precision is not None:
        normalized_qty = quantize_to_precision(normalized_qty, market_rules.amount_precision, rounding=ROUND_DOWN)

    if normalized_qty <= _DECIMAL_ZERO:
        return ValidationDecision(
            is_valid=False,
            exchange=exchange,
            symbol=symbol,
            market_type=market_type,
            order_type=order_type,
            side=side,
            analysis_price=analysis_price,
            execution_reference_price=float(exec_price),
            execution_price_source=execution_reference.source,
            raw_qty=float(raw_qty),
            normalized_qty=0.0,
            raw_price=float(raw_price) if raw_price is not None else None,
            normalized_price=None,
            amount_min=market_rules.amount_min,
            amount_step=market_rules.amount_step,
            price_step=market_rules.price_step,
            min_cost=market_rules.min_cost,
            final_cost=None,
            contract_size=market_rules.contract_size,
            adjusted_for_minimums=False,
            risk_blocked=False,
            skip_reason="rejected_invalid_quantity",
            requires_cost_for_market_buy=market_rules.requires_cost_for_market_buy,
            exchange_rules_snapshot=market_rules.to_dict(),
            diagnostics=diagnostics,
        )

    normalized_price = exec_price if raw_price is None else raw_price
    if price_step > _DECIMAL_ZERO:
        rounding = ROUND_DOWN if side.lower() == "buy" else ROUND_UP
        normalized_price = (normalized_price / price_step).to_integral_value(rounding=rounding) * price_step
    if market_rules.price_precision is not None:
        rounding = ROUND_DOWN if side.lower() == "buy" else ROUND_HALF_UP
        normalized_price = quantize_to_precision(normalized_price, market_rules.price_precision, rounding=rounding)

    amount_min = _decimal(market_rules.amount_min)
    amount_max = _decimal(market_rules.amount_max)
    min_cost = _decimal(market_rules.min_cost)
    max_cost = _decimal(market_rules.max_cost)
    max_qty_allowed = _decimal(risk_context.get("max_qty")) if risk_context.get("max_qty") is not None else _DECIMAL_ZERO
    max_cost_allowed = _decimal(risk_context.get("max_cost")) if risk_context.get("max_cost") is not None else _DECIMAL_ZERO
    allow_adjust_up = bool(risk_context.get("allow_adjust_up", False))
    adjusted_for_minimums = False

    if amount_min > _DECIMAL_ZERO and normalized_qty < amount_min:
        if allow_adjust_up:
            normalized_qty = amount_min
            if amount_step > _DECIMAL_ZERO:
                normalized_qty = ceil_to_step(normalized_qty, amount_step)
            if market_rules.amount_precision is not None:
                normalized_qty = quantize_to_precision(normalized_qty, market_rules.amount_precision, rounding=ROUND_UP)
            adjusted_for_minimums = True
        else:
            return ValidationDecision(
                is_valid=False,
                exchange=exchange,
                symbol=symbol,
                market_type=market_type,
                order_type=order_type,
                side=side,
                analysis_price=analysis_price,
                execution_reference_price=float(exec_price),
                execution_price_source=execution_reference.source,
                raw_qty=float(raw_qty),
                normalized_qty=float(normalized_qty),
                raw_price=float(raw_price) if raw_price is not None else None,
                normalized_price=float(normalized_price),
                amount_min=market_rules.amount_min,
                amount_step=market_rules.amount_step,
                price_step=market_rules.price_step,
                min_cost=market_rules.min_cost,
                final_cost=float(normalized_qty * normalized_price * max(contract_size, _DECIMAL_ONE)),
                contract_size=market_rules.contract_size,
                adjusted_for_minimums=False,
                risk_blocked=False,
                skip_reason="skipped_min_qty",
                requires_cost_for_market_buy=market_rules.requires_cost_for_market_buy,
                exchange_rules_snapshot=market_rules.to_dict(),
                diagnostics=diagnostics,
            )

    final_cost = normalized_qty * normalized_price * max(contract_size, _DECIMAL_ONE)
    diagnostics["projected_notional"] = float(final_cost)

    if min_cost > _DECIMAL_ZERO and final_cost < min_cost:
        required_qty = min_cost / max(normalized_price * max(contract_size, _DECIMAL_ONE), Decimal("0.00000001"))
        diagnostics["required_min_qty_for_notional"] = float(required_qty)
        if allow_adjust_up:
            normalized_qty = required_qty
            if amount_step > _DECIMAL_ZERO:
                normalized_qty = ceil_to_step(normalized_qty, amount_step)
            if amount_min > _DECIMAL_ZERO and normalized_qty < amount_min:
                normalized_qty = amount_min
            if market_rules.amount_precision is not None:
                normalized_qty = quantize_to_precision(normalized_qty, market_rules.amount_precision, rounding=ROUND_UP)
            final_cost = normalized_qty * normalized_price * max(contract_size, _DECIMAL_ONE)
            adjusted_for_minimums = True
        else:
            return ValidationDecision(
                is_valid=False,
                exchange=exchange,
                symbol=symbol,
                market_type=market_type,
                order_type=order_type,
                side=side,
                analysis_price=analysis_price,
                execution_reference_price=float(exec_price),
                execution_price_source=execution_reference.source,
                raw_qty=float(raw_qty),
                normalized_qty=float(normalized_qty),
                raw_price=float(raw_price) if raw_price is not None else None,
                normalized_price=float(normalized_price),
                amount_min=market_rules.amount_min,
                amount_step=market_rules.amount_step,
                price_step=market_rules.price_step,
                min_cost=market_rules.min_cost,
                final_cost=float(final_cost),
                contract_size=market_rules.contract_size,
                adjusted_for_minimums=False,
                risk_blocked=False,
                skip_reason="skipped_min_notional",
                requires_cost_for_market_buy=market_rules.requires_cost_for_market_buy,
                exchange_rules_snapshot=market_rules.to_dict(),
                diagnostics=diagnostics,
            )

    if amount_max > _DECIMAL_ZERO and normalized_qty > amount_max:
        return ValidationDecision(
            is_valid=False,
            exchange=exchange,
            symbol=symbol,
            market_type=market_type,
            order_type=order_type,
            side=side,
            analysis_price=analysis_price,
            execution_reference_price=float(exec_price),
            execution_price_source=execution_reference.source,
            raw_qty=float(raw_qty),
            normalized_qty=float(normalized_qty),
            raw_price=float(raw_price) if raw_price is not None else None,
            normalized_price=float(normalized_price),
            amount_min=market_rules.amount_min,
            amount_step=market_rules.amount_step,
            price_step=market_rules.price_step,
            min_cost=market_rules.min_cost,
            final_cost=float(final_cost),
            contract_size=market_rules.contract_size,
            adjusted_for_minimums=adjusted_for_minimums,
            risk_blocked=False,
            skip_reason="exchange_amount_max_failed",
            requires_cost_for_market_buy=market_rules.requires_cost_for_market_buy,
            exchange_rules_snapshot=market_rules.to_dict(),
            diagnostics=diagnostics,
        )

    if max_qty_allowed > _DECIMAL_ZERO and normalized_qty > max_qty_allowed:
        return ValidationDecision(
            is_valid=False,
            exchange=exchange,
            symbol=symbol,
            market_type=market_type,
            order_type=order_type,
            side=side,
            analysis_price=analysis_price,
            execution_reference_price=float(exec_price),
            execution_price_source=execution_reference.source,
            raw_qty=float(raw_qty),
            normalized_qty=float(normalized_qty),
            raw_price=float(raw_price) if raw_price is not None else None,
            normalized_price=float(normalized_price),
            amount_min=market_rules.amount_min,
            amount_step=market_rules.amount_step,
            price_step=market_rules.price_step,
            min_cost=market_rules.min_cost,
            final_cost=float(final_cost),
            contract_size=market_rules.contract_size,
            adjusted_for_minimums=adjusted_for_minimums,
            risk_blocked=True,
            skip_reason="skipped_amount_adjustment_exceeds_risk",
            requires_cost_for_market_buy=market_rules.requires_cost_for_market_buy,
            exchange_rules_snapshot=market_rules.to_dict(),
            diagnostics=diagnostics,
        )

    if max_cost_allowed > _DECIMAL_ZERO and final_cost > max_cost_allowed:
        return ValidationDecision(
            is_valid=False,
            exchange=exchange,
            symbol=symbol,
            market_type=market_type,
            order_type=order_type,
            side=side,
            analysis_price=analysis_price,
            execution_reference_price=float(exec_price),
            execution_price_source=execution_reference.source,
            raw_qty=float(raw_qty),
            normalized_qty=float(normalized_qty),
            raw_price=float(raw_price) if raw_price is not None else None,
            normalized_price=float(normalized_price),
            amount_min=market_rules.amount_min,
            amount_step=market_rules.amount_step,
            price_step=market_rules.price_step,
            min_cost=market_rules.min_cost,
            final_cost=float(final_cost),
            contract_size=market_rules.contract_size,
            adjusted_for_minimums=adjusted_for_minimums,
            risk_blocked=True,
            skip_reason="skipped_exchange_constraints_conflict",
            requires_cost_for_market_buy=market_rules.requires_cost_for_market_buy,
            exchange_rules_snapshot=market_rules.to_dict(),
            diagnostics=diagnostics,
        )

    if max_cost > _DECIMAL_ZERO and final_cost > max_cost:
        return ValidationDecision(
            is_valid=False,
            exchange=exchange,
            symbol=symbol,
            market_type=market_type,
            order_type=order_type,
            side=side,
            analysis_price=analysis_price,
            execution_reference_price=float(exec_price),
            execution_price_source=execution_reference.source,
            raw_qty=float(raw_qty),
            normalized_qty=float(normalized_qty),
            raw_price=float(raw_price) if raw_price is not None else None,
            normalized_price=float(normalized_price),
            amount_min=market_rules.amount_min,
            amount_step=market_rules.amount_step,
            price_step=market_rules.price_step,
            min_cost=market_rules.min_cost,
            final_cost=float(final_cost),
            contract_size=market_rules.contract_size,
            adjusted_for_minimums=adjusted_for_minimums,
            risk_blocked=False,
            skip_reason="exchange_cost_max_failed",
            requires_cost_for_market_buy=market_rules.requires_cost_for_market_buy,
            exchange_rules_snapshot=market_rules.to_dict(),
            diagnostics=diagnostics,
        )

    market_buy_cost = final_cost if market_rules.requires_cost_for_market_buy and order_type.lower() == "market" and side.lower() == "buy" else None

    return ValidationDecision(
        is_valid=True,
        exchange=exchange,
        symbol=symbol,
        market_type=market_type,
        order_type=order_type,
        side=side,
        analysis_price=float(analysis_dec) if analysis_dec is not None else None,
        execution_reference_price=float(exec_price),
        execution_price_source=execution_reference.source,
        raw_qty=float(raw_qty),
        normalized_qty=float(normalized_qty),
        raw_price=float(raw_price) if raw_price is not None else None,
        normalized_price=float(normalized_price),
        amount_min=market_rules.amount_min,
        amount_step=market_rules.amount_step,
        price_step=market_rules.price_step,
        min_cost=market_rules.min_cost,
        final_cost=float(final_cost),
        contract_size=market_rules.contract_size,
        adjusted_for_minimums=adjusted_for_minimums,
        risk_blocked=False,
        skip_reason=None,
        market_buy_cost=float(market_buy_cost) if market_buy_cost is not None else None,
        requires_cost_for_market_buy=market_rules.requires_cost_for_market_buy,
        exchange_rules_snapshot=market_rules.to_dict(),
        diagnostics=diagnostics,
    )
