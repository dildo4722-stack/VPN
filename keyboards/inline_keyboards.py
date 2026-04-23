from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_menu():
    """Главное меню"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Выбрать устройство", callback_data="select_device")
    builder.button(text="👤 Личный кабинет", callback_data="profile")
    builder.adjust(1)
    return builder.as_markup()


def get_device_menu():
    """Меню выбора устройства"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Android", callback_data="device_android")
    builder.button(text="💻 Windows", callback_data="device_windows")
    builder.button(text="🍎 macOS", callback_data="device_macos")
    builder.button(text="📲 iOS", callback_data="device_ios")
    builder.button(text="◀️ Назад", callback_data="back_to_main")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def get_profile_menu():
    """Меню личного кабинета"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔌 Подключить устройство", callback_data="connect_device")
    builder.button(text="🔄 Продление подписки", callback_data="extend_subscription")
    builder.button(text="💰 Баланс", callback_data="show_balance")
    builder.button(text="🎁 Подарить", callback_data="gift_subscription")
    builder.button(text="🤝 Партнерская программа", callback_data="referral_program")
    builder.button(text="❓ Поддержка", callback_data="support")
    builder.button(text="📜 Пользовательское соглашение", callback_data="user_agreement")
    builder.adjust(1)
    return builder.as_markup()


def get_tariff_menu():
    """Меню выбора тарифа"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 1 день - 9₽", callback_data="tariff_1")
    builder.button(text="📅 30 дней - 149₽", callback_data="tariff_30")
    builder.button(text="📅 90 дней - 399₽", callback_data="tariff_90")
    builder.button(text="📅 180 дней - 599₽", callback_data="tariff_180")
    builder.button(text="📅 360 дней - 999₽", callback_data="tariff_360")
    builder.button(text="◀️ Назад", callback_data="back_to_profile")
    builder.adjust(1)
    return builder.as_markup()


def get_device_count_menu(tariff_days: int, base_price: float, device_price: float, current_devices: int = 1):
    """Меню выбора количества устройств"""
    builder = InlineKeyboardBuilder()
    
    for devices in [1, 2, 3, 4, 5, 6]:
        total_price = base_price + (devices - 1) * device_price
        status = "✅" if devices == current_devices else "📌"
        builder.button(
            text=f"{status} {devices} устройств - {total_price:.0f}₽",
            callback_data=f"devices_{tariff_days}_{devices}"
        )
    
    builder.button(text="◀️ Назад", callback_data="back_to_tariffs")
    builder.adjust(1)
    return builder.as_markup()


def get_payment_method_menu(amount: float):
    """Меню выбора способа оплаты"""
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Рубли (RUB)", callback_data=f"pay_rub_{amount}")
    builder.button(text="💰 USDT (криптовалюта)", callback_data=f"pay_usdt_{amount}")
    builder.button(text="⭐ Telegram Stars", callback_data=f"pay_stars_{amount}")
    builder.button(text="◀️ Назад", callback_data="back_to_tariffs")
    builder.adjust(1)
    return builder.as_markup()


def get_back_button(callback: str = "back_to_main", text: str = "◀️ Назад"):
    """Кнопка назад"""
    builder = InlineKeyboardBuilder()
    builder.button(text=text, callback_data=callback)
    return builder.as_markup()


def get_confirm_payment_button(payment_id: int):
    """Кнопка подтверждения оплаты (для админов)"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить оплату", callback_data=f"confirm_payment_{payment_id}")
    builder.button(text="❌ Отклонить", callback_data=f"reject_payment_{payment_id}")
    builder.adjust(1)
    return builder.as_markup()