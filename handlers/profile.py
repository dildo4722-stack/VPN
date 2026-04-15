from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message, FSInputFile, BufferedInputFile, LabeledPrice
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import qrcode
from io import BytesIO
import random
import string
import time

from database.db_manager import get_user, get_active_subscription, async_session_maker, update_user_balance
from keyboards.inline_keyboards import get_profile_menu, get_tariff_menu, get_back_button
from utils.text_formatter import format_profile_message
from services.referral_service import (
    get_referral_link, get_referral_stats, update_withdrawal_info,
    update_referral_code, get_or_create_referral_code
)

router = Router()

class GiftStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_tariff = State()

class DepositStates(StatesGroup):
    waiting_for_amount = State()

class CouponStates(StatesGroup):
    waiting_for_code = State()

class WithdrawalStates(StatesGroup):
    waiting_for_method = State()
    waiting_for_details = State()


class ChangeCodeStates(StatesGroup):
    waiting_for_confirmation = State()
    waiting_for_new_code = State()


async def show_profile(callback: CallbackQuery):
    from database.db_manager import get_usd_rate
    
    user = await get_user(callback.from_user.id)
    subscription = await get_active_subscription(user.id)
    usd_rate = await get_usd_rate()
    
    rub = user.balance
    usdt = rub / usd_rate if usd_rate > 0 else 0
    stars = int(rub)
    
    profile_text = format_profile_message(user, subscription)
    
    balance_text = f"\n\n💳 RUB: {rub:.2f} | 💎 USDT: {usdt:.2f} | ⭐ Stars: {stars}"
    
    await callback.message.edit_text(
        profile_text + balance_text,
        reply_markup=get_profile_menu(),
        parse_mode="HTML"
    )
    await callback.answer()


from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.db_manager import get_user, get_usd_rate
from datetime import datetime




@router.callback_query(lambda c: c.data == "show_balance")
async def show_balance(callback: CallbackQuery):
    """Управление балансом с отображением в 3 валютах"""
    from database.db_manager import get_user_balances
    
    balances = await get_user_balances(callback.from_user.id)
    
    text = (
        f"💰 <b>Управление вашим балансом</b>\n\n"
        f"<blockquote>"
        f"💳 RUB: <b>{balances['rub']:.2f} ₽</b>\n"
        f"⭐ Stars: <b>{balances['stars']}</b>\n"
        f"💎 USDT: <b>{balances['usdt']:.2f}</b>"
        f"</blockquote>\n\n"
        f"📌 Выберите действие:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="deposit_balance")],
        [InlineKeyboardButton(text="📜 История пополнений", callback_data="deposit_history")],
        [InlineKeyboardButton(text="🎫 Активировать купон", callback_data="activate_coupon")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_profile")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "deposit_balance")
async def deposit_balance(callback: CallbackQuery):
    """Выбор валюты пополнения"""
    text = "💳 <b>Выберите валюту пополнения:</b>\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="deposit_stars")],
        [InlineKeyboardButton(text="💰 USDT (криптовалюта)", callback_data="deposit_usdt")],
        [InlineKeyboardButton(text="💳 Рубли (RUB) 🔜", callback_data="deposit_rub_disabled")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="show_balance")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "deposit_rub")
async def deposit_rub(callback: CallbackQuery, state: FSMContext):
    """Пополнение в рублях - запрос суммы"""
    await callback.message.edit_text(
        "💳 <b>Пополнение в RUB</b>\n\n"
        "Введите сумму пополнения в рублях (от 100₽):\n\n"
        "Пример: <code>500</code>\n\n"
        "Чтобы отменить: /cancel",
        parse_mode="HTML"
    )
    
    await state.set_state(DepositStates.waiting_for_amount)
    await state.update_data(method="rub")
    await callback.answer()

@router.callback_query(lambda c: c.data == "deposit_rub_disabled")
async def deposit_rub_disabled(callback: CallbackQuery):
    """RUB временно недоступен"""
    await callback.answer("❌ Пополнение в RUB временно недоступно. Используйте Stars или USDT.", show_alert=True)


@router.callback_query(lambda c: c.data.startswith("deposit_usdt"))
async def deposit_usdt(callback: CallbackQuery, state: FSMContext):
    """Пополнение через USDT - запрос суммы"""
    await callback.message.edit_text(
        "💰 <b>Пополнение через USDT</b>\n\n"
        "Введите сумму пополнения в рублях (от 100₽):\n\n"
        "Пример: <code>500</code>\n\n"
        "Чтобы отменить: /cancel",
        parse_mode="HTML"
    )
    
    await state.set_state(DepositStates.waiting_for_amount)
    await state.update_data(method="usdt")
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("deposit_stars"))
async def deposit_stars(callback: CallbackQuery, state: FSMContext):
    """Пополнение через Stars - запрос суммы в Stars"""
    await callback.message.edit_text(
        "⭐ <b>Пополнение через Telegram Stars</b>\n\n"
        "Введите сумму пополнения в Stars (от 50 Stars):\n\n"
        "Пример: <code>100</code>\n\n"
        "Чтобы отменить: /cancel",
        parse_mode="HTML"
    )
    
    await state.set_state(DepositStates.waiting_for_amount)
    await state.update_data(method="stars")
    await callback.answer()


