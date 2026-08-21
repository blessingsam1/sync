from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AdminAction, BotEvent


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bot_event(
        self,
        bot_name: str,
        event_type: str,
        telegram_id: int | None,
        details: dict | None = None,
    ) -> None:
        self.session.add(
            BotEvent(
                bot_name=bot_name,
                event_type=event_type,
                telegram_id=telegram_id,
                details=details or {},
            )
        )
        await self.session.commit()

    async def admin_action(
        self,
        admin_telegram_id: int,
        action: str,
        target_type: str | None = None,
        target_id: str | None = None,
        details: dict | None = None,
    ) -> None:
        self.session.add(
            AdminAction(
                admin_telegram_id=admin_telegram_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                details=details or {},
            )
        )
        await self.session.commit()

