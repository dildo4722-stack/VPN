import time
from aiogram import Router, F
from aiogram.types import (
    CallbackQuery, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    LabeledPrice, 
    PreCheckoutQuery, 
    Message
)
from aiogram.fsm.context import FSMContext

from config import TARIFFS, MAX_DEVICES
from database.db_manager import get_user, update_user_balance, get_active_subscription, get_usd_rate
from keyboards.inline_keyboards import (
    get_device_count_menu, 
    get_payment_method_menu, 
    get_tariff_menu,
    get_back_button
)
from services.payment_service import (
    create_crypto_payment,
    check_crypto_payment,
    activate_subscription_after_payment
)
from utils.text_formatter import format_tariff_info

router = Router()
temp_tariff_selection = {}
temp_coupon = {}
temp_rub_payment = {}  
temp_subscription_payments = {}  


@router.callback_query(lambda c: c.data == "extend_subscription")
async def extend_subscription(callback: CallbackQuery):
    """Продление подписки - проверяем активированный купон"""
    user = await get_user(callback.from_user.id)
    subscription = await get_active_subscription(user.id)
    
    coupon_data = temp_coupon.get(callback.from_user.id)
    
    if subscription:
        end_date_str = subscription.end_date.strftime("%Y-%m-%d %H:%M:%S")
        text = (
            f"💰 Баланс: {user.balance:.2f} ₽\n\n"
            f"📅 Текущая дата истечения подписки: {end_date_str} 🔑\n\n"
        )
        if coupon_data and coupon_data.get("type") == "discount":
            text += f"🎫 <b>Активирована скидка {coupon_data['discount_percent']}%!</b>\n\n"
        text += f"📋 Выберите план продления:"
    else:
        text = "📋 Выберите план подписки:"
        if coupon_data and coupon_data.get("type") == "discount":
            text = f"🎫 <b>Активирована скидка {coupon_data['discount_percent']}%!</b>\n\n{text}"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_tariff_menu()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("tariff_"))
async def select_tariff(callback: CallbackQuery):
    tariff_days = int(callback.data.split("_")[1])
    tariff_info = TARIFFS.get(tariff_days)
    
    if not tariff_info:
        await callback.answer("Тариф не найден", show_alert=True)
        return
    
    coupon_data = temp_coupon.get(callback.from_user.id)
    discount_percent = 0
    
    if coupon_data and coupon_data.get("type") == "discount":

        if (coupon_data.get("tariff_days") == tariff_days or coupon_data.get("tariff_days") == 0):
            discount_percent = coupon_data.get("discount_percent", 0)
    
    original_price = tariff_info["price"]
    discounted_price = original_price * (100 - discount_percent) / 100
    
    temp_tariff_selection[callback.from_user.id] = {
        "days": tariff_days,
        "base_price": original_price,
        "discounted_price": discounted_price,
        "discount_percent": discount_percent,
        "device_price": tariff_info["device_price"],
        "base_devices": tariff_info["base_devices"]
    }
    
    if discount_percent > 0:
        text = (
            f"🎫 <b>Применена скидка {discount_percent}%!</b>\n\n"
            f"📅 <b>{tariff_days} дней</b>\n"
            f"💰 Базовая цена: {original_price} ₽\n"
            f"💸 Цена со скидкой: <b>{discounted_price:.0f} ₽</b>\n\n"
        )
    else:
        text = format_tariff_info(
            tariff_days=tariff_days,
            base_price=tariff_info["price"],
            device_price=tariff_info["device_price"],
            max_devices=MAX_DEVICES
        )
    
    
    keyboard = get_device_count_menu(
        tariff_days=tariff_days,
        base_price=discounted_price,  
        device_price=tariff_info["device_price"]
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("devices_"))
async def select_devices_count(callback: CallbackQuery):
    _, tariff_days, devices_count = callback.data.split("_")
    tariff_days = int(tariff_days)
    devices_count = int(devices_count)
    
    selection = temp_tariff_selection.get(callback.from_user.id)
    if not selection:
        await callback.answer("Сессия истекла", show_alert=True)
        return
    
    tariff_info = TARIFFS.get(tariff_days)
    

    base_price = selection.get("discounted_price", tariff_info["price"])
    

    device_price = tariff_info["device_price"]
    if selection.get("discount_percent", 0) > 0:
        device_price = device_price * (100 - selection["discount_percent"]) / 100
    
    total_price = base_price + (devices_count - 1) * device_price
    
    from database.db_manager import get_usd_rate
    usd_rate = await get_usd_rate()
    usdt_amount = total_price / usd_rate
    
    temp_tariff_selection[callback.from_user.id].update({
        "devices": devices_count,
        "total_price_rub": total_price,
        "total_price_usdt": round(usdt_amount, 2)
    })
    
    discount_text = ""
    if selection.get("discount_percent", 0) > 0:
        discount_text = f"\n🎫 Скидка {selection['discount_percent']}% применена!"
    
    await callback.message.edit_text(
        f"💰 К оплате:\n"
        f"• {total_price:.2f} ₽\n"
        f"• {usdt_amount:.2f} USDT\n\n"
        f"📅 Тариф: {tariff_days} дней\n"
        f"📱 Устройств: {devices_count}{discount_text}\n\n"
        f"Выберите способ оплаты:",
        reply_markup=get_payment_method_menu(total_price)
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("pay_usdt_"))
async def pay_with_usdt(callback: CallbackQuery):
    """Оплата через USDT"""
    amount_rub = float(callback.data.split("_")[2])
    selection = temp_tariff_selection.get(callback.from_user.id)
    
    if not selection:
        await callback.answer("Сессия истекла, выберите тариф заново", show_alert=True)
        await callback.message.edit_text("📋 Выберите план подписки:", reply_markup=get_tariff_menu())
        return
    
    result = await create_crypto_payment(
        user_id=callback.from_user.id,
        amount_usdt=selection["total_price_usdt"],  
        tariff_days=selection["days"],
        devices_count=selection["devices"]
    )
    
    if not result["success"]:
        await callback.answer(f"Ошибка: {result.get('error', 'Неизвестная ошибка')}", show_alert=True)
        return
    
    selection["invoice_id"] = result["invoice_id"]
    
    message_text = (
        f"💳 <b>Счет на оплату USDT</b>\n\n"
        f"💰 Сумма: <b>{result['amount_usdt']} USDT</b>\n"
        f"📅 Тариф: {selection['days']} дней\n"
        f"📱 Устройств: {selection['devices']}\n\n"
        f"⏰ Счет действителен 1 час\n\n"
        f"<b>Как оплатить:</b>\n"
        f"1️⃣ Нажмите «Оплатить USDT»\n"
        f"2️⃣ Оплатите через @send или @CryptoBot\n"
        f"3️⃣ Вернитесь и нажмите «✅ Я оплатил»\n\n"
        f"<i>После оплаты подписка активируется автоматически!</i>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить USDT", url=result['pay_url'])],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"check_usdt_{result['invoice_id']}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_tariffs")]
    ])
    
    await callback.message.edit_text(message_text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("check_usdt_"))
