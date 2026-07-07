"""Telegram bot (aiogram polling). Config: root .env via Settings."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.config import Settings


class TelegramBot:
    def __init__(self, settings: Settings, logger: logging.Logger) -> None:
        self.settings = settings
        self.logger = logger
        self._bot: Bot | None = None
        self._dp: Dispatcher | None = None

    def _ensure_bot(self) -> tuple[Bot, Dispatcher]:
        if self._bot is None:
            self._bot = Bot(token=self.settings.bot_token)
            self._dp = Dispatcher()
            self._register_handlers(self._dp)
        return self._bot, self._dp  # type: ignore[return-value]

    def _register_handlers(self, dp: Dispatcher) -> None:
        settings = self.settings

        @dp.message(Command("start"))
        async def cmd_start(message: Message) -> None:
            builder = InlineKeyboardBuilder()
            builder.button(
                text="Открыть Task Tracker",
                web_app=WebAppInfo(url=settings.webapp_url),
            )
            await message.answer(
                "Добро пожаловать в Task Tracker!\n"
                "Нажмите кнопку ниже, чтобы открыть mini app.",
                reply_markup=builder.as_markup(),
            )

    async def run(self) -> None:
        bot, dp = self._ensure_bot()
        self.logger.info("Starting Telegram bot polling")
        try:
            await dp.start_polling(bot, handle_signals=False)
        except asyncio.CancelledError:
            self.logger.info("Telegram bot polling cancelled")
            raise

    async def stop(self) -> None:
        if self._dp is not None:
            await self._dp.stop_polling()
        if self._bot is not None:
            await self._bot.session.close()
        self._bot = None
        self._dp = None
        self.logger.info("Telegram bot stopped")
