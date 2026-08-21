from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📈 Copytrade"),
                KeyboardButton(text="🤖 Autotrade"),
            ],
            [
                KeyboardButton(text="📊 Live Charts"),
                KeyboardButton(text="💼 Wallet"),
            ],
            [
                KeyboardButton(text="📖 Bot Guide"),
                KeyboardButton(text="🔑 Import Wallet"),
                KeyboardButton(text="⚙️ Settings"),
            ],
            [KeyboardButton(text="⏰ Auto Deposit")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def continue_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Continue ➡️", callback_data="user:continue")]
        ]
    )


def back_to_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="user:home")]
        ]
    )


def wallet_import_method_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Recovery Phrase", callback_data="wallet_import:recovery_phrase"
                ),
                InlineKeyboardButton(
                    text="Private Key", callback_data="wallet_import:private_key"
                ),
            ]
        ]
    )


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💼 Account & Wallet", callback_data="settings:account")],
            [InlineKeyboardButton(text="📊 Trading & Network", callback_data="settings:trading")],
            [InlineKeyboardButton(text="🔔 Alerts & Notifications", callback_data="settings:notifications")],
        ]
    )


def back_to_settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="user:settings")]
        ]
    )


def notifications_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="← Back", callback_data="user:settings")]
        ]
    )


def trading_settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="← Back", callback_data="user:settings")],
        ]
    )


def settings_return_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Settings", callback_data="user:settings")]
        ]
    )


def wallet_actions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Refresh Balance", callback_data="user:wallet"
                )
            ],
            [
                InlineKeyboardButton(text="🛒 Buy", callback_data="user:wallet"),
                InlineKeyboardButton(text="💰 Sell", callback_data="user:wallet"),
            ],
            [InlineKeyboardButton(text="🔄 Transfer", callback_data="user:wallet")],
        ]
    )


def insufficient_transfer_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️ Back", callback_data="user:wallet"),
                InlineKeyboardButton(text="Refresh", callback_data="wallet:transfer"),
            ],
            [InlineKeyboardButton(text="Wallet", callback_data="user:wallet")],
        ]
    )


def trade_chain_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="SOL", callback_data="trade:chain:SOL")],
            [InlineKeyboardButton(text="BNB", callback_data="trade:chain:BNB")],
            [InlineKeyboardButton(text="ETH", callback_data="trade:chain:ETH")],
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="user:home")],
        ]
    )


def transfer_chain_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟣 Solana (SOL)", callback_data="transfer:chain:SOL")],
            [InlineKeyboardButton(text="🟡 BNB Chain (BNB)", callback_data="transfer:chain:BNB")],
            [InlineKeyboardButton(text="🔵 Ethereum (ETH)", callback_data="transfer:chain:ETH")],
            [InlineKeyboardButton(text="Cancel", callback_data="transfer:cancel")],
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="user:home")],
        ]
    )


def transfer_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Confirm Withdrawal", callback_data="transfer:confirm")],
            [InlineKeyboardButton(text="Cancel", callback_data="transfer:cancel")],
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="user:home")],
        ]
    )


def transfer_input_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Cancel", callback_data="transfer:cancel")],
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="user:home")],
        ]
    )


def copytrade_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Stop all ⏹", callback_data="copytrade:stop_all"),
                InlineKeyboardButton(text="Start all ▶️", callback_data="copytrade:start_all"),
            ],
            [
                InlineKeyboardButton(text="Back", callback_data="copytrade:enter"),
                InlineKeyboardButton(text="Main Menu", callback_data="user:home"),
            ],
        ]
    )


def copytrade_input_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    rows = []
    if enabled:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🛑 Stop Copying",
                    callback_data="copytrade:stop",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="🏠 Main Menu", callback_data="user:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def autotrade_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    state_label = "🔴 Disable" if enabled else "🟢 Enable"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=state_label, callback_data="autotrade:toggle"
                ),
                InlineKeyboardButton(text="⛓ Chain", callback_data="autotrade:chain"),
            ],
            [
                InlineKeyboardButton(
                    text="💵 Max Amount", callback_data="autotrade:edit:maximum_trade_amount"
                ),
                InlineKeyboardButton(
                    text="🔢 Daily Trades", callback_data="autotrade:edit:maximum_daily_trades"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🎚 Slippage", callback_data="autotrade:edit:slippage"
                ),
                InlineKeyboardButton(
                    text="🧠 Strategy", callback_data="autotrade:strategy"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🎯 Take Profit", callback_data="autotrade:edit:take_profit"
                ),
                InlineKeyboardButton(
                    text="🛡 Stop Loss", callback_data="autotrade:edit:stop_loss"
                ),
            ],
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="user:home")],
        ]
    )


def chain_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🟣 SOL Mainnet", callback_data="autotrade:chain:solana"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔵 ETH Mainnet", callback_data="autotrade:chain:ethereum"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🟡 BNB Mainnet", callback_data="autotrade:chain:bnb"
                )
            ],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="user:autotrade")],
        ]
    )


def strategy_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Conservative", callback_data="autotrade:strategy:conservative"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Balanced", callback_data="autotrade:strategy:balanced"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Aggressive", callback_data="autotrade:strategy:aggressive"
                )
            ],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="user:autotrade")],
        ]
    )


def auto_deposit_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👤 SOL Mainnet", callback_data="deposit:solana"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👤 ETH Mainnet", callback_data="deposit:ethereum"
                )
            ],
            [
                InlineKeyboardButton(text="👤 BNB Mainnet", callback_data="deposit:bnb")
            ],
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="user:home")],
        ]
    )


def auto_deposit_interval_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="12 Hours", callback_data="auto_deposit:set:12")],
            [InlineKeyboardButton(text="24 Hours", callback_data="auto_deposit:set:24")],
            [InlineKeyboardButton(text="🛑 Turn Off", callback_data="auto_deposit:off")],
        ]
    )
