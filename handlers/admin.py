from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
from config import ADMIN_IDS
from database.db_manager import async_session_maker, get_user, update_user_balance_rub, update_user_balance_stars, update_user_balance_usdt
from database.models import User, Subscription, Payment, Coupon
from sqlalchemy import select, update, func
import asyncio
from aiogram.filters import StateFilter

router = Router()


class CreateCouponStates(StatesGroup):
    waiting_for_type = State()  
    waiting_for_discount_value = State()  
    waiting_for_discount_tariff = State()  
    waiting_for_discount_devices = State()  
    waiting_for_money_amount = State()  
    waiting_for_uses = State()  


class EditTariffStates(StatesGroup):
    waiting_for_tariff_days = State()  # выбор тарифа
    waiting_for_devices = State()  # ввод устройств и цен


class AddBalanceStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_currency = State()
    waiting_for_amount = State()


class RassStates(StatesGroup):
    waiting_for_message = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ==================== АДМИН-ПАНЕЛЬ ====================

@router.message(Command("admin"))
async def admin_panel(message: Message):
    """Админ-панель"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Заявки на вывод", callback_data="admin_withdrawals")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="💱 Курс USD", callback_data="admin_currency")],
        [InlineKeyboardButton(text="🎫 Создать купон", callback_data="admin_create_coupon")],
        [InlineKeyboardButton(text="➕ Пополнить баланс", callback_data="admin_add_balance")],
        [InlineKeyboardButton(text="💸 Управление тарифами", callback_data="admin_edit_tariffs")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_rass")],
        [InlineKeyboardButton(text="📋 Список купонов", callback_data="admin_list_coupons")]
    ])
    
    await message.answer("👑 <b>Админ-панель</b>\n\nВыберите действие:", reply_markup=keyboard, parse_mode="HTML")


# ==================== КУПОНЫ ====================

@router.callback_query(lambda c: c.data == "admin_create_coupon")
async def admin_create_coupon(callback: CallbackQuery, state: FSMContext):
    """Создание купона - выбор типа"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏷️ Скидка на тариф", callback_data="coupon_type_discount")],
        [InlineKeyboardButton(text="💰 Денежный бонус", callback_data="coupon_type_money")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
    ])
    
    await callback.message.edit_text(
        "🎫 <b>Создание купона</b>\n\n"
        "Выберите тип купона:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "coupon_type_discount")
async def coupon_type_discount(callback: CallbackQuery, state: FSMContext):
    """Создание купона на скидку"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await state.update_data(coupon_type="discount")
    await state.set_state(CreateCouponStates.waiting_for_discount_value)
    
    await callback.message.edit_text(
        "🎫 <b>Создание купона на скидку</b>\n\n"
        "Введите процент скидки (например: 50):\n\n"
        "Чтобы отменить: /cancel",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(CreateCouponStates.waiting_for_discount_value)
async def set_discount_value(message: Message, state: FSMContext):
    """Установка процента скидки"""
    try:
        percent = int(message.text)
        if percent < 1 or percent > 100:
            await message.answer("❌ Процент скидки должен быть от 1 до 100")
            return
        
        await state.update_data(discount_percent=percent)
        await state.set_state(CreateCouponStates.waiting_for_discount_tariff)
        
        # Показываем выбор тарифа
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 1 день", callback_data="discount_tariff_1")],
            [InlineKeyboardButton(text="📅 30 дней", callback_data="discount_tariff_30")],
            [InlineKeyboardButton(text="📅 90 дней", callback_data="discount_tariff_90")],
            [InlineKeyboardButton(text="📅 180 дней", callback_data="discount_tariff_180")],
            [InlineKeyboardButton(text="📅 360 дней", callback_data="discount_tariff_360")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_create_coupon")]
        ])
        
        await message.answer(
            f"✅ Скидка {percent}%\n\n"
            f"Выберите тариф, на который действует скидка:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except ValueError:
        await message.answer("❌ Введите число")


@router.callback_query(lambda c: c.data.startswith("discount_tariff_"))
async def set_discount_tariff(callback: CallbackQuery, state: FSMContext):
    """Выбор тарифа для скидки"""
    tariff_days = int(callback.data.split("_")[2])
    await state.update_data(discount_tariff=tariff_days)
    await state.set_state(CreateCouponStates.waiting_for_discount_devices)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 устройство", callback_data="discount_devices_1")],
        [InlineKeyboardButton(text="2 устройства", callback_data="discount_devices_2")],
        [InlineKeyboardButton(text="3 устройства", callback_data="discount_devices_3")],
        [InlineKeyboardButton(text="4 устройства", callback_data="discount_devices_4")],
        [InlineKeyboardButton(text="5 устройств", callback_data="discount_devices_5")],
        [InlineKeyboardButton(text="6 устройств", callback_data="discount_devices_6")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_create_coupon")]
    ])
    
    await callback.message.edit_text(
        f"✅ Тариф: {tariff_days} дней\n\n"
        f"Выберите количество устройств:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("discount_devices_"))
async def set_discount_devices(callback: CallbackQuery, state: FSMContext):
    """Выбор количества устройств и создание купона"""
    devices = int(callback.data.split("_")[2])
    
    data = await state.get_data()
    percent = data.get("discount_percent")
    tariff_days = data.get("discount_tariff")
    
    await state.set_state(CreateCouponStates.waiting_for_uses)
    
    await callback.message.edit_text(
        f"✅ Скидка: {percent}%\n"
        f"✅ Тариф: {tariff_days} дней\n"
        f"✅ Устройств: {devices}\n\n"
        f"Введите количество использований купона (например: 100):\n\n"
        f"Чтобы отменить: /cancel",
        parse_mode="HTML"
    )
    await state.update_data(discount_devices=devices)
    await callback.answer()


@router.callback_query(lambda c: c.data == "coupon_type_money")
async def coupon_type_money(callback: CallbackQuery, state: FSMContext):
    """Создание денежного купона"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await state.update_data(coupon_type="money")
    await state.set_state(CreateCouponStates.waiting_for_money_amount)
    
    await callback.message.edit_text(
        "🎫 <b>Создание денежного купона</b>\n\n"
        "Введите сумму начисления в рублях (например: 500):\n\n"
        "Чтобы отменить: /cancel",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(CreateCouponStates.waiting_for_money_amount)
async def set_money_amount(message: Message, state: FSMContext):
    """Установка суммы денежного купона"""
    try:
        amount = float(message.text)
        if amount < 1:
            await message.answer("❌ Сумма должна быть больше 0")
            return
        
        await state.update_data(money_amount=amount)
        await state.set_state(CreateCouponStates.waiting_for_uses)
        
        await message.answer(
            f"✅ Сумма: {amount} ₽\n\n"
            f"Введите количество использований купона (например: 100):\n\n"
            f"Чтобы отменить: /cancel",
            parse_mode="HTML"
        )
        
    except ValueError:
        await message.answer("❌ Введите число")


@router.message(CreateCouponStates.waiting_for_uses)
async def set_coupon_uses(message: Message, state: FSMContext):
    """Установка количества использований и сохранение купона"""
    try:
        uses = int(message.text)
        if uses < 1:
            await message.answer("❌ Количество использований должно быть больше 0")
            return
        
        data = await state.get_data()
        coupon_type = data.get("coupon_type")
        
        import random
        import string
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        
        async with async_session_maker() as session:
            from database.models import Coupon
            
            if coupon_type == "discount":
                coupon = Coupon(
                    code=code,
                    type="discount",
                    discount_percent=data.get("discount_percent"),
                    tariff_days=data.get("discount_tariff"),
                    devices=data.get("discount_devices"),
                    max_uses=uses,
                    used_count=0,
                    is_active=True
                )
            else:
                coupon = Coupon(
                    code=code,
                    type="money",
                    amount=data.get("money_amount"),
                    max_uses=uses,
                    used_count=0,
                    is_active=True
                )
            
            session.add(coupon)
            await session.commit()
        
        await message.answer(
            f"✅ <b>Купон создан!</b>\n\n"
            f"📌 <b>Код:</b> <code>{code}</code>\n"
            f"📊 <b>Тип:</b> {'Скидка' if coupon_type == 'discount' else 'Денежный'}\n"
            f"🔢 <b>Использований:</b> {uses}\n\n"
            f"Сохраните этот код!",
            parse_mode="HTML"
        )
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите число")


# ==================== ПОПОЛНЕНИЕ БАЛАНСА АДМИНОМ ====================

@router.callback_query(lambda c: c.data == "admin_add_balance")
async def admin_add_balance(callback: CallbackQuery, state: FSMContext):
    """Пополнение баланса пользователя админом"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await state.set_state(AddBalanceStates.waiting_for_user_id)
    
    await callback.message.edit_text(
        "➕ <b>Пополнение баланса</b>\n\n"
        "Введите Telegram ID пользователя:\n\n"
        "Чтобы отменить: /cancel",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AddBalanceStates.waiting_for_user_id)
async def add_balance_get_user(message: Message, state: FSMContext):
    """Получение ID пользователя"""
    try:
        user_id = int(message.text.strip())
        user = await get_user(user_id)
        
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        
        await state.update_data(target_id=user_id, target_user=user)
        await state.set_state(AddBalanceStates.waiting_for_currency)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 RUB", callback_data="add_currency_rub")],
            [InlineKeyboardButton(text="⭐ Stars", callback_data="add_currency_stars")],
            [InlineKeyboardButton(text="💎 USDT", callback_data="add_currency_usdt")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
        ])
        
        await message.answer(
            f"👤 Пользователь: {user.first_name or user.username}\n"
            f"🆔 ID: {user.telegram_id}\n\n"
            f"Выберите валюту:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except ValueError:
        await message.answer("❌ Введите корректный ID")


@router.callback_query(lambda c: c.data.startswith("add_currency_"))
async def add_balance_currency(callback: CallbackQuery, state: FSMContext):
    """Выбор валюты для пополнения"""
    currency = callback.data.split("_")[2]
    await state.update_data(currency=currency)
    await state.set_state(AddBalanceStates.waiting_for_amount)
    
    await callback.message.edit_text(
        f"💳 <b>Пополнение в {currency.upper()}</b>\n\n"
        f"Введите сумму:\n\n"
        f"Чтобы отменить: /cancel",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AddBalanceStates.waiting_for_amount)
async def add_balance_amount(message: Message, state: FSMContext):
    """Пополнение баланса"""
    try:
        amount = float(message.text)
        data = await state.get_data()
        target_id = data.get("target_id")
        currency = data.get("currency")
        
        user = await get_user(target_id)
        
        if currency == "rub":
            await update_user_balance_rub(user.id, amount)
            await message.answer(f"✅ Пользователю {target_id} начислено {amount} RUB")
        elif currency == "stars":
            await update_user_balance_stars(user.id, int(amount))
            await message.answer(f"✅ Пользователю {target_id} начислено {int(amount)} Stars")
        elif currency == "usdt":
            await update_user_balance_usdt(user.id, amount)
            await message.answer(f"✅ Пользователю {target_id} начислено {amount} USDT")
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите число")


# ==================== РАССЫЛКА ====================

@router.callback_query(lambda c: c.data == "admin_rass")
async def admin_rass(callback: CallbackQuery, state: FSMContext):
    """Запуск рассылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await state.set_state(RassStates.waiting_for_message)
    
    await callback.message.edit_text(
        "📢 <b>Рассылка</b>\n\n"
        "Отправьте сообщение для рассылки (текст или фото/видео с подписью):\n\n"
        "Чтобы отменить: /cancel",
        parse_mode="HTML"
    )
    await callback.answer()
@router.callback_query(lambda c: c.data == "admin_list_coupons")
async def admin_list_coupons(callback: CallbackQuery):
    """Список всех купонов с подробной информацией"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    async with async_session_maker() as session:
        from database.models import Coupon
        from sqlalchemy import select, func
        
        result = await session.execute(
            select(Coupon).order_by(Coupon.created_at.desc())
        )
        coupons = result.scalars().all()
        
        total_coupons = len(coupons)
        active_coupons = len([c for c in coupons if c.is_active and c.used_count < c.max_uses])
        total_uses = sum(c.used_count for c in coupons)
        total_money_given = sum(c.amount for c in coupons if c.type == "money" and c.used_count > 0)
    
    if not coupons:
        text = (
            "📋 <b>СПИСОК КУПОНОВ</b>\n\n"
            "<blockquote>❌ Купонов пока нет</blockquote>\n\n"
            "💡 Нажмите «Создать новый», чтобы добавить купон."
        )
    else:
        text = (
            "📋 <b>СПИСОК КУПОНОВ</b>\n\n"
            f"<blockquote>📊 <b>Статистика:</b>\n"
            f"├ Всего купонов: {total_coupons}\n"
            f"├ Активных: {active_coupons}\n"
            f"├ Использований: {total_uses}\n"
            f"└ Выдано бонусов: {total_money_given:.0f} ₽</blockquote>\n\n"
        )
        
        for i, c in enumerate(coupons, 1):

            if not c.is_active:
                status = "⚫ НЕАКТИВЕН"
                status_emoji = "❌"
            elif c.used_count >= c.max_uses:
                status = "🔴 ИСТЕК (лимит)"
                status_emoji = "⚠️"
            else:
                status = "🟢 АКТИВЕН"
                status_emoji = "✅"
            
            use_percent = (c.used_count / c.max_uses * 100) if c.max_uses > 0 else 0
            
            if c.type == "money":
                type_icon = "💰"
                type_name = "ДЕНЕЖНЫЙ"
                reward = f"+{c.amount:.0f} ₽ на баланс"
            else:
                type_icon = "🏷️"
                type_name = "СКИДОЧНЫЙ"
                reward = f"Скидка {c.discount_percent}%\n       └ на {c.tariff_days} дней, {c.devices} устройств"
            
            bar_length = 20
            filled = int(bar_length * c.used_count / c.max_uses) if c.max_uses > 0 else 0
            bar = "█" * filled + "░" * (bar_length - filled)
            
            text += (
                f"<blockquote>"
                f"┌ <b>[{i}] {type_icon} {type_name} КУПОН</b> {status_emoji}\n"
                f"├ 🎫 <b>Код:</b> <code>{c.code}</code>\n"
                f"├ 📦 <b>Награда:</b> {reward}\n"
                f"├ 📊 <b>Использований:</b> {c.used_count} / {c.max_uses}\n"
                f"├ 📈 <b>Прогресс:</b> [{bar}] {use_percent:.0f}%\n"
                f"├ ✅ <b>Осталось:</b> {c.max_uses - c.used_count}\n"
                f"├ 📅 <b>Создан:</b> {c.created_at.strftime('%d.%m.%Y в %H:%M')}\n"
                f"├ 🔘 <b>Статус:</b> {status}\n"
            )
            

            if c.type == "discount":
                example_price = 500  
                saved = int(example_price * c.discount_percent / 100)
                text += f"└ 💡 <b>Пример экономии:</b> {saved}₽ при покупке\n"
            else:
                text += f"└ 💡 <b>Пример:</b> активация даст +{c.amount:.0f}₽\n"
            
            text += f"</blockquote>\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎫 Создать новый купон", callback_data="admin_create_coupon")],
        [InlineKeyboardButton(text="🗑️ Удалить все неактивные", callback_data="admin_delete_inactive_coupons")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_delete_inactive_coupons")
async def admin_delete_inactive_coupons(callback: CallbackQuery):
    """Удаление всех неактивных купонов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    async with async_session_maker() as session:
        from database.models import Coupon
        from sqlalchemy import delete
        
        result = await session.execute(
            delete(Coupon).where(
                (Coupon.is_active == False) | (Coupon.used_count >= Coupon.max_uses)
            )
        )
        await session.commit()
        deleted_count = result.rowcount
    
    await callback.answer(f"✅ Удалено {deleted_count} неактивных купонов", show_alert=True)
    await admin_list_coupons(callback)

@router.message(RassStates.waiting_for_message)
async def send_rass(message: Message, state: FSMContext):
    """Отправка рассылки"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    async with async_session_maker() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
    
    success = 0
    fail = 0
    
    status_msg = await message.answer("⏳ Начинаю рассылку...")
    
    for user in users:
        try:
            if message.photo:
                await message.bot.send_photo(
                    chat_id=user.telegram_id,
                    photo=message.photo[-1].file_id,
                    caption=message.caption or ""
                )
            elif message.video:
                await message.bot.send_video(
                    chat_id=user.telegram_id,
                    video=message.video.file_id,
                    caption=message.caption or ""
                )
            else:
                await message.bot.send_message(
                    chat_id=user.telegram_id,
                    text=message.text
                )
            success += 1
        except:
            fail += 1
        
        await asyncio.sleep(0.05)
    
    await status_msg.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📤 Отправлено: {success}\n"
        f"❌ Не отправлено: {fail}",
        parse_mode="HTML"
    )
    
    await state.clear()

# ==================== КУРС USD ====================

@router.callback_query(lambda c: c.data == "admin_currency")
async def admin_currency(callback: CallbackQuery):
    """Изменение курса USD"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    from database.db_manager import get_usd_rate
    current_rate = await get_usd_rate()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Увеличить на 1", callback_data="usd_up_1")],
        [InlineKeyboardButton(text="📉 Уменьшить на 1", callback_data="usd_down_1")],
        [InlineKeyboardButton(text="📈 Увеличить на 5", callback_data="usd_up_5")],
        [InlineKeyboardButton(text="📉 Уменьшить на 5", callback_data="usd_down_5")],
        [InlineKeyboardButton(text="✏️ Установить вручную", callback_data="usd_set")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
    ])
    
    await callback.message.edit_text(
        f"💱 <b>Курс USD к RUB</b>\n\n"
        f"Текущий курс: <b>1$ = {current_rate:.2f}₽</b>\n\n"
        f"Выберите действие:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("usd_up_"))
async def usd_up(callback: CallbackQuery):
    """Увеличение курса"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    value = int(callback.data.split("_")[2])
    
    from database.db_manager import get_usd_rate, update_usd_rate
    import importlib
    import database.db_manager
    
    importlib.reload(database.db_manager)
    
    current_rate = await get_usd_rate()
    new_rate = current_rate + value
    
    await update_usd_rate(new_rate)
    
    try:
        from config import USD_TO_RUB
        pass
    except:
        pass
    
    await callback.answer(f"✅ Курс увеличен на {value}. Теперь: 1$ = {new_rate:.2f}₽", show_alert=True)
    await admin_currency(callback)


@router.callback_query(lambda c: c.data.startswith("usd_down_"))
async def usd_down(callback: CallbackQuery):
    """Уменьшение курса"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    value = int(callback.data.split("_")[2])
    
    from database.db_manager import get_usd_rate, update_usd_rate
    current_rate = await get_usd_rate()
    new_rate = max(1, current_rate - value)
    
    await update_usd_rate(new_rate)
    
    await callback.answer(f"✅ Курс уменьшен на {value}. Теперь: 1$ = {new_rate:.2f}₽", show_alert=True)
    await admin_currency(callback)


@router.callback_query(lambda c: c.data == "usd_set")
async def usd_set(callback: CallbackQuery, state: FSMContext):
    """Установка курса вручную"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    from database.db_manager import get_usd_rate
    current_rate = await get_usd_rate()
    
    # Создаём временное состояние
    class CurrencyState(StatesGroup):
        waiting_for_rate = State()
    
    await state.set_state(CurrencyState.waiting_for_rate)
    
    await callback.message.edit_text(
        f"💱 <b>Установка курса USD</b>\n\n"
        f"Текущий курс: 1$ = {current_rate:.2f}₽\n\n"
        f"Отправьте новое значение курса (например: 85.5)\n\n"
        f"Чтобы отменить: /cancel",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(StateFilter("CurrencyState.waiting_for_rate"))
async def set_currency_rate(message: Message, state: FSMContext):
    """Установка нового курса из сообщения"""
    try:
        new_rate = float(message.text)
        
        if new_rate < 1:
            await message.answer("❌ Курс не может быть меньше 1")
            return
        
        from database.db_manager import update_usd_rate
        await update_usd_rate(new_rate)
        
        await message.answer(f"✅ Курс установлен: 1$ = {new_rate:.2f}₽")
        
        from handlers.admin import admin_panel
        await admin_panel(message)
        
    except ValueError:
        await message.answer("❌ Неверный формат. Отправьте число (например: 85.5)")
    
    await state.clear()


# ==================== ЗАЯВКИ НА ВЫВОД ====================

@router.callback_query(lambda c: c.data == "admin_withdrawals")
async def admin_withdrawals(callback: CallbackQuery):
    """Список заявок на вывод"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    from database.models import WithdrawalRequest
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(WithdrawalRequest, User)
            .join(User)
            .where(WithdrawalRequest.status == "pending")
            .order_by(WithdrawalRequest.created_at.desc())
        )
        requests = result.all()
    
    if not requests:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
        ])
        await callback.message.edit_text("📭 Нет активных заявок на вывод", reply_markup=keyboard)
        await callback.answer()
        return
    
    text = "💰 <b>ЗАЯВКИ НА ВЫВОД</b>\n\n"
    for req, user in requests:
        text += (
            f"┌ <b>Заявка #{req.id}</b>\n"
            f"├ 👤 ID: <code>{user.telegram_id}</code>\n"
            f"├ 👤 Имя: {user.first_name or 'Не указано'}\n"
            f"├ 💸 Сумма: {req.amount:.2f}₽\n"
            f"├ 🏦 Способ: {req.method}\n"
            f"├ 🧾 Реквизиты: {req.details}\n"
            f"├ 📅 Создана: {req.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"└ 🔘 /approve_{req.id} - одобрить | /reject_{req.id} - отклонить\n\n"
        )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_withdrawals")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


