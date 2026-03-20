from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _placeholder_class(name: str):
    return type(name, (), {})


def _load_api_module():
    fastapi_module = types.ModuleType("fastapi")

    class HTTPException(Exception):
        def __init__(self, status_code: int = 500, detail: str | None = None):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class APIRouter:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def _decorator(self, fn):
            return fn

        get = post = put = delete = api_route = lambda self, *args, **kwargs: self._decorator

    fastapi_module.APIRouter = APIRouter
    fastapi_module.BackgroundTasks = _placeholder_class("BackgroundTasks")
    fastapi_module.Depends = lambda dependency=None: dependency
    fastapi_module.HTTPException = HTTPException
    sys.modules["fastapi"] = fastapi_module

    fastapi_responses = types.ModuleType("fastapi.responses")
    fastapi_responses.StreamingResponse = _placeholder_class("StreamingResponse")
    sys.modules["fastapi.responses"] = fastapi_responses

    app_module = types.ModuleType("app")
    sys.modules["app"] = app_module

    db_module = types.ModuleType("app.db")
    db_module.get_db = lambda: None
    sys.modules["app.db"] = db_module
    app_module.db = db_module

    core_module = types.ModuleType("app.core")
    core_module.settings = types.SimpleNamespace(
        admin_email="davidksinc@gmail.com",
        telegram_admin_bot_token="root-token",
        telegram_admin_chat_id="root-chat",
    )
    sys.modules["app.core"] = core_module
    app_module.core = core_module

    models_module = types.ModuleType("app.models")
    for name in [
        "BotSession",
        "Connector",
        "OpenPosition",
        "PlanConfig",
        "PlatformPolicy",
        "PricingConfig",
        "StrategyTemplate",
        "TradeLog",
        "TradeRun",
        "User",
        "UserPlatformGrant",
        "UserStrategyControl",
    ]:
        setattr(models_module, name, _placeholder_class(name))
    sys.modules["app.models"] = models_module
    app_module.models = models_module

    deps_module = types.ModuleType("app.routers.deps")
    deps_module.admin_user = lambda user=None: user
    deps_module.current_user = lambda user=None: user
    sys.modules["app.routers.deps"] = deps_module

    schemas_module = types.ModuleType("app.schemas")
    for name in [
        "AdminUserCreate",
        "AdminGrantUpdate",
        "AdminPlanConfigPayload",
        "AdminPolicyUpdate",
        "AdminPricingConfigUpdate",
        "AdminStrategyControlUpdate",
        "AdminUserUpdate",
        "BotSessionCopyPayload",
        "BotSessionCreate",
        "BotSessionUpdate",
        "ConnectorCreate",
        "ConnectorUpdate",
        "StrategyRequest",
        "StrategyControlUpdate",
        "StrategyTemplateApplyPayload",
        "StrategyTemplateCreate",
        "TradingViewWebhook",
    ]:
        setattr(schemas_module, name, _placeholder_class(name))
    sys.modules["app.schemas"] = schemas_module

    security_module = types.ModuleType("app.security")
    security_module.decrypt_payload = lambda payload: payload or {}
    security_module.encrypt_payload = lambda payload: payload
    security_module.hash_password = lambda password: f"hashed:{password}"
    sys.modules["app.security"] = security_module

    alerts_module = types.ModuleType("app.services.alerts")
    alerts_module.TelegramDeliveryError = type("TelegramDeliveryError", (Exception,), {})
    alerts_module.format_failure_message = lambda scope, detail: f"{scope}:{detail}"
    alerts_module.format_user_failure_message = lambda **kwargs: "failure"
    alerts_module.format_user_info_message = lambda **kwargs: "info"
    alerts_module.normalize_alert_locale = lambda value: value or "es"
    alerts_module.send_admin_user_alert_sync = lambda *args, **kwargs: True
    alerts_module.send_telegram_alert_sync = lambda *args, **kwargs: True
    alerts_module.send_user_telegram_test_alert = lambda *args, **kwargs: True
    sys.modules["app.services.alerts"] = alerts_module

    connector_state_module = types.ModuleType("app.services.connector_state")
    connector_state_module.PLATFORM_MARKET_TYPES = {}
    connector_state_module.ensure_connector_market_type_state = lambda connector, persist=True, db=None: getattr(connector, "market_type", "spot")
    connector_state_module.normalize_market_type = lambda value: (value or "spot")
    connector_state_module.resolve_connector_market_type = lambda platform, market_type=None, config=None: market_type or "spot"
    connector_state_module.resolve_runtime_market_type = lambda connector, requested_market_type=None: requested_market_type or getattr(connector, "market_type", "spot")
    connector_state_module.sync_connector_config_market_type = lambda config, market_type: config or {}
    sys.modules["app.services.connector_state"] = connector_state_module

    simple_service_modules = {
        "app.services.connectors": {"get_client": lambda connector: None},
        "app.services.market": {"price_check": lambda **kwargs: {}},
        "app.services.policies": {
            "ensure_user_grants": lambda *args, **kwargs: None,
            "get_user_grant": lambda *args, **kwargs: None,
            "validate_connector_request": lambda *args, **kwargs: None,
        },
        "app.services.pricing": {"estimate_monthly_cost": lambda *args, **kwargs: 0},
        "app.services.position_lifecycle": {"trigger_kill_switch": lambda *args, **kwargs: {}},
        "app.services.trading": {
            "activity_metrics": lambda *args, **kwargs: {},
            "dashboard_data": lambda *args, **kwargs: {},
            "run_strategy": lambda *args, **kwargs: [],
            "sync_positions_with_exchange": lambda *args, **kwargs: {},
        },
        "app.services.strategies": {
            "ALL_STRATEGIES": ["ema_rsi"],
            "get_strategy_rule": lambda slug: {"market_types": ["spot", "futures"]},
        },
    }
    for module_name, attrs in simple_service_modules.items():
        module = types.ModuleType(module_name)
        for key, value in attrs.items():
            setattr(module, key, value)
        sys.modules[module_name] = module

    module_path = Path(__file__).resolve().parents[1] / "app" / "routers" / "api.py"
    spec = importlib.util.spec_from_file_location("api_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_main_module():
    fastapi_module = types.ModuleType("fastapi")

    class _FakeFastAPI:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def mount(self, *args, **kwargs):
            return None

        def include_router(self, *args, **kwargs):
            return None

        def add_middleware(self, *args, **kwargs):
            return None

        def on_event(self, *_args, **_kwargs):
            return lambda fn: fn

        def get(self, *_args, **_kwargs):
            return lambda fn: fn

    fastapi_module.FastAPI = _FakeFastAPI
    fastapi_module.Request = _placeholder_class("Request")
    sys.modules["fastapi"] = fastapi_module

    staticfiles_module = types.ModuleType("fastapi.staticfiles")

    class _FakeStaticFiles:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    staticfiles_module.StaticFiles = _FakeStaticFiles
    sys.modules["fastapi.staticfiles"] = staticfiles_module

    middleware_module = types.ModuleType("starlette.middleware.base")
    middleware_module.BaseHTTPMiddleware = _placeholder_class("BaseHTTPMiddleware")
    sys.modules["starlette.middleware.base"] = middleware_module

    sqlalchemy_module = types.ModuleType("sqlalchemy")
    sqlalchemy_module.inspect = lambda engine: types.SimpleNamespace(has_table=lambda name: False)
    sqlalchemy_module.text = lambda value: value
    sys.modules["sqlalchemy"] = sqlalchemy_module

    app_module = types.ModuleType("app")
    sys.modules["app"] = app_module

    core_module = types.ModuleType("app.core")
    core_module.settings = types.SimpleNamespace(
        app_name="Test App",
        admin_email="davidksinc@gmail.com",
        admin_name="davidksinc",
        admin_password="secret",
        telegram_admin_bot_token="root-token",
        telegram_admin_chat_id="root-chat",
    )
    sys.modules["app.core"] = core_module
    app_module.core = core_module

    db_module = types.ModuleType("app.db")
    db_module.Base = types.SimpleNamespace(metadata=types.SimpleNamespace(create_all=lambda bind=None: None))
    db_module.SessionLocal = lambda: None
    db_module.engine = object()
    sys.modules["app.db"] = db_module
    app_module.db = db_module

    models_module = types.ModuleType("app.models")

    class User:
        def __init__(self, **kwargs):
            self.alert_language = None
            self.telegram_alerts_enabled = False
            self.telegram_bot_token_encrypted = None
            self.telegram_chat_id_encrypted = None
            for key, value in kwargs.items():
                setattr(self, key, value)

    for name in ["BotSession", "StrategyProfile", "StrategyTemplate", "UserStrategyControl"]:
        setattr(models_module, name, _placeholder_class(name))
    models_module.User = User
    sys.modules["app.models"] = models_module
    app_module.models = models_module

    routers_module = types.ModuleType("app.routers")
    routers_module.api = types.SimpleNamespace(router=object())
    routers_module.auth = types.SimpleNamespace(router=object())
    routers_module.views = types.SimpleNamespace(router=object())
    sys.modules["app.routers"] = routers_module

    security_module = types.ModuleType("app.security")
    security_module.encrypt_payload = lambda payload: payload
    security_module.hash_password = lambda password: f"hashed:{password}"
    sys.modules["app.security"] = security_module

    alerts_module = types.ModuleType("app.services.alerts")
    alerts_module.format_failure_message = lambda scope, detail: f"{scope}:{detail}"
    alerts_module.send_telegram_alert = lambda message: True
    sys.modules["app.services.alerts"] = alerts_module

    policies_module = types.ModuleType("app.services.policies")
    policies_module.ensure_user_grants = lambda *args, **kwargs: None
    policies_module.seed_platform_policies = lambda *args, **kwargs: None
    sys.modules["app.services.policies"] = policies_module

    pricing_module = types.ModuleType("app.services.pricing")
    pricing_module.ensure_pricing_seed = lambda *args, **kwargs: None
    sys.modules["app.services.pricing"] = pricing_module

    bot_runner_module = types.ModuleType("app.services.bot_runner")
    bot_runner_module.start_bot_worker = lambda: None
    bot_runner_module.stop_bot_worker = lambda: None
    sys.modules["app.services.bot_runner"] = bot_runner_module

    module_path = Path(__file__).resolve().parents[1] / "app" / "main.py"
    spec = importlib.util.spec_from_file_location("main_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_trade_run_reason_codes_include_summary_and_status_derivation():
    api = _load_api_module()
    run = types.SimpleNamespace(status="skipped_low_confidence", notes="")
    parsed_note = {
        "decision_summary": {
            "primary_reason": "strategy_hold",
            "reason_codes": ["strategy_hold", "low_confidence"],
        }
    }

    reason_codes = api._trade_run_reason_codes(run, parsed_note)

    assert reason_codes == ["strategy_hold", "low_confidence"]


def test_operational_states_prioritize_requested_reporting_labels():
    api = _load_api_module()
    parsed_note = {
        "circuit_breaker_triggered": True,
        "market_quality": {"anomalies": {"severity": "warning", "issues": ["volatility_spike"]}},
    }

    states = api._operational_states_from_reason_codes(
        ["low_confidence", "signal_hold", "risk_engine_blocked", "exchange_rejected"],
        parsed_note,
    )

    assert states == [
        "volatilidad_excesiva",
        "mercado_lateral_ruidoso",
        "baja_calidad_de_senal",
        "riesgo_global_alto",
        "problemas_tecnicos",
    ]


def test_trade_run_connector_snapshot_falls_back_to_notes_when_connector_missing():
    api = _load_api_module()

    snapshot = api._trade_run_connector_snapshot(
        None,
        {
            "connector": {
                "id": 33,
                "label": "Binance principal",
                "platform": "binance",
                "market_type": "futures",
            }
        },
    )

    assert snapshot["connector_id"] == 33
    assert snapshot["connector_label"] == "Binance principal"
    assert snapshot["platform"] == "binance"
    assert snapshot["market_type"] == "futures"


def test_trade_run_connector_snapshot_prefers_live_connector_when_available():
    api = _load_api_module()
    connector = types.SimpleNamespace(id=9, label="Bybit Alpha", platform="bybit", market_type="spot")

    snapshot = api._trade_run_connector_snapshot(
        connector,
        {"connector": {"label": "stale", "platform": "binance", "market_type": "futures"}},
    )

    assert snapshot["connector_id"] == 9
    assert snapshot["connector_label"] == "Bybit Alpha"
    assert snapshot["platform"] == "bybit"
    assert snapshot["market_type"] == "spot"


def test_sync_root_admin_telegram_overwrites_admin_profile_with_settings():
    main = _load_main_module()
    admin = main.User(email="admin@example.com", name="davidksinc", hashed_password="x")

    main._sync_root_admin_telegram(admin)

    assert admin.telegram_alerts_enabled is True
    assert admin.telegram_bot_token_encrypted["value"] == "root-token"
    assert admin.telegram_chat_id_encrypted["value"] == "root-chat"
    assert admin.alert_language == "es"