@router.message(DepositStates.waiting_for_amount)
async def process_deposit_amount(message: Message, state: FSMContext):
    """Обработка суммы пополнения"""
    try:
        amount = float(message.text)
        data = await state.get_data()
        method = data.get("method")
        
        if method == "rub":
            if amount < 100:
                await message.answer("❌ Минимальная сумма пополнения 100₽")
                return
            
            await message.answer(
                "❌ Пополнение в RUB временно недоступно.\nИспользуйте Stars или USDT.",
                reply_markup=get_back_button("show_balance", "◀️ Назад")
            )
        
        elif method == "usdt":
            if amount < 0.5:
                await message.answer("❌ Минимальная сумма пополнения 0,5 USDT")
                return
            
            from services.payment_service import create_crypto_payment
            result = await create_crypto_payment(
                user_id=message.from_user.id,
                amount_usdt=amount,
                tariff_days=0,
                devices_count=0
            )
            
            if result["success"]:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💎 Оплатить USDT", url=result['pay_url'])],
                    [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"check_deposit_usdt_{result['invoice_id']}_{amount}")],
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="show_balance")]
                ])
                
                await message.answer(
                    f"💎 <b>Счет на пополнение USDT</b>\n\n"
                    f"Сумма: {amount} USDT\n\n"
                    f"Оплатите счет и нажмите «Я оплатил»",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                await message.answer(f"❌ Ошибка: {result.get('error')}")
        
        elif method == "stars":
            stars_amount = int(amount)
            
            if stars_amount < 50:
                await message.answer("❌ Минимальная сумма пополнения 50 Stars")
                return
            
            prices = [LabeledPrice(label="Пополнение Stars", amount=stars_amount)]
            
            await message.answer_invoice(
                title="Пополнение баланса Stars",
                description=f"Сумма пополнения: {stars_amount} Stars",
                payload=f"deposit_stars_{message.from_user.id}_{stars_amount}_{int(time.time())}",
                provider_token="",
                currency="XTR",
                prices=prices,
                start_parameter="deposit",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⭐ Оплатить Stars", pay=True)]
                ])
            )
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите число")

@router.callback_query(lambda c: c.data.startswith("check_deposit_usdt_"))
async def check_deposit_usdt(callback: CallbackQuery):
    """Проверка оплаты USDT для пополнения"""
    parts = callback.data.split("_")
    invoice_id = int(parts[3])
    amount = float(parts[4])
    
    from services.payment_service import check_crypto_payment
    from database.db_manager import get_user, update_user_balance_usdt
    
    await callback.message.edit_text("⏳ Проверяем оплату...", reply_markup=None)
    
    result = await check_crypto_payment(invoice_id)
    
    if result["status"] == "paid":
        user = await get_user(callback.from_user.id)
        if user:
            await update_user_balance_usdt(user.id, amount)
            await callback.message.edit_text(
                f"✅ <b>Баланс пополнен!</b>\n\n"
                f"💎 Сумма: +{amount} USDT",
                reply_markup=get_back_button("show_balance", "◀️ Назад"),
                parse_mode="HTML"
            )
    elif result["status"] == "active":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Проверить еще раз", callback_data=f"check_deposit_usdt_{invoice_id}_{amount}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="show_balance")]
        ])
        await callback.message.edit_text("⏳ Платеж еще не обработан. Оплатите и проверьте еще раз.", reply_markup=keyboard)
    else:
        await callback.message.edit_text("❌ Счет не найден или истек", reply_markup=get_back_button("show_balance", "◀️ Назад"))
    
    await callback.answer()


