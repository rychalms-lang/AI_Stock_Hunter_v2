from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


SCHEMA_VERSION = "1.0"


DEFAULT_ENVIRONMENT: Dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "environment_id": "personal_cash_account",
    "name": "Personal Cash Account",
    "preset_source": "built_in",
    "account_rules": {
        "starting_capital": 25000.0,
        "currency": "USD",
        "margin_enabled": False,
        "maximum_leverage": 1.0,
        "fractional_shares": False,
        "minimum_cash_reserve_pct": 10.0,
        "maximum_invested_pct": 90.0,
        "maximum_open_positions": 7,
        "maximum_position_allocation_pct": 15.0,
        "fixed_transaction_fee": 0.0,
        "percentage_transaction_fee_pct": 0.0,
        "slippage_pct": 0.10,
    },
    "risk_limits": {
        "daily_loss_limit_dollars": 1000.0,
        "daily_loss_limit_pct": 4.0,
        "overall_max_drawdown_pct": 12.0,
        "trailing_drawdown_amount": 3000.0,
        "trailing_drawdown_pct": 12.0,
        "trailing_drawdown_method": "end_of_day_peak",
        "maximum_single_position_exposure_pct": 15.0,
        "maximum_sector_exposure_pct": 35.0,
        "maximum_portfolio_heat_pct": 10.0,
        "maximum_risk_per_trade_pct": 2.0,
        "maximum_risk_per_position_pct": 2.0,
    },
    "trading_restrictions": {
        "long_only": True,
        "short_selling_allowed": False,
        "overnight_holding_allowed": True,
        "weekend_holding_allowed": True,
        "forced_end_of_day_liquidation": False,
        "minimum_holding_period_days": 0,
        "maximum_holding_period_days": 10,
        "maximum_trades_per_day": 10,
        "maximum_new_positions_per_day": 7,
        "maximum_turnover_pct": 100.0,
        "restricted_tickers": [],
        "minimum_share_price": 0.0,
        "maximum_share_price": 100000.0,
        "minimum_liquidity": None,
    },
    "consistency_rules": {
        "maximum_profit_from_one_day_pct": 50.0,
        "maximum_profit_from_one_trade_pct": 35.0,
        "minimum_trading_days": 10,
        "minimum_profitable_days": 3,
        "maximum_consecutive_losing_days": 5,
        "maximum_single_day_profit_pct": 10.0,
        "maximum_daily_return_pct": 10.0,
        "daily_profit_cap_pct": None,
        "minimum_consistency_score": 50.0,
    },
    "targets": {
        "profit_target_dollars": 2500.0,
        "profit_target_pct": 10.0,
        "minimum_evaluation_days": 10,
        "maximum_evaluation_days": 252,
        "required_account_buffer_pct": 0.0,
        "payout_threshold": None,
        "minimum_balance_before_payout": None,
    },
    "execution_overrides": {
        "position_sizing_model": "equal_weight",
        "fixed_dollar_sizing": None,
        "equal_weight_sizing": True,
        "volatility_adjusted_sizing": False,
        "maximum_selected_candidates_per_day": 7,
        "minimum_confidence_threshold": None,
        "minimum_expected_return_threshold": None,
        "maximum_allowed_risk_category": None,
        "hold_period_override_days": None,
        "stop_loss_override_pct": None,
        "take_profit_override_pct": None,
        "regime_filter_enabled": False,
        "sector_filter_enabled": False,
    },
}


BUILT_IN_PRESETS: List[Dict[str, Any]] = []