# ==================== СТАТИСТИКА ====================

@router.callback_query(lambda c: c.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    """Статистика бота"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    async with async_session_maker() as session:
        from database.models import WithdrawalRequest
        
        total_users = await session.execute(select(func.count()).select_from(User))
        total_users = total_users.scalar() or 0
        
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_users = await session.execute(
            select(func.count()).select_from(User).where(User.created_at >= today)
        )
        today_users = today_users.scalar() or 0
        
        active_subs = await session.execute(
            select(func.count()).select_from(Subscription).where(Subscription.is_active == True)
        )
        active_subs = active_subs.scalar() or 0
        
        total_withdrawn = await session.execute(
            select(func.sum(WithdrawalRequest.amount)).where(WithdrawalRequest.status == "approved")
        )
        total_withdrawn = total_withdrawn.scalar() or 0.0
        
        pending_withdrawals = await session.execute(
            select(func.sum(WithdrawalRequest.amount)).where(WithdrawalRequest.status == "pending")
        )
        pending_withdrawals = pending_withdrawals.scalar() or 0.0
        
        total_referrals = await session.execute(
            select(func.count()).select_from(User).where(User.referrer_id != None)
        )
        total_referrals = total_referrals.scalar() or 0
        
        total_payments = await session.execute(
            select(func.sum(Payment.amount)).where(Payment.status == "success")
        )
        total_payments = total_payments.scalar() or 0.0
        
        withdrawal_requests_count = await session.execute(
            select(func.count()).select_from(WithdrawalRequest)
        )
        withdrawal_requests_count = withdrawal_requests_count.scalar() or 0
        
        pending_count = await session.execute(
            select(func.count()).select_from(WithdrawalRequest).where(WithdrawalRequest.status == "pending")
        )
        pending_count = pending_count.scalar() or 0
    
    text = (
        "📊 <b>СТАТИСТИКА БОТА</b>\n\n"
        "👥 <b>Пользователи:</b>\n"
        f"├ Всего: {total_users}\n"
        f"├ За сегодня: {today_users}\n"
        f"└ Рефералов: {total_referrals}\n\n"
        "💎 <b>Подписки:</b>\n"
        f"└ Активных: {active_subs}\n\n"
        "💰 <b>Финансы:</b>\n"
        f"├ Всего пополнений: {total_payments:.2f}₽\n"
        f"├ Выплачено: {total_withdrawn:.2f}₽\n"
        f"└ Ожидает выплаты: {pending_withdrawals:.2f}₽\n\n"
        "📋 <b>Заявки на вывод:</b>\n"
        f"├ Всего: {withdrawal_requests_count}\n"
        f"└ В обработке: {pending_count}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


# ==================== ПОЛЬЗОВАТЕЛИ ====================

@router.callback_query(lambda c: c.data == "admin_users")
async def admin_users(callback: CallbackQuery):
    """Список пользователей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).order_by(User.created_at.desc()).limit(50)
        )
        users = result.scalars().all()
    
    text = "👥 <b>ПОСЛЕДНИЕ 50 ПОЛЬЗОВАТЕЛЕЙ</b>\n\n"
    for user in users:
        text += (
            f"┌ <b>ID:</b> <code>{user.telegram_id}</code>\n"
            f"├ <b>Имя:</b> {user.first_name or 'Не указано'}\n"
            f"├ <b>Баланс:</b> {user.balance_rub:.2f}₽ | {user.balance_stars}⭐ | {user.balance_usdt:.2f}💎\n"
            f"├ <b>Рефералов:</b> {user.referrer_id and 'Приглашен' or 'Нет'}\n"
            f"├ <b>Дата:</b> {user.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"└ {'✅ Принял соглашение' if user.agreed_to_terms else '❌ Не принял'}\n\n"
        )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.message(lambda msg: msg.text and msg.text.startswith("/approve_"))
