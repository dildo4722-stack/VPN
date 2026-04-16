from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from database.db_manager import get_user, create_user, get_active_subscription
from keyboards.inline_keyboards import get_device_menu, get_profile_menu
from keyboards.terms_keyboard import get_terms_keyboard
from utils.text_formatter import format_welcome_message, format_profile_message
from services.referral_service import get_user_by_code
from aiogram.types import Message, CallbackQuery

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    args = message.text.split()
    referrer_id = None
    
    # Проверяем реферальный параметр
    if len(args) > 1:
        ref_param = args[1]
        if ref_param.startswith("ref_"):
            code = ref_param[4:]
            referrer = await get_user_by_code(code)
            if referrer:
                referrer_id = referrer.telegram_id
    
    user = await get_user(message.from_user.id)
    
    if not user:
        # Создание нового пользователя
        user = await create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            referrer_id=referrer_id
        )
        
        # Уведомляем реферера
        if referrer_id:
            try:
                await message.bot.send_message(
                    chat_id=referrer_id,
                    text=f"🎉 <b>Новый реферал!</b>\n\n"
                         f"👤 <b>Пользователь:</b> {message.from_user.first_name or message.from_user.username}\n"
                         f"🆔 <b>ID:</b> <code>{message.from_user.id}</code>\n\n"
                         f"💰 Вы получите 50% от его пополнений!",
                    parse_mode="HTML"
                )
            except:
                pass
        
        # Показываем соглашение
        await show_terms(message)
        
    else:
        # Существующий пользователь
        if not user.agreed_to_terms:
            await show_terms(message)
        else:
            subscription = await get_active_subscription(user.id)
            profile_text = format_profile_message(user, subscription)
            await message.answer(
                profile_text,
                reply_markup=get_profile_menu(),
                parse_mode="HTML"
            )


async def show_terms(message: Message):
    """Показать соглашение"""
    text = (
        "📜 <b>Пользовательское соглашение</b>\n\n"
        "Для использования бота необходимо ознакомиться и принять условия:\n\n"
        "• <b>Пользовательское соглашение</b> — правила использования сервиса\n"
        "• <b>Политика конфиденциальности</b> — как мы обрабатываем данные\n\n"
        "Пожалуйста, прочитайте документы перед принятием."
    )
    
    await message.answer(text, reply_markup=get_terms_keyboard(), parse_mode="HTML")


@router.callback_query(lambda c: c.data == "accept_terms")
async def accept_terms(callback: CallbackQuery):
    """Пользователь принял условия"""
    from database.db_manager import async_session_maker
    from sqlalchemy import update
    from database.models import User
    
    async with async_session_maker() as session:
        await session.execute(
            update(User)
            .where(User.telegram_id == callback.from_user.id)
            .values(agreed_to_terms=True)
        )
        await session.commit()
    
    welcome_text = format_welcome_message()
    
    await callback.message.edit_text(
        welcome_text,
        reply_markup=get_device_menu(),
        parse_mode="HTML"
    )
    await callback.answer("✅ Спасибо! Теперь вы можете пользоваться ботом.")


@router.callback_query(lambda c: c.data == "decline_terms")
async def decline_terms(callback: CallbackQuery):
    """Пользователь не принял условия"""
    await callback.message.edit_text(
        "❌ <b>Вы не приняли условия пользовательского соглашения.</b>\n\n"
        "К сожалению, без этого вы не можете пользоваться ботом.\n\n"
        "Если передумаете, просто отправьте /start снова.",
        parse_mode="HTML"
    )
    await callback.answer()