async def check_usdt_payment(callback: CallbackQuery):
    """Проверка оплаты USDT"""
    invoice_id = int(callback.data.split("_")[2])
    selection = temp_tariff_selection.get(callback.from_user.id)
    
    await callback.message.edit_text("⏳ <b>Проверяем статус платежа...</b>", reply_markup=None, parse_mode="HTML")
    
    result = await check_crypto_payment(invoice_id)
    
    if result["status"] == "paid":
        success = await activate_subscription_after_payment(
            user_id=result["user_id"],
            tariff_days=result["tariff_days"],
            devices_count=result["devices_count"]
        )

        from services.referral_service import process_referral_payment
        await process_referral_payment(callback.from_user.id, selection["total_price_rub"])
        
        if success:
            await callback.message.edit_text(
                "✅ <b>Оплата успешно подтверждена!</b>\n\n"
                f"🎉 Подписка активирована!\n"
                f"📅 Тариф: {result['tariff_days']} дней\n"
                f"📱 Устройств: {result['devices_count']}\n\n"
                "🔌 Используйте кнопку «Подключить устройство» в личном кабинете.",
                reply_markup=get_back_button("back_to_profile", "◀️ В личный кабинет"),
                parse_mode="HTML"
            )
            if callback.from_user.id in temp_tariff_selection:
                del temp_tariff_selection[callback.from_user.id]
        else:
            await callback.message.edit_text(
                "❌ Ошибка активации подписки. Обратитесь в поддержку.",
                reply_markup=get_back_button("back_to_profile", "◀️ Назад")
            )
            
    elif result["status"] == "active":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Проверить еще раз", callback_data=f"check_usdt_{invoice_id}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_tariffs")]
        ])
        await callback.message.edit_text(
            "⏳ Платеж еще не обработан.\n\nОплатите счет и нажмите «Проверить еще раз».",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    elif result["status"] == "expired":
        await callback.message.edit_text(
            "❌ Счет истек. Пожалуйста, создайте новый счет.",
            reply_markup=get_tariff_menu(),
            parse_mode="HTML"
        )
        if callback.from_user.id in temp_tariff_selection:
            del temp_tariff_selection[callback.from_user.id]
    else:
        await callback.message.edit_text(
            "❓ Не удалось проверить статус платежа. Попробуйте позже.",
            reply_markup=get_back_button("back_to_tariffs", "◀️ Назад")
        )
    
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("pay_stars_"))
async def pay_with_stars(callback: CallbackQuery):
    """Оплата через Telegram Stars"""
    amount_rub = float(callback.data.split("_")[2])
    selection = temp_tariff_selection.get(callback.from_user.id)
    
    if not selection:
        await callback.answer("Сессия истекла, выберите тариф заново", show_alert=True)
        await callback.message.edit_text("📋 Выберите план подписки:", reply_markup=get_tariff_menu())
        return
    

    stars_amount = int(amount_rub)
    

    temp_tariff_selection[callback.from_user.id]["stars_amount"] = stars_amount
    
    prices = [LabeledPrice(label=f"VPN подписка на {selection['days']} дней", amount=stars_amount)]
    
    await callback.message.answer_invoice(
        title=f"VPN подписка на {selection['days']} дней",
        description=f"Тариф: {selection['days']} дней\nУстройств: {selection['devices']}\n\nПосле оплаты подписка активируется автоматически.",
        payload=f"stars_{callback.from_user.id}_{selection['days']}_{selection['devices']}_{int(time.time())}",
        provider_token="",
        currency="XTR",
        prices=prices,
        start_parameter="vpn_subscription",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Оплатить Stars", pay=True)]
        ])
    )
    
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    """Обработка предварительной проверки перед оплатой"""
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_deposit(message: Message):
    """Обработка успешной оплаты Stars для пополнения"""
    payment = message.successful_payment
    payload = payment.invoice_payload
    amount = int(payment.total_amount)  # сумма в Stars
    
    from database.db_manager import get_user, update_user_balance_stars
    from database.models import Payment
    from database.db_manager import async_session_maker
    
    print(f"DEBUG successful_deposit: payload={payload}, amount={amount}")
    
    if payload.startswith("deposit_stars"):
        parts = payload.split("_")
        user_id = int(parts[2])
        stars_amount = int(parts[3]) if len(parts) > 3 else amount
        
        print(f"DEBUG: user_id={user_id}, stars_amount={stars_amount}")
        
        if user_id == message.from_user.id:
            user = await get_user(user_id)
            if user:
                # Начисляем Stars
                await update_user_balance_stars(user.id, stars_amount)
                
                # Сохраняем в историю
                async with async_session_maker() as session:
                    payment_record = Payment(
                        user_id=user.id,
                        amount=stars_amount,
                        currency="STARS",
                        payment_method="stars",
                        status="success",
                        external_id=payload,
                        tariff_days=0,
                        devices_count=0
                    )
                    session.add(payment_record)
                    await session.commit()
                
                await message.answer(
                    f"✅ <b>Баланс пополнен!</b>\n\n"
                    f"⭐ Сумма: +{stars_amount} Stars",
                    parse_mode="HTML"
                )
            else:
                await message.answer("❌ Ошибка: пользователь не найден")
        else:
            await message.answer("❌ Ошибка: несоответствие пользователя")


