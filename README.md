# Private Testnet Telegram Trading Bot

Two Telegram bots share one FastAPI application layer and PostgreSQL database:

```text
Telegram testers -> User bot  -> application services -> PostgreSQL
Project admins   -> Admin bot -> application services -> PostgreSQL
                                      |
                                Trading service
                                      |
                              testnet-only adapters
```

This repository is deliberately restricted to Ethereum Sepolia, BNB Smart Chain
Testnet, and Solana Devnet. It never generates wallets. Project wallet addresses
and keys are supplied through environment variables. User-visible balances are
internal database accounting balances, not blockchain balances.

## Database Schema

- `users`: unique Telegram users and active status.
- `balances`: per-user `Numeric(36,18)` balance, available balance, and locked balance.
- `balance_transactions`: immutable audit trail for admin add/subtract/set operations.
- `trades`: simulated or testnet trade records.
- `transactions`: idempotent testnet transaction records.
- `copytrade_settings`: per-user followed strategy and risk settings.
- `autotrade_settings`: per-user automation, chain, limits, slippage, TP, and SL.
- `admin_actions`: admin audit records without secret values.
- `bot_events`: operational bot events without credentials.

## Directory Structure

```text
app/
  bots/handlers/{user,admin}/
  bots/keyboards/{user,admin}/
  chains/
  config/
  database/models/
  database/repositories/
  schemas/
  security/
  services/
alembic/
tests/
```

## Wallet and Balance Flow

1. `/start` creates only a Telegram user and three zero-valued balance rows.
2. The user wallet screen displays configured project addresses and database balances.
3. It never reads an on-chain balance for the user display.
4. Admin adjustments lock the balance row, use `Decimal`, require a reason and
   confirmation, and write a `balance_transactions` record in the same transaction.
5. Deposits shown by the bot are testnet addresses only and do not credit internal balances.

## Security Model

- `NETWORK_MODE=testnet` is mandatory.
- RPC URLs receive static screening and their chain identity is verified at startup.
- Every adapter call invokes `NetworkGuard`.
- Admin bot access is enforced by middleware for every update.
- Private keys use `SecretStr`, are filtered from logs, and are never stored by default.
- Private-key reveal requires an authorized explicit callback and is rate limited.
- Transaction idempotency is enforced by a unique database key.
- Actual broadcasting defaults off with `TRADING_EXECUTION_ENABLED=false`.

## Setup

```bash
cp .env.example .env
# Fill only testnet bot tokens, wallet credentials, RPC URLs, admin IDs, and a Fernet key.
docker compose up --build
```

Generate `ENCRYPTION_KEY` locally:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

The backend is available at `http://localhost:8000`. Health endpoints:

- `GET /health`
- `GET /health/ready`

## Implementation Phases

1. FastAPI, configuration, SQLAlchemy, Alembic, and bot lifecycle.
2. Configured addresses, user registration, menu, and wallet screen.
3. Admin authentication, notifications, user management, and credential confirmation.
4. Database balance operations and audit records.
5. Copytrade, autotrade, charts, import placeholder, and deposit screens.
6. Testnet-only adapters and idempotent trading service.
7. Tests, containers, documentation, and security verification.

## Important Limitations

- Copytrade, autotrade, and charts are MVP simulations/configuration surfaces.
- `TRADING_EXECUTION_ENABLED=false` keeps transaction broadcasting disabled by default.
- No deposit monitor exists; testnet deposits do not change database balances.
- Telegram messages containing an admin-revealed testnet key are scheduled for deletion,
  but Telegram remains an inherently sensitive channel. Use only disposable testnet keys.

