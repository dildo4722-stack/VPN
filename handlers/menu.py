from aiogram import Router
from aiogram.types import CallbackQuery
from keyboards.inline_keyboards import get_main_menu, get_profile_menu
from database.db_manager import get_user

router = Router()


@router.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.edit_text(
        "Добро пожаловать в главное меню!",
        reply_markup=get_main_menu()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "profile")
async def go_to_profile(callback: CallbackQuery):
    from handlers.profile import show_profile
    await show_profile(callback)