@router.message(F.successful_payment)
async def successful_deposit(message: Message):
    """Обработка успешной оплаты Stars для пополнения"""
    payment = message.successful_payment
    payload = payment.invoice_payload
    amount = int(payment.total_amount)  
    
    from database.db_manager import get_user, update_user_balance_stars
    
    if payload.startswith("deposit_stars"):
        parts = payload.split("_")
        user_id = int(parts[2])
        stars_amount = int(parts[3]) if len(parts) > 3 else amount
        
        if user_id == message.from_user.id:
            user = await get_user(user_id)
            if user:
                await update_user_balance_stars(user.id, stars_amount)
                await message.answer(
                    f"✅ <b>Баланс пополнен!</b>\n\n"
                    f"⭐ Сумма: +{stars_amount} Stars",
                    parse_mode="HTML"
                )


@router.callback_query(lambda c: c.data == "deposit_history")
async def deposit_history(callback: CallbackQuery):
    """История пополнений"""
    from database.models import Payment
    from database.db_manager import async_session_maker
    from sqlalchemy import select
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(Payment).where(
                Payment.user_id == callback.from_user.id,
                Payment.status == "success"
            ).order_by(Payment.created_at.desc()).limit(20)
        )
        payments = result.scalars().all()
    
    if not payments:
        text = "📜 <b>История пополнений</b>\n\n<blockquote>Пополнений пока нет</blockquote>"
    else:
        text = "📜 <b>История пополнений</b>\n\n"
        for p in payments:
            text += f"<blockquote>✅ +{p.amount:.2f} ₽ | {p.payment_method}\n📅 {p.created_at.strftime('%d.%m.%Y %H:%M')}</blockquote>\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="show_balance")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "activate_coupon")
async def activate_coupon(callback: CallbackQuery, state: FSMContext):
    """Активация купона"""
    await callback.message.edit_text(
        "🎫 <b>Активация купона</b>\n\n"
        "Введите промокод:\n\n"
        "Чтобы отменить: /cancel",
        parse_mode="HTML",
        reply_markup=get_back_button("show_balance", "◀️ Назад")
    )
    
    await state.set_state(CouponStates.waiting_for_code)
    await callback.answer()


@router.message(CouponStates.waiting_for_code)
async def process_coupon(message: Message, state: FSMContext):
    """Обработка промокода"""
    code = message.text.strip().upper()
    
    from database.db_manager import get_user, update_user_balance_rub, update_user_balance_stars, update_user_balance_usdt
    from database.models import Coupon
    from database.db_manager import async_session_maker
    from sqlalchemy import select, update
    
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Ошибка")
        await state.clear()
        return
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(Coupon).where(Coupon.code == code, Coupon.is_active == True)
        )
        coupon = result.scalar_one_or_none()
        
        if not coupon:
            await message.answer("❌ Неверный промокод")
            await state.clear()
            return
        
        if coupon.used_count >= coupon.max_uses:
            await message.answer("❌ Промокод больше не действует")
            await state.clear()
            return
        
        if coupon.type == "money":

            await update_user_balance_rub(user.id, coupon.amount)
            await message.answer(f"✅ Промокод активирован! +{coupon.amount:.0f} ₽")
        
        elif coupon.type == "discount":
            from handlers.tariffs import temp_coupon
            temp_coupon[message.from_user.id] = {
                "type": "discount",
                "discount_percent": coupon.discount_percent,
                "tariff_days": coupon.tariff_days,
                "devices": coupon.devices,
                "code": coupon.code
            }
            await message.answer(
                f"✅ Промокод активирован! Скидка {coupon.discount_percent}% "
                f"на тариф {coupon.tariff_days} дней ({coupon.devices} устройств)\n\n"
                f"💰 <b>Воспользуйтесь скидкой при оформлении подписки!</b>",
                parse_mode="HTML"
            )
        
        await session.execute(
            update(Coupon).where(Coupon.id == coupon.id).values(
                used_count=coupon.used_count + 1,
                is_active=False if coupon.used_count + 1 >= coupon.max_uses else True
            )
        )
        await session.commit()
    
    await state.clear()

