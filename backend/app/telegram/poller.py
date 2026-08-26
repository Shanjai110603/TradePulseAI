import asyncio
import logging
import httpx
from typing import Optional
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.telegram.bot import telegram_service
from app.telegram.handlers import TelegramUpdateHandler

logger = logging.getLogger(__name__)


class TelegramLongPoller:
    """
    Asynchronous long-polling service for Telegram Bot API.
    Continuously listens for Telegram messages, commands, and callback query
    button clicks without requiring a public HTTPS webhook domain.
    """

    def __init__(self):
        self._is_running = False
        self._task: Optional[asyncio.Task] = None
        self._offset = 0
        self.bot_username: Optional[str] = None

    def start(self):
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            logger.info("No TELEGRAM_BOT_TOKEN provided; Telegram polling disabled (running in simulated/test mode).")
            return

        if not self._is_running:
            self._is_running = True
            self._task = asyncio.create_task(self._poll_loop())
            logger.info("Telegram Long Polling worker started.")

    def stop(self):
        self._is_running = False
        if self._task:
            self._task.cancel()
            logger.info("Telegram Long Polling worker stopped.")

    async def _poll_loop(self):
        token = settings.TELEGRAM_BOT_TOKEN
        base_url = f"https://api.telegram.org/bot{token}"

        # 1. Verify Bot Token and Fetch Bot Info
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                me_resp = await client.get(f"{base_url}/getMe")
                if me_resp.status_code == 200:
                    me_data = me_resp.json().get("result", {})
                    self.bot_username = me_data.get("username")
                    logger.info(f"Connected to Telegram Bot: @{self.bot_username} (ID: {me_data.get('id')})")
                else:
                    logger.warning(f"Telegram getMe failed with status {me_resp.status_code}: {me_resp.text}")
            except Exception as e:
                logger.error(f"Failed to connect to Telegram getMe: {e}")

        # 2. Continuous Polling Loop
        while self._is_running:
            try:
                async with httpx.AsyncClient(timeout=35.0) as client:
                    resp = await client.get(
                        f"{base_url}/getUpdates",
                        params={
                            "offset": self._offset,
                            "timeout": 20,
                            "allowed_updates": ["message", "callback_query"]
                        }
                    )

                    if resp.status_code == 200:
                        data = resp.json()
                        updates = data.get("result", [])

                        for update in updates:
                            update_id = update.get("update_id", 0)
                            self._offset = max(self._offset, update_id + 1)

                            # Process update within database session
                            async with AsyncSessionLocal() as db:
                                try:
                                    await TelegramUpdateHandler.process_update(update, db)
                                except Exception as err:
                                    logger.error(f"Error processing Telegram update {update_id}: {err}", exc_info=True)

                    elif resp.status_code == 409:
                        logger.warning("Telegram polling conflict (webhook active or another instance running). Sleeping 10s...")
                        await asyncio.sleep(10)
                    else:
                        logger.warning(f"Telegram getUpdates returned status {resp.status_code}: {resp.text}")
                        await asyncio.sleep(5)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Telegram poller: {e}")
                await asyncio.sleep(5)


telegram_poller = TelegramLongPoller()