async def approve_withdrawal(message: Message):
    """Подтверждение заявки на вывод"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    try:
        request_id = int(message.text.split("_")[1])
    except:
        await message.answer("❌ Неверный формат. Используйте: /approve_123")
        return
    
    from database.models import WithdrawalRequest
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(WithdrawalRequest, User)
            .join(User)
            .where(WithdrawalRequest.id == request_id)
        )
        req_user = result.first()
        
        if not req_user:
            await message.answer(f"❌ Заявка #{request_id} не найдена")
            return
        
        req, user = req_user
        
        if req.status != "pending":
            await message.answer(f"❌ Заявка #{request_id} уже обработана")
            return
        
        # Обновляем статус
        await session.execute(
            update(WithdrawalRequest)
            .where(WithdrawalRequest.id == request_id)
            .values(status="approved", processed_at=datetime.utcnow())
        )
        
        # Списываем баланс
        await session.execute(
            update(User)
            .where(User.id == user.id)
            .values(balance_rub=User.balance_rub - req.amount)
        )
        
        await session.commit()
    
    # Уведомляем пользователя
    try:
        await message.bot.send_message(
            chat_id=user.telegram_id,
            text=f"✅ <b>Заявка на вывод одобрена!</b>\n\n"
                 f"💰 Сумма: {req.amount:.2f}₽\n"
                 f"🏦 Способ: {req.method}",
            parse_mode="HTML"
        )
    except:
        pass
    
    await message.answer(f"✅ Заявка #{request_id} одобрена")


@router.message(lambda msg: msg.text and msg.text.startswith("/reject_"))
async def reject_withdrawal(message: Message):
    """Отклонение заявки на вывод"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    try:
        request_id = int(message.text.split("_")[1])
    except:
        await message.answer("❌ Неверный формат. Используйте: /reject_123")
        return
    
    from database.models import WithdrawalRequest
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(WithdrawalRequest, User)
            .join(User)
            .where(WithdrawalRequest.id == request_id)
        )
        req_user = result.first()
        
        if not req_user:
            await message.answer(f"❌ Заявка #{request_id} не найдена")
            return
        
        req, user = req_user
        
        if req.status != "pending":
            await message.answer(f"❌ Заявка #{request_id} уже обработана")
            return
        
        await session.execute(
            update(WithdrawalRequest)
            .where(WithdrawalRequest.id == request_id)
            .values(status="rejected", processed_at=datetime.utcnow())
        )
        await session.commit()
    
    # Уведомляем пользователя
    try:
        await message.bot.send_message(
            chat_id=user.telegram_id,
            text=f"❌ <b>Заявка на вывод отклонена!</b>\n\n"
                 f"💰 Сумма: {req.amount:.2f}₽\n\n"
                 f"Причина: обратитесь в поддержку",
            parse_mode="HTML"
        )
    except:
        pass
    
    await message.answer(f"❌ Заявка #{request_id} отклонена")