@router.callback_query(lambda c: c.data == "referral_program")
async def referral_program(callback: CallbackQuery, state: FSMContext = None):
    """Партнерская программа с 6 кнопками"""
    user = await get_user(callback.from_user.id)
    

    ref_link = await get_referral_link(callback.from_user.id)
    stats = await get_referral_stats(callback.from_user.id)
    

    code = stats.get('referral_code') or await get_or_create_referral_code(callback.from_user.id)
    
    example_1000 = 1000 * 0.5
    example_500 = 500 * 0.5
    example_150 = 150
    
    # Статус вывода
    withdrawal_status = "✅ Задан" if stats['withdrawal_method'] else "❌ Не задан"
    
    text = (
        "👥 <b>Партнёрская программа</b>\n\n"
        "<blockquote>💼 <b>Зарабатывай вместе с нами!</b>\n\n"
        "1) Приглашай друзей по своей уникальной ссылке и получай 50% с каждого пополнения.\n"
        "2) Выводи заработанные средства на удобный способ.</blockquote>\n\n"
        f"🔗 <b>Ваша ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"🔑 <b>Ваш код:</b> <code>{code}</code>\n\n"
        "<b>📊 Ваша статистика:</b>\n"
        f"<blockquote>👤 Приглашено: {stats['invited_count']}\n"
        f"💰 Заработано: {stats['total_earned']:.2f} ₽\n"
        f"🏦 Вывод: {withdrawal_status}</blockquote>\n\n"
        f"💸 <b>Вывод доступен от 1000₽.</b>\n\n"
        "<b>📈 Ставки по уровням:</b>\n"
        f"<blockquote>Уровень 1: 50% (пример: {example_1000:.0f}₽ с 1000₽)\n"
        f"Уровень 2: 25% (пример: {example_500:.0f}₽ с 1000₽)\n"
        f"Уровень 3: 15% (пример: {example_150:.0f}₽ с 1000₽)</blockquote>"
    )
    
    # 6 кнопок
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Вывести средства", callback_data="withdraw_funds")],
        [InlineKeyboardButton(text=f"🏦 Вывод: {withdrawal_status}", callback_data="setup_withdrawal")],
        [InlineKeyboardButton(text="👥 Пригласить друзей", callback_data="invite_friends")],
        [InlineKeyboardButton(text="📱 Показать QR", callback_data="show_qr")],
        [InlineKeyboardButton(text="🔄 Сменить код ссылки", callback_data="change_referral_code")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_profile")]
    ])
    

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    
    await callback.answer()

@router.callback_query(lambda c: c.data == "withdraw_funds")
async def withdraw_funds(callback: CallbackQuery):
    """Запрос на вывод средств"""
    stats = await get_referral_stats(callback.from_user.id)
    
    if stats['total_earned'] < 1000:
        await callback.answer(
            f"❌ Минимальная сумма вывода 1000₽.\nВаш баланс: {stats['total_earned']:.2f}₽",
            show_alert=True
        )
        return
    
    if not stats['withdrawal_method'] or not stats['withdrawal_details']:
        await callback.answer(
            "❌ Сначала настройте способ вывода в разделе «Вывод»",
            show_alert=True
        )
        return
    
    from services.referral_service import create_withdrawal_request
    from config import ADMIN_IDS
    
    success = await create_withdrawal_request(
        user_id=callback.from_user.id,
        amount=stats['total_earned'],
        method=stats['withdrawal_method'],
        details=stats['withdrawal_details']
    )
    
    if success:
        await callback.answer(
            "✅ Заявка на вывод отправлена!\nОжидайте обработки (до 24 часов)",
            show_alert=True
        )
        
        for admin_id in ADMIN_IDS:
            try:
                await callback.bot.send_message(
                    chat_id=admin_id,
                    text=f"💰 <b>Новая заявка на вывод!</b>\n\n"
                         f"👤 Пользователь: {callback.from_user.id}\n"
                         f"💸 Сумма: {stats['total_earned']:.2f}₽\n"
                         f"🏦 Способ: {stats['withdrawal_method']}\n"
                         f"🧾 Реквизиты: {stats['withdrawal_details']}",
                    parse_mode="HTML"
                )
            except:
                pass
    else:
        await callback.answer(
            "❌ Ошибка создания заявки. Попробуйте позже.",
            show_alert=True
        )


