from datetime import datetime
from config import BOT_NAME


def format_welcome_message() -> str:
    return (
        f"✨ <b>Добро пожаловать в \"{BOT_NAME}\"!</b> ✨\n\n"
        f"<blockquote>Наши преимущества:\n"
        f"• 🚀 Высокая скорость соединения\n"
        f"• 🔒 Надежная защита данных\n"
        f"• 🌍 Доступ к мировому контенту\n"
        f"• 💰 Доступные цены\n"
        f"• 📱 Поддержка всех устройств</blockquote>\n\n"
        f"<i>Подключайся и почувствуй свободу интернета!</i>"
    )


def format_subscription_created_message(
    tariff_days: int,
    traffic_gb: float,
    devices_limit: int,
    end_date: datetime,
    config_link: str,
    device_type: str
) -> str:
    return (
        f"✅ <b>Подписка успешно создана!</b> 🎉\n\n"
        f"📦 <b>Информация о тарифе:</b>\n"
        f"🕒 Тариф: {'Пробный тариф на 3 дня - 0р' if tariff_days == 3 else f'{tariff_days} дней'}\n"
        f"📊 Трафик: {traffic_gb} ГБ\n"
        f"📱 Лимит устройств: {devices_limit}\n\n"
        f"<b>Добавьте подписку в приложение — это просто:</b>\n\n"
        f"📲 <b>Ссылка для подключения {device_type.upper()}:</b>\n"
        f"<code>{config_link}</code>\n\n"
        f"<i>Если у вас возникнут вопросы, не стесняйтесь обращаться в поддержку.</i>"
    )


def format_profile_message(user, subscription) -> str:
    from database.db_manager import get_usd_rate
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
        usd_rate = loop.run_until_complete(get_usd_rate())
    except:
        usd_rate = 78.3
    
    rub = user.balance
    usdt = rub / usd_rate if usd_rate > 0 else 0
    stars = int(rub)
    
    profile_text = (
        f"👤 <b>ПРОФИЛЬ</b>\n"
        f"<blockquote>📝 Имя: {user.first_name or user.username or 'Пользователь'}\n"
        f"🆔 ID: <code>{user.telegram_id}</code>\n"
        f"💰 Баланс: <b>{rub:.2f} ₽</b> | ⭐ {stars} Stars | 💎 {usdt:.2f} USDT</blockquote>\n\n"
    )
    
    if subscription:
        remaining_traffic = subscription.remaining_traffic_gb
        used_percent = (subscription.used_traffic_gb / subscription.total_traffic_gb * 100) if subscription.total_traffic_gb > 0 else 0
        
        progress_bar_length = 20
        filled_length = int(progress_bar_length * used_percent / 100)
        bar = "█" * filled_length + "░" * (progress_bar_length - filled_length)
        
        profile_text += (
            f"🔑 <b>ВАША ПОДПИСКА</b>\n"
            f"<blockquote>📦 <b>Информация о тарифе:</b>\n"
            f"💎 Тариф: {'Пробный тариф на 3 дня - 0р' if subscription.is_trial else f'{subscription.tariff_days} дней'}\n"
            f"📊 Трафик: {subscription.used_traffic_gb:.1f} / {subscription.total_traffic_gb} ГБ\n"
            f"📊 Прогресс: {bar} {used_percent:.0f}%\n"
        )
        
        if remaining_traffic <= 1:
            profile_text += f"🔥 <b>Хочешь безлимит? Продли подписку!</b>\n"
        
        profile_text += (
            f"📱 Лимит устройств: {subscription.devices_limit}\n"
            f"📅 Срок действия: {subscription.end_date.strftime('%d %B %Y года, %H:%M')} (МСК)</blockquote>\n\n"
            f"💡 Используйте кнопки ниже для управления подпиской"
        )
    else:
        profile_text += (
            f"🔑 <b>ВАША ПОДПИСКА</b>\n"
            f"<blockquote>❌ <b>Нет активной подписки</b>\n\n"
            f"💡 Нажмите «Продление подписки», чтобы выбрать тариф</blockquote>"
        )
    
    return profile_text
def format_tariff_info(tariff_days: int, base_price: float, device_price: float, max_devices: int) -> str:
    return (
        f"📅 <b>{tariff_days} дней</b>\n"
        f"💰 Базовая стоимость: {base_price} ₽\n\n"
        f"<b>Настройка тарифа:</b>\n"
        f"Базово: 1 устройство\n"
        f"Сейчас: 1 устройство\n\n"
        f"➕ За каждое дополнительное устройство +{device_price} ₽\n"
        f"📱 Доступно до {max_devices} устройств\n\n"
        f"<i>При необходимости измените параметры ниже и подтвердите оплату.</i>"
    )