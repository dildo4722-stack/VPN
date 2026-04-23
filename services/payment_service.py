from integrations.crypto_bot_api import crypto_bot
from database.db_manager import get_user, create_subscription, get_usd_rate


async def create_crypto_payment(user_id: int, amount_usdt: float, tariff_days: int, devices_count: int):
    """Создание платежа в USDT"""
    usd_rate = await get_usd_rate()
    amount_rub = amount_usdt * usd_rate
    return await crypto_bot.create_invoice(user_id, amount_rub, tariff_days, devices_count, usd_rate)


async def check_crypto_payment(invoice_id: int):
    return await crypto_bot.check_payment(invoice_id)


async def activate_subscription_after_payment(user_id: int, tariff_days: int, devices_count: int):
    user = await get_user(user_id)
    if user:
        await create_subscription(user.id, tariff_days, devices_count, 0)
        return True
    return False