# ==================== УПРАВЛЕНИЕ ТАРИФАМИ ====================

@router.callback_query(lambda c: c.data == "admin_edit_tariffs")
async def admin_edit_tariffs(callback: CallbackQuery, state: FSMContext):
    """Управление тарифами - выбор тарифа для редактирования"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    from config import TARIFFS
    
    text = "💸 <b>Управление тарифами</b>\n\n"
    text += "Текущие тарифы:\n\n"
    
    for days, info in TARIFFS.items():
        text += f"📅 {days} дней: {info['price']}₽ (база), +{info['device_price']}₽ за устройство\n"
    
    text += "\nВыберите тариф для редактирования:"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 1 день", callback_data="edit_tariff_1")],
        [InlineKeyboardButton(text="📅 30 дней", callback_data="edit_tariff_30")],
        [InlineKeyboardButton(text="📅 90 дней", callback_data="edit_tariff_90")],
        [InlineKeyboardButton(text="📅 180 дней", callback_data="edit_tariff_180")],
        [InlineKeyboardButton(text="📅 360 дней", callback_data="edit_tariff_360")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edit_tariff_"))
async def edit_tariff_select(callback: CallbackQuery, state: FSMContext):
    """Выбор тарифа для редактирования"""
    tariff_days = int(callback.data.split("_")[2])
    
    await state.update_data(tariff_days=tariff_days)
    await state.set_state(EditTariffStates.waiting_for_devices)
    
    await callback.message.edit_text(
        f"📅 <b>Редактирование тарифа: {tariff_days} дней</b>\n\n"
        f"Введите данные в формате:\n"
        f"<code>цена_за_1_устройство,цена_за_2_устройства,цена_за_3_устройства,...</code>\n\n"
        f"Пример для 1-6 устройств:\n"
        f"<code>10,20,30,40,50,60</code>\n\n"
        f"Или введите: <code>базовая_цена,цена_за_дополнительное</code>\n"
        f"Пример: <code>10,10</code> (база 10₽, +10₽ за каждое доп. устройство)\n\n"
        f"Чтобы отменить: /cancel",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(EditTariffStates.waiting_for_devices)
async def save_tariff_devices(message: Message, state: FSMContext):
    """Сохранение новых цен для тарифа"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    data = await state.get_data()
    tariff_days = data.get("tariff_days")
    
    try:
        parts = message.text.strip().split(',')
        
        if len(parts) == 2:
            # Формат: базовая_цена,цена_за_дополнительное
            base_price = float(parts[0])
            device_price = float(parts[1])
        elif len(parts) >= 1:
            # Формат: цены для 1-6 устройств
            prices = [float(p.strip()) for p in parts]
            base_price = prices[0] if len(prices) > 0 else 10
            if len(prices) >= 2:
                device_price = prices[1] - prices[0]  # разница между 2 и 1 устройством
            else:
                device_price = base_price
        else:
            await message.answer("❌ Неверный формат. Попробуйте ещё раз.")
            return
        
        if base_price < 0 or device_price < 0:
            await message.answer("❌ Цена не может быть отрицательной")
            return
        
        # Обновляем TARIFFS в config.py
        import config
        import os
        
        config.TARIFFS[tariff_days] = {
            "price": base_price,
            "base_devices": 1,
            "device_price": device_price
        }
        
        # Сохраняем в файл .env или config.py
        with open("config.py", "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        with open("config.py", "w", encoding="utf-8") as f:
            for line in lines:
                if line.strip().startswith("TARIFFS = {"):
                    # Перезаписываем словарь TARIFFS
                    f.write("TARIFFS = {\n")
                    for days, info in config.TARIFFS.items():
                        f.write(f"    {days}: {{\"price\": {info['price']}, \"base_devices\": 1, \"device_price\": {info['device_price']}}},\n")
                    f.write("}\n")
                else:
                    f.write(line)
        
        # Обновляем также в db_manager.py для init_default_data
        from database.models import TariffConfig
        from database.db_manager import async_session_maker
        from sqlalchemy import update
        
        async with async_session_maker() as session:
            await session.execute(
                update(TariffConfig)
                .where(TariffConfig.days == tariff_days)
                .values(base_price=base_price, device_price=device_price)
            )
            await session.commit()
        
        await message.answer(
            f"✅ <b>Тариф обновлён!</b>\n\n"
            f"📅 {tariff_days} дней\n"
            f"💰 Базовая цена: {base_price} ₽\n"
            f"➕ Цена за устройство: {device_price} ₽\n\n"
            f"Изменения вступят в силу после перезапуска бота.",
            parse_mode="HTML"
        )
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Ошибка: введите числа через запятую")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@router.callback_query(lambda c: c.data == "admin_panel")
async def back_to_admin_panel(callback: CallbackQuery):
    """Назад в админ-панель"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Заявки на вывод", callback_data="admin_withdrawals")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="💱 Курс USD", callback_data="admin_currency")],
        [InlineKeyboardButton(text="🎫 Создать купон", callback_data="admin_create_coupon")],
        [InlineKeyboardButton(text="➕ Пополнить баланс", callback_data="admin_add_balance")],
        [InlineKeyboardButton(text="💸 Управление тарифами", callback_data="admin_edit_tariffs")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_rass")],
        [InlineKeyboardButton(text="📋 Список купонов", callback_data="admin_list_coupons")]
    ])
    
    await callback.message.edit_text("👑 <b>Админ-панель</b>\n\nВыберите действие:", reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()