@router.callback_query(lambda c: c.data == "setup_withdrawal")
async def setup_withdrawal(callback: CallbackQuery, state: FSMContext):
    """Настройка способа вывода"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Банковская карта", callback_data="withdraw_card")],
        [InlineKeyboardButton(text="🟢 USDT (TRC20)", callback_data="withdraw_usdt")],
        [InlineKeyboardButton(text="💰 QIWI", callback_data="withdraw_qiwi")],
        [InlineKeyboardButton(text="📱 СБП", callback_data="withdraw_sbp")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="referral_program")]
    ])
    
    await callback.message.edit_text(
        "🏦 <b>Выберите способ вывода средств:</b>\n\n"
        "После выбора введите реквизиты.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("withdraw_"))
async def select_withdrawal_method(callback: CallbackQuery, state: FSMContext):
    """Выбор метода вывода"""
    method = callback.data.split("_")[1]
    
    method_names = {
        "card": "Банковская карта",
        "usdt": "USDT (TRC20)",
        "qiwi": "QIWI",
        "sbp": "СБП"
    }
    
    method_name = method_names.get(method, method)
    
    await state.update_data(method=method_name)
    await state.set_state(WithdrawalStates.waiting_for_details)
    
    await callback.message.edit_text(
        f"💳 <b>Выбран способ: {method_name}</b>\n\n"
        f"Введите реквизиты для вывода:\n"
        f"• Для карты: номер карты\n"
        f"• Для USDT: адрес кошелька\n"
        f"• Для QIWI: номер телефона\n"
        f"• Для СБП: номер телефона\n\n"
        f"<i>Отправьте одним сообщением:</i>",
        reply_markup=get_back_button("setup_withdrawal", "◀️ Назад"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(WithdrawalStates.waiting_for_details)
async def save_withdrawal_details(message: Message, state: FSMContext):
    """Сохранение реквизитов"""
    data = await state.get_data()
    method = data.get("method")
    details = message.text
    
    success = await update_withdrawal_info(message.from_user.id, method, details)
    
    if success:
        await message.answer(
            f"✅ <b>Реквизиты сохранены!</b>\n\n"
            f"🏦 Способ: {method}\n"
            f"🧾 Реквизиты: {details}\n\n"
            f"Вывод доступен от 1000₽.",
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Ошибка сохранения. Попробуйте позже.")
    
    await state.clear()
    

    from handlers.profile import referral_program
    await referral_program(message)


@router.callback_query(lambda c: c.data == "invite_friends")
async def invite_friends(callback: CallbackQuery):
    """Поделиться ссылкой (через Telegram)"""
    ref_link = await get_referral_link(callback.from_user.id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поделиться", switch_inline_query=ref_link)],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="referral_program")]
    ])
    
    await callback.message.edit_text(
        f"🔗 <b>Ваша партнёрская ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"📤 Нажмите на кнопку ниже, чтобы поделиться ссылкой с друзьями!",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "show_qr")
async def show_qr(callback: CallbackQuery):
    """Показать QR-код со ссылкой"""
    ref_link = await get_referral_link(callback.from_user.id)
    

    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(ref_link)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    

    bio = BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    
    try:
        await callback.message.delete()
    except:
        pass
    
    await callback.message.answer_photo(
        photo=BufferedInputFile(bio.getvalue(), filename="qr.png"),
        caption=f"🔗 <b>QR-код вашей партнёрской ссылки:</b>\n\n"
                f"<code>{ref_link}</code>\n\n"
                f"📱 Наведите камеру на QR-код",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_from_qr")]
        ])
    )
    
    await callback.answer()


@router.callback_query(lambda c: c.data == "back_from_qr")
async def back_from_qr(callback: CallbackQuery):
    """Возврат из QR в партнерскую программу"""
    try:
        await callback.message.delete()
    except:
        pass
    
    await send_referral_program(callback.message, callback.from_user.id)
    await callback.answer()

async def send_referral_program(message, user_id: int):
    """Отправка партнерской программы новым сообщением"""
    user = await get_user(user_id)
    
    ref_link = await get_referral_link(user_id)
    stats = await get_referral_stats(user_id)
    code = stats.get('referral_code') or await get_or_create_referral_code(user_id)
    
    example_1000 = 1000 * 0.5
    example_500 = 500 * 0.5
    example_150 = 150
    withdrawal_status = "✅ Задан" if stats['withdrawal_method'] else "❌ Не задан"
    
    text = (
        "👥 <b>Партнёрская программа</b>\n\n"
        "<blockquote>💼 <b>Зарабатывай вместе с нами!</b>\n\n"
        "1) Приглашай друзей по своей уникальной ссылке и получай 50% с каждого пополнения.\n"
        "2) Выводи заработанные средства на удобный способ.</blockquote>\n\n"
        f"🔗 <b>Ваша ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"🔑 <b>Ваш код:</b> <code>{code}</code>\n\n"
        "<b>📊 Ваша статистика:</b>\n"
        f"<blockquote>👤 Приглашено: {stats['invited_count']}\n"
        f"💰 Заработано: {stats['total_earned']:.2f} ₽\n"
        f"🏦 Вывод: {withdrawal_status}</blockquote>\n\n"
        f"💸 <b>Вывод доступен от 1000₽.</b>\n\n"
        "<b>📈 Ставки по уровням:</b>\n"
        f"<blockquote>Уровень 1: 50% (пример: {example_1000:.0f}₽ с 1000₽)\n"
        f"Уровень 2: 25% (пример: {example_500:.0f}₽ с 1000₽)\n"
        f"Уровень 3: 15% (пример: {example_150:.0f}₽ с 1000₽)</blockquote>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Вывести средства", callback_data="withdraw_funds")],
        [InlineKeyboardButton(text=f"🏦 Вывод: {withdrawal_status}", callback_data="setup_withdrawal")],
        [InlineKeyboardButton(text="👥 Пригласить друзей", callback_data="invite_friends")],
        [InlineKeyboardButton(text="📱 Показать QR", callback_data="show_qr")],
        [InlineKeyboardButton(text="🔄 Сменить код ссылки", callback_data="change_referral_code")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_profile")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
@router.callback_query(lambda c: c.data == "change_referral_code")
async def change_referral_code(callback: CallbackQuery, state: FSMContext):
    """Запрос на смену кода ссылки"""
    text = (
        "⚠️ <b>Внимание! Смена кода партнёрской ссылки</b>\n\n"
        "Вы получите новую ссылку с уникальным кодом (например: partner_abc12345).\n"
        "Старая ссылка продолжит работать.\n\n"
        "Обе ссылки будут активны и засчитывать партнеров.\n\n"
        "Вы уверены, что хотите сгенерировать новый код?"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, сменить", callback_data="confirm_change_code")],
        [InlineKeyboardButton(text="❌ Нет, не надо", callback_data="referral_program")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "confirm_change_code")
async def confirm_change_code(callback: CallbackQuery, state: FSMContext):
    """Подтверждение смены кода - запрос нового кода"""
    await state.set_state(ChangeCodeStates.waiting_for_new_code)
    
    text = (
        "🔗 <b>Введите новый код для партнёрской ссылки.</b>\n\n"
        "Только латиница/цифры и подчёркивание.\n"
        "Диапазон: 3–32 символа.\n\n"
        "Пример: <code>solonet</code>\n\n"
        "Чтобы отменить: напишите <code>отмена</code>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Отмена", callback_data="referral_program")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(ChangeCodeStates.waiting_for_new_code)
async def save_new_code(message: Message, state: FSMContext):
    """Сохранение нового кода"""
    new_code = message.text.strip()
    
    if new_code.lower() == "отмена":
        await state.clear()
        from handlers.profile import referral_program
        await referral_program(message)
        return
    
    import re
    if not re.match(r'^[a-zA-Z0-9_]{3,32}$', new_code):
        await message.answer(
            "❌ <b>Неверный формат кода!</b>\n\n"
            "Код должен содержать только:\n"
            "• Латинские буквы (a-z, A-Z)\n"
            "• Цифры (0-9)\n"
            "• Нижнее подчеркивание (_)\n\n"
            "Длина: 3-32 символа.\n\n"
            "Попробуйте ещё раз:",
            parse_mode="HTML"
        )
        return
    
    success = await update_referral_code(message.from_user.id, new_code)
    
    if success:
        await message.answer(
            f"✅ <b>Код успешно изменён!</b>\n\n"
            f"🔗 Ваша новая ссылка:\n"
            f"<code>https://t.me/your_bot?start=ref_{new_code}</code>\n\n"
            f"Старая ссылка продолжит работать.",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ <b>Этот код уже занят!</b>\n\n"
            "Пожалуйста, выберите другой код.",
            parse_mode="HTML"
        )
        return
    
    await state.clear()
    

    from handlers.profile import referral_program
    await referral_program(message)

@router.callback_query(lambda c: c.data == "back_to_profile")
async def back_to_profile_from_referral(callback: CallbackQuery):
    """Возврат из партнерской программы в профиль"""
    user = await get_user(callback.from_user.id)
    
    if not user:
        await callback.answer("Ошибка: пользователь не найден", show_alert=True)
        return
    
    subscription = await get_active_subscription(user.id)
    profile_text = format_profile_message(user, subscription)
    
    try:
        await callback.message.edit_text(
            profile_text,
            reply_markup=get_profile_menu(),
            parse_mode="HTML"
        )
    except:
        await callback.message.answer(
            profile_text,
            reply_markup=get_profile_menu(),
            parse_mode="HTML"
        )
    await callback.answer()

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.db_manager import get_user_by_telegram_id, transfer_subscription, update_user_balance, get_user
from config import TARIFFS

class GiftStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_tariff = State()


@router.callback_query(lambda c: c.data == "gift_subscription")
async def gift_subscription_start(callback: CallbackQuery, state: FSMContext):
    """Начало процесса дарения подписки"""
    await callback.message.edit_text(
        "🎁 <b>Подарить подписку</b>\n\n"
        "Введите Telegram ID пользователя, которому хотите подарить подписку.\n\n"
        "Как найти ID: @userinfobot\n\n"
        "Чтобы отменить: /cancel",
        parse_mode="HTML",
        reply_markup=get_back_button("show_balance", "◀️ Назад")
    )
    
    await state.set_state(GiftStates.waiting_for_user_id)
    await callback.answer()


@router.message(GiftStates.waiting_for_user_id)
async def gift_get_user_id(message: Message, state: FSMContext):
    """Получение ID пользователя для подарка"""
    try:
        target_id = int(message.text.strip())
        
        target_user = await get_user_by_telegram_id(target_id)
        
        if not target_user:
            await message.answer(
                "❌ Пользователь с таким ID не найден.\n"
                "Убедитесь, что он зарегистрирован в боте.\n\n"
                "Попробуйте ещё раз или /cancel"
            )
            return
        

        await state.update_data(target_id=target_id)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 1 день - 10₽", callback_data="gift_tariff_1")],
            [InlineKeyboardButton(text="📅 30 дней - 150₽", callback_data="gift_tariff_30")],
            [InlineKeyboardButton(text="📅 90 дней - 400₽", callback_data="gift_tariff_90")],
            [InlineKeyboardButton(text="📅 180 дней - 600₽", callback_data="gift_tariff_180")],
            [InlineKeyboardButton(text="📅 360 дней - 999₽", callback_data="gift_tariff_360")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="show_balance")]
        ])
        
        await message.answer(
            f"🎁 <b>Вы выбрали пользователя:</b>\n"
            f"👤 {target_user.first_name or target_user.username}\n"
            f"🆔 {target_user.telegram_id}\n\n"
            f"📋 <b>Выберите тариф для подарка:</b>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(GiftStates.waiting_for_tariff)
        
    except ValueError:
        await message.answer("❌ Введите корректный ID (только цифры)")


@router.callback_query(lambda c: c.data.startswith("gift_tariff_"))
async def gift_select_tariff(callback: CallbackQuery, state: FSMContext):
    """Выбор тарифа для подарка"""
    tariff_days = int(callback.data.split("_")[2])
    tariff_info = TARIFFS.get(tariff_days)
    
    if not tariff_info:
        await callback.answer("Тариф не найден", show_alert=True)
        return
    
    data = await state.get_data()
    target_id = data.get("target_id")
    target_user = await get_user_by_telegram_id(target_id)
    

    sender = await get_user(callback.from_user.id)
    
    total_price = tariff_info["price"]
    
    if sender.balance < total_price:
        need = total_price - sender.balance
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="show_balance")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="show_balance")]
        ])
        
        await callback.message.edit_text(
            f"❌ <b>Недостаточно средств!</b>\n\n"
            f"💰 Ваш баланс: {sender.balance:.2f} ₽\n"
            f"💸 Стоимость подарка: {total_price:.2f} ₽\n"
            f"📉 Не хватает: {need:.2f} ₽\n\n"
            f"Пополните баланс и повторите попытку.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
        return
    

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, подарить", callback_data=f"gift_confirm_{tariff_days}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="show_balance")]
    ])
    
    await callback.message.edit_text(
        f"🎁 <b>Подтверждение подарка</b>\n\n"
        f"👤 <b>Кому:</b> {target_user.first_name or target_user.username}\n"
        f"🆔 <b>ID:</b> {target_user.telegram_id}\n\n"
        f"📅 <b>Тариф:</b> {tariff_days} дней\n"
        f"💰 <b>Стоимость:</b> {total_price:.2f} ₽\n\n"
        f"<i>Средства будут списаны с вашего баланса.</i>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.update_data(tariff_days=tariff_days, total_price=total_price)
    await callback.answer()


@router.callback_query(lambda c: c.data == "deposit_rub_disabled")
async def deposit_rub_disabled(callback: CallbackQuery):
    """RUB временно недоступен"""
    await callback.answer("❌ Пополнение в RUB временно недоступно. Используйте Stars или USDT.", show_alert=True)

@router.callback_query(lambda c: c.data.startswith("gift_confirm_"))
async def gift_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтверждение дарения подписки"""
    tariff_days = int(callback.data.split("_")[2])
    
    data = await state.get_data()
    target_id = data.get("target_id")
    total_price = data.get("total_price")
    
    sender = await get_user(callback.from_user.id)
    target_user = await get_user_by_telegram_id(target_id)
    

    if sender.balance < total_price:
        await callback.answer("❌ Недостаточно средств!", show_alert=True)
        await callback.message.edit_text(
            "❌ Недостаточно средств. Пополните баланс.",
            reply_markup=get_back_button("show_balance", "◀️ Назад")
        )
        return
    

    await update_user_balance(sender.id, -total_price)
    

    await transfer_subscription(
        from_user_id=sender.id,
        to_user_id=target_user.id,
        tariff_days=tariff_days,
        devices_limit=1
    )
    

    try:
        await callback.bot.send_message(
            chat_id=target_user.telegram_id,
            text=f"🎉 <b>Вам подарили подписку!</b>\n\n"
                 f"👤 <b>От:</b> {sender.first_name or sender.username}\n"
                 f"📅 <b>Тариф:</b> {tariff_days} дней\n\n"
                 f"🔌 Используйте кнопку «Подключить устройство» в личном кабинете.",
            parse_mode="HTML"
        )
    except:
        pass

    await callback.message.edit_text(
        f"✅ <b>Подписка успешно подарена!</b>\n\n"
        f"🎁 <b>Кому:</b> {target_user.first_name or target_user.username}\n"
        f"📅 <b>Тариф:</b> {tariff_days} дней\n"
        f"💰 <b>Списано:</b> {total_price:.2f} ₽\n"
        f"💳 <b>Остаток:</b> {sender.balance - total_price:.2f} ₽",
        reply_markup=get_back_button("show_balance", "◀️ Назад"),
        parse_mode="HTML"
    )
    
    await state.clear()
    await callback.answer()