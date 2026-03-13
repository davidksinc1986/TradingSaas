from app.models import PlanConfig, PricingConfig


def ensure_pricing_seed(db):
    pricing = db.query(PricingConfig).first()
    if not pricing:
        pricing = PricingConfig(
            base_commission_usd=15.0,
            cost_per_app_usd=2.5,
            cost_per_symbol_usd=0.3,
            cost_per_movement_usd=0.15,
            cost_per_gb_ram_usd=2.0,
            cost_per_gb_disk_usd=0.1,
            suggested_ram_per_app_gb=1.0,
            suggested_disk_per_app_gb=3.0,
        )
        db.add(pricing)

    if db.query(PlanConfig).count() == 0:
        db.add_all([
            PlanConfig(
                name="Plan Básico",
                description="Ideal para empezar con bajo riesgo.",
                apps=3,
                symbols=15,
                daily_movements=20,
                monthly_price_usd=20,
                is_custom=False,
                sort_order=1,
            ),
            PlanConfig(
                name="Plan Pro",
                description="Más capacidad para ejecución diaria.",
                apps=5,
                symbols=35,
                daily_movements=60,
                monthly_price_usd=49,
                is_custom=False,
                sort_order=2,
            ),
            PlanConfig(
                name="Plan Custom",
                description="Personaliza apps, símbolos y movimientos.",
                apps=0,
                symbols=0,
                daily_movements=0,
                monthly_price_usd=0,
                is_custom=True,
                sort_order=3,
            ),
        ])


def estimate_monthly_cost(pricing: PricingConfig, apps: int, symbols: int, daily_movements: int):
    estimated_ram_gb = max(apps * pricing.suggested_ram_per_app_gb, 1)
    estimated_disk_gb = max(apps * pricing.suggested_disk_per_app_gb, 3)

    infra_cost = (
        (apps * pricing.cost_per_app_usd)
        + (symbols * pricing.cost_per_symbol_usd)
        + (daily_movements * pricing.cost_per_movement_usd)
        + (estimated_ram_gb * pricing.cost_per_gb_ram_usd)
        + (estimated_disk_gb * pricing.cost_per_gb_disk_usd)
    )
    total = infra_cost + pricing.base_commission_usd

    return {
        "apps": apps,
        "symbols": symbols,
        "daily_movements": daily_movements,
        "estimated_ram_gb": round(estimated_ram_gb, 2),
        "estimated_disk_gb": round(estimated_disk_gb, 2),
        "infra_cost_usd": round(infra_cost, 2),
        "base_commission_usd": round(pricing.base_commission_usd, 2),
        "estimated_total_usd": round(total, 2),
    }
