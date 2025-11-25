import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update
from aiogram.filters import CommandStart
from typing import Any, Awaitable, Callable, Dict

from bot.config import load_config
from bot.database import Database
from bot.handlers import start, rooms, draw

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


class DatabaseMiddleware:
    """Middleware to inject database instance into handlers"""

    def __init__(self, db: Database):
        self.db = db

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        # Inject database instance
        data['db'] = self.db

        # Add user to database if message or callback query
        if event.message and event.message.from_user:
            user = event.message.from_user
            self.db.add_user(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )
        elif event.callback_query and event.callback_query.from_user:
            user = event.callback_query.from_user
            self.db.add_user(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )

        return await handler(event, data)


async def main():
    """Main bot function"""
    # Load configuration
    config = load_config()

    if not config.bot.token:
        logger.error("BOT_TOKEN not found in environment variables!")
        sys.exit(1)

    # Initialize database
    db = Database(config.db.dsn)

    # Wait for database to be ready
    max_retries = 30
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            db.connect()
            logger.info("Successfully connected to database")
            break
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Database connection attempt {attempt + 1}/{max_retries} failed: {e}")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"Failed to connect to database after {max_retries} attempts")
                sys.exit(1)

    # Initialize bot and dispatcher
    bot = Bot(
        token=config.bot.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher()

    # Register middleware
    dp.update.middleware(DatabaseMiddleware(db))

    # Register routers
    dp.include_router(start.router)
    dp.include_router(rooms.router)
    dp.include_router(draw.router)

    logger.info("Bot started")

    try:
        # Start polling
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        # Cleanup
        await bot.session.close()
        db.close()
        logger.info("Bot stopped")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
