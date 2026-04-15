import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN
from database.db_manager import init_db
from handlers import start, menu, devices, profile, tariffs, admin
from utils.logger import setup_logger


async def main():
    setup_logger()
    logger = logging.getLogger(__name__)
    

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    

    await init_db()
    logger.info("База данных инициализирована")
    

    dp.include_router(start.router)
    dp.include_router(menu.router)
    dp.include_router(devices.router)
    dp.include_router(profile.router)
    dp.include_router(tariffs.router)
    dp.include_router(admin.router)
    

    logger.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())