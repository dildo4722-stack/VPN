from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from database.db_manager import get_user, create_user, get_active_subscription
from keyboards.inline_keyboards import get_device_menu, get_profile_menu
from utils.text_formatter import format_welcome_message, format_profile_message
from services.referral_service import get_user_by_code

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    args = message.text.split()
    referrer_id = None
    
    if len(args) > 1:
        ref_param = args[1]
        if ref_param.startswith("ref_"):
            code = ref_param[4:]  
            referrer = await get_user_by_code(code)
            if referrer:
                referrer_id = referrer.telegram_id
    
    user = await get_user(message.from_user.id)
    
    if not user:
        user = await create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            referrer_id=referrer_id
        )
        
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
        
        welcome_text = format_welcome_message()
        await message.answer(
            welcome_text,
            reply_markup=get_device_menu(),
            parse_mode="HTML"
        )
    else:
        subscription = await get_active_subscription(user.id)
        profile_text = format_profile_message(user, subscription)
        await message.answer(
            profile_text,
            reply_markup=get_profile_menu(),
            parse_mode="HTML"
        )