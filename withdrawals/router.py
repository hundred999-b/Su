from finance.models import PayoutProviderConfig

from .provider_base import PayoutProviderError


PROVIDER_MODULES = {
    "paystack": "withdrawals.paystack_service",
    "stripe_connect": "withdrawals.stripe_connect_service",
    "airwallex": "withdrawals.airwallex_service",
    "mangopay": "withdrawals.mangopay_service",
    "nowpayments": "withdrawals.nowpayments_service",
}


def get_provider(name):
    name = str(name or "").strip().lower()

    module_name = PROVIDER_MODULES.get(name)

    if not module_name:
        raise PayoutProviderError(
            f"Unsupported payout provider: {name}"
        )

    import importlib

    module = importlib.import_module(module_name)

    provider = getattr(module, "provider", None)

    if provider is None:
        raise PayoutProviderError(
            f"Payout provider adapter is not configured: {name}"
        )

    return provider


def get_enabled_provider(name):
    name = str(name or "").strip().lower()

    config = (
        PayoutProviderConfig.objects
        .filter(provider=name, enabled=True)
        .first()
    )

    if not config:
        raise PayoutProviderError(
            f"Payout provider '{name}' is not enabled in Admin."
        )

    return get_provider(name)


def get_enabled_providers():
    configs = (
        PayoutProviderConfig.objects
        .filter(enabled=True)
        .order_by("priority", "provider")
    )

    providers = []

    for config in configs:
        try:
            provider = get_provider(config.provider)
        except Exception:
            continue

        providers.append((config, provider))

    return providers
