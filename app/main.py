from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.bots.runtime import BotRuntime, start_bot_runtime
from app.chains import BnbMainnetAdapter, EthereumMainnetAdapter, SolanaMainnetAdapter
from app.config.settings import Settings, get_settings
from app.database import close_database, initialize_database
from app.security.logging import configure_secret_redaction
from app.security.network_guard import NetworkGuard
from app.security.encryption import SecretEncryption


def create_app(settings_override: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings = settings_override or get_settings()
        settings.validate_runtime()
        configure_secret_redaction(settings)
        SecretEncryption(settings.encryption_key.get_secret_value())

        session_factory = initialize_database(settings.database_url)
        network_guard = NetworkGuard(settings)
        if settings.verify_rpc_on_startup:
            await network_guard.verify_all()

        app.state.settings = settings
        app.state.network_guard = network_guard
        app.state.chain_adapters = {
            "ethereum": EthereumMainnetAdapter(settings, network_guard),
            "bnb": BnbMainnetAdapter(settings, network_guard),
            "solana": SolanaMainnetAdapter(settings, network_guard),
        }

        runtime: BotRuntime | None = None
        if settings.bot_polling_enabled:
            runtime = await start_bot_runtime(settings, session_factory)
        app.state.bot_runtime = runtime

        try:
            yield
        finally:
            if runtime is not None:
                await runtime.stop()
            await close_database()

    app = FastAPI(
        title="Degen, Copytrade and Autotrade Bot",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "network_mode": "mainnet"}

    @app.get("/health/ready")
    async def ready() -> dict[str, object]:
        return {
            "status": "ready",
            "network_mode": app.state.settings.network_mode,
            "rpc_identity_verified": app.state.settings.verify_rpc_on_startup,
            "bot_polling_enabled": app.state.settings.bot_polling_enabled,
        }

    return app


app = create_app()