def deep_merge(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def environment_from_overrides(overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return deep_merge(DEFAULT_ENVIRONMENT, overrides or {})


def builtin_presets() -> List[Dict[str, Any]]:
    if BUILT_IN_PRESETS:
        return deepcopy(BUILT_IN_PRESETS)

    presets = [
        DEFAULT_ENVIRONMENT,
        environment_from_overrides({
            "environment_id": "conservative_swing_account",
            "name": "Conservative Swing Account",
            "account_rules": {
                "minimum_cash_reserve_pct": 25.0,
                "maximum_invested_pct": 70.0,
                "maximum_open_positions": 5,
                "maximum_position_allocation_pct": 12.0,
            },
            "risk_limits": {
                "daily_loss_limit_pct": 2.5,
                "overall_max_drawdown_pct": 8.0,
                "trailing_drawdown_pct": 8.0,
            },
        }),
        environment_from_overrides({
            "environment_id": "small_account_challenge",
            "name": "Small Account Challenge",
            "account_rules": {
                "starting_capital": 5000.0,
                "minimum_cash_reserve_pct": 5.0,
                "maximum_open_positions": 4,
                "maximum_position_allocation_pct": 25.0,
            },
            "targets": {"profit_target_pct": 10.0, "profit_target_dollars": 500.0},
        }),
        environment_from_overrides({
            "environment_id": "aggressive_growth_account",
            "name": "Aggressive Growth Account",
            "account_rules": {
                "minimum_cash_reserve_pct": 0.0,
                "maximum_invested_pct": 100.0,
                "maximum_open_positions": 10,
                "maximum_position_allocation_pct": 25.0,
            },
            "risk_limits": {
                "daily_loss_limit_pct": 6.0,
                "overall_max_drawdown_pct": 20.0,
                "trailing_drawdown_pct": 20.0,
            },
        }),
        environment_from_overrides({
            "environment_id": "strict_funded_style_account",
            "name": "Strict Funded-Style Account",
            "account_rules": {
                "starting_capital": 100000.0,
                "minimum_cash_reserve_pct": 10.0,
                "maximum_open_positions": 5,
                "maximum_position_allocation_pct": 10.0,
            },
            "risk_limits": {
                "daily_loss_limit_pct": 2.0,
                "overall_max_drawdown_pct": 6.0,
                "trailing_drawdown_amount": 5000.0,
                "trailing_drawdown_pct": 5.0,
            },
            "targets": {"profit_target_pct": 8.0, "profit_target_dollars": 8000.0},
        }),
        environment_from_overrides({
            "environment_id": "trailing_drawdown_evaluation",
            "name": "Trailing Drawdown Evaluation",
            "risk_limits": {
                "trailing_drawdown_amount": 2500.0,
                "trailing_drawdown_pct": 8.0,
                "trailing_drawdown_method": "end_of_day_peak",
            },
        }),
        environment_from_overrides({
            "environment_id": "daily_loss_limit_evaluation",
            "name": "Daily Loss Limit Evaluation",
            "risk_limits": {"daily_loss_limit_pct": 2.0, "daily_loss_limit_dollars": 500.0},
        }),
        environment_from_overrides({
            "environment_id": "consistency_rule_evaluation",
            "name": "Consistency Rule Evaluation",
            "consistency_rules": {
                "maximum_profit_from_one_day_pct": 40.0,
                "maximum_profit_from_one_trade_pct": 25.0,
                "minimum_consistency_score": 60.0,
            },
        }),
        environment_from_overrides({
            "environment_id": "no_overnight_holdings_evaluation",
            "name": "No Overnight Holdings Evaluation",
            "trading_restrictions": {
                "overnight_holding_allowed": False,
                "forced_end_of_day_liquidation": True,
            },
        }),
        environment_from_overrides({
            "environment_id": "custom_environment",
            "name": "Custom Environment",
            "preset_source": "custom_local",
        }),
    ]

    return deepcopy(presets)


def validate_environment(environment: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    account = environment.get("account_rules", {})
    risk = environment.get("risk_limits", {})
    restrictions = environment.get("trading_restrictions", {})
    consistency = environment.get("consistency_rules", {})
    targets = environment.get("targets", {})

    def pct(name: str, value: Any) -> None:
        if value is not None and not (0 <= float(value) <= 100):
            errors.append(f"{name} must be between 0% and 100%.")

    pct("Cash reserve", account.get("minimum_cash_reserve_pct"))
    pct("Maximum invested percentage", account.get("maximum_invested_pct"))
    pct("Position allocation", account.get("maximum_position_allocation_pct"))
    pct("Consistency rule", consistency.get("maximum_profit_from_one_day_pct"))
    pct("Maximum sector exposure", risk.get("maximum_sector_exposure_pct"))

    if float(account.get("starting_capital", 0)) <= 0:
        errors.append("Starting capital must be positive.")
    if float(targets.get("profit_target_pct", 0)) <= 0 and float(targets.get("profit_target_dollars", 0)) <= 0:
        errors.append("Profit target must be positive.")
    if int(account.get("maximum_open_positions", 0)) < 1:
        errors.append("Maximum positions must be at least 1.")
    if float(account.get("maximum_position_allocation_pct", 0)) <= 0:
        errors.append("Position allocation must be greater than 0%.")
    if float(account.get("maximum_position_allocation_pct", 0)) > float(account.get("maximum_invested_pct", 100)):
        errors.append("Position allocation cannot exceed maximum invested percentage.")
    if int(targets.get("minimum_evaluation_days", 0)) > int(targets.get("maximum_evaluation_days", 999999)):
        errors.append("Minimum trading days cannot exceed maximum evaluation days.")
    if risk.get("trailing_drawdown_amount") and not risk.get("trailing_drawdown_method"):
        errors.append("Trailing drawdown requires a trailing method.")
    if restrictions.get("forced_end_of_day_liquidation") and restrictions.get("overnight_holding_allowed"):
        errors.append("Forced end-of-day liquidation conflicts with overnight holding.")
    if restrictions.get("long_only") and restrictions.get("short_selling_allowed"):
        errors.append("Long-only mode conflicts with short selling.")
    if account.get("margin_enabled") and float(account.get("maximum_leverage", 0)) < 1.0:
        errors.append("Leverage must be at least 1.0 when margin is enabled.")
    if float(risk.get("daily_loss_limit_pct", 0)) > float(risk.get("overall_max_drawdown_pct", 100)):
        warnings.append("Daily loss limit is greater than the overall drawdown limit.")
    if float(risk.get("maximum_sector_exposure_pct", 0)) > float(account.get("maximum_invested_pct", 100)):
        errors.append("Maximum sector exposure cannot exceed total invested percentage.")
    for label in ["stop_loss_override_pct", "take_profit_override_pct"]:
        value = environment.get("execution_overrides", {}).get(label)
        if value is not None and float(value) <= 0:
            errors.append(f"{label.replace('_', ' ')} must be positive.")

    return errors, warnings