@router.callback_query(lambda c: c.data == "back_to_tariffs")
async def back_to_tariffs(callback: CallbackQuery):
    await callback.message.edit_text("📋 Выберите план подписки:", reply_markup=get_tariff_menu())
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("pay_rub_"))
async def pay_with_rub(callback: CallbackQuery, state: FSMContext):
    """Оплата подписки в рублях через Platega"""
    amount_rub = float(callback.data.split("_")[2])
    selection = temp_tariff_selection.get(callback.from_user.id)
    
    if not selection:
        await callback.answer("Сессия истекла, выберите тариф заново", show_alert=True)
        await callback.message.edit_text("📋 Выберите план подписки:", reply_markup=get_tariff_menu())
        return
    
    # Сохраняем данные для последующей активации
    temp_rub_payment[callback.from_user.id] = {
        "tariff_days": selection["days"],
        "devices_count": selection["devices"],
        "amount_rub": amount_rub
    }
    
    # Показываем выбор способа оплаты
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 СБП (QR-код)", callback_data=f"subscription_rub_method_2")],
        [InlineKeyboardButton(text="🌍 Криптовалюта", callback_data=f"subscription_rub_method_13")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_tariffs")]
    ])
    
    await callback.message.edit_text(
        f"💳 <b>Оплата подписки в рублях</b>\n\n"
        f"📅 Тариф: {selection['days']} дней\n"
        f"📱 Устройств: {selection['devices']}\n"
        f"💰 Сумма: {amount_rub:.2f} ₽\n\n"
        f"Выберите способ оплаты:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("subscription_rub_method_"))
async def subscription_rub_process_payment(callback: CallbackQuery, state: FSMContext):
    """Обработка оплаты подписки через Platega"""
    method_id = int(callback.data.split("_")[3])
    
    payment_data = temp_rub_payment.get(callback.from_user.id)
    
    if not payment_data:
        await callback.answer("Ошибка: попробуйте снова", show_alert=True)
        return
    
    rub_amount = payment_data["amount_rub"]
    tariff_days = payment_data["tariff_days"]
    devices_count = payment_data["devices_count"]
    
    from services.platega_service import platega
    
    order_id = f"sub_{callback.from_user.id}_{int(time.time())}"
    
    result = await platega.create_invoice(
        amount=rub_amount,
        order_id=order_id,
        description=f"Оплата подписки VPN на {tariff_days} дней",
        telegram_id=callback.from_user.id,
        payment_method=method_id
    )
    
    if result.get("status") == "success":
        # 👇 ИСПРАВЛЕНО: используем transaction_id (UUID) как ключ
        transaction_id = result["transaction_id"]
        
        temp_subscription_payments[transaction_id] = {
            "user_id": callback.from_user.id,
            "amount": rub_amount,
            "tariff_days": tariff_days,
            "devices_count": devices_count,
            "payment_method": "platega",
            "order_id": order_id
        }
        
        # Очищаем временные данные
        if callback.from_user.id in temp_rub_payment:
            del temp_rub_payment[callback.from_user.id]
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", url=result['payment_url'])],
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"check_subscription_platega_{transaction_id}")],  # 👈 transaction_id
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_tariffs")]
        ])
        
        method_names = {
            2: "СБП (QR-код)",
            11: "Банковская карта",
            13: "Криптовалюта",
            12: "Международная карта"
        }
        method_name = method_names.get(method_id, "Оплата")
        
        await callback.message.edit_text(
            f"💳 <b>Счет на оплату подписки</b>\n\n"
            f"📅 Тариф: {tariff_days} дней\n"
            f"📱 Устройств: {devices_count}\n"
            f"💰 Сумма: {rub_amount:.2f} ₽\n"
            f"💳 Способ: {method_name}\n\n"
            f"1. Нажмите «Оплатить»\n"
            f"2. Оплатите удобным способом\n"
            f"3. Нажмите «Я оплатил»\n\n"
            f"<i>Счет действителен 1 час</i>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        error_msg = result.get('message', 'Неизвестная ошибка')
        await callback.message.edit_text(
            f"❌ Ошибка создания платежа: {error_msg}\n\n"
            f"Попробуйте другой способ оплаты.",
            reply_markup=get_back_button("back_to_tariffs", "◀️ Назад")
        )
    
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("check_subscription_platega_"))
async def check_subscription_platega_payment(callback: CallbackQuery):
    """Проверка оплаты подписки через Platega"""
    transaction_id = callback.data.split("_")[3]  # теперь это UUID
    
    from services.platega_service import platega
    from services.payment_service import activate_subscription_after_payment
    
    await callback.message.edit_text("⏳ Проверяем статус платежа...", reply_markup=None)
    
    result = await platega.check_payment(transaction_id)
    
    if result.get("status") == "success" and result.get("paid"):
        payment_data = temp_subscription_payments.get(transaction_id)  # ищем по UUID
        if payment_data:
            success = await activate_subscription_after_payment(
                user_id=payment_data["user_id"],
                tariff_days=payment_data["tariff_days"],
                devices_count=payment_data["devices_count"]
            )
            
            if success:
                await callback.message.edit_text(
                    f"✅ <b>Подписка оплачена!</b>\n\n"
                    f"🎉 Подписка активирована!\n"
                    f"📅 Тариф: {payment_data['tariff_days']} дней\n"
                    f"📱 Устройств: {payment_data['devices_count']}\n\n"
                    f"🔌 Используйте кнопку «Подключить устройство» в личном кабинете.",
                    reply_markup=get_back_button("back_to_profile", "◀️ В личный кабинет"),
                    parse_mode="HTML"
                )
                
                # Очищаем данные
                if transaction_id in temp_subscription_payments:
                    del temp_subscription_payments[transaction_id]
                if callback.from_user.id in temp_tariff_selection:
                    del temp_tariff_selection[callback.from_user.id]
            else:
                await callback.message.edit_text(
                    "❌ Ошибка активации подписки. Обратитесь в поддержку.",
                    reply_markup=get_back_button("back_to_profile", "◀️ Назад")
                )
    elif result.get("transaction_status") == "PENDING":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Проверить еще раз", callback_data=f"check_subscription_platega_{transaction_id}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_tariffs")]
        ])
        await callback.message.edit_text(
            "⏳ Платеж еще не обработан. Оплатите и нажмите «Проверить еще раз».",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            "❌ Платеж не найден или истек",
            reply_markup=get_back_button("back_to_tariffs", "◀️ Назад")
        )
    
    await callback.answer()