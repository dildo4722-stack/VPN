from aiogram import Router
from aiogram.types import CallbackQuery
from datetime import datetime, timedelta
from database.db_manager import get_user, create_subscription, get_active_subscription
from keyboards.inline_keyboards import get_device_menu, get_main_menu, get_back_button
from utils.text_formatter import format_subscription_created_message
from config import TRIAL_DAYS, TRIAL_TRAFFIC_GB, TRIAL_DEVICES

router = Router()



@router.callback_query(lambda c: c.data == "connect_device")
async def connect_device(callback: CallbackQuery):
    """Временная заглушка для подключения устройства"""
    
    instruction_text = (
        "📖 <b>Инструкция по подключению VPN:</b>\n\n"
        "1️⃣ Скачайте приложение HAPP из официального магазина:\n"
        "   • Android: Google Play\n"
        "   • iOS: App Store\n"
        "   • Windows: с официального сайта\n"
        "   • macOS: App Store\n\n"
        "2️⃣ Скопируйте полученную ссылку,зайдите в приложение и нажмите «Вставить из буфера обмена»\n\n"
        "3️⃣ Вставьте полученную ссылку или файл конфигурации\n\n"
        "4️⃣ Включите VPN и наслаждайтесь свободным интернетом!\n\n"
        "📹 <b>Видео-инструкция:</b>httpstyt-bydet-ssilka\n"
        "📄 <b>Текстовая инструкция:</b> https://telegra.ph/\n\n"
        "💬 Если возникли вопросы - напишите в поддержку!"
    )
    
    await callback.message.edit_text(
        instruction_text,
        reply_markup=get_back_button("back_to_profile", "◀️ Вернуться в профиль"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "select_device")
async def select_device(callback: CallbackQuery):
    await callback.message.edit_text(
        "📱 Выберите ваше устройство:",
        reply_markup=get_device_menu()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("device_"))
async def handle_device_selection(callback: CallbackQuery):
    device_type = callback.data.split("_")[1]

    user = await get_user(callback.from_user.id)
    active_sub = await get_active_subscription(user.id)
    
    if active_sub:
        # заглушка
        config_link = f"https://vpn.example.com/config/{user.id}/{device_type}"
        await callback.message.edit_text(
            f"🔗 Ссылка для подключения {device_type.upper()}:\n"
            f"<code>{config_link}</code>\n\n"
            f"📖 Инструкция по подключению отправлена в чат.",
            reply_markup=get_main_menu()
        )
    else:
        subscription = await create_subscription(
            user_id=user.id,
            tariff_days=TRIAL_DAYS,
            devices_limit=TRIAL_DEVICES,
            total_traffic_gb=TRIAL_TRAFFIC_GB,
            is_trial=True
        )
        
        # заглушка
        config_link = f"https://vpn.example.com/config/{user.id}/{device_type}"
        

        message_text = format_subscription_created_message(
            tariff_days=TRIAL_DAYS,
            traffic_gb=TRIAL_TRAFFIC_GB,
            devices_limit=TRIAL_DEVICES,
            end_date=subscription.end_date,
            config_link=config_link,
            device_type=device_type
        )
        
        await callback.message.edit_text(
            message_text,
            reply_markup=get_main_menu()
        )
    
    await callback.answer()