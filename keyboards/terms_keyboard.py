from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_terms_keyboard():
    """Клавиатура для принятия соглашения"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Пользовательское соглашение", url="https://telegra.ph/Polzovatelskoe-soglashenie-04-01-19")],
        [InlineKeyboardButton(text="🔒 Политика конфиденциальности", url="https://telegra.ph/Politika-konfidencialnosti-04-01-26")],
        [InlineKeyboardButton(text="✅ Принимаю условия", callback_data="accept_terms")],
        [InlineKeyboardButton(text="❌ Не принимаю", callback_data="decline_terms")]
    ])