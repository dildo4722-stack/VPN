import logging
import random
import string
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import select, func, update

from database.db_manager import async_session_maker  # 👈 ДОБАВИТЬ ЭТУ СТРОКУ
from database.models import User, ReferralTransaction

logger = logging.getLogger(__name__)


async def generate_unique_code() -> str:
    """Генерация уникального кода для ссылки"""
    async with async_session_maker() as session:
        while True:
            
            code = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            
            result = await session.execute(
                select(User).where(User.referral_code == code)
            )
            if not result.scalar_one_or_none():
                return code


async def get_or_create_referral_code(user_id: int) -> str:
    """Получение или создание реферального кода"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            if not user.referral_code:
                user.referral_code = await generate_unique_code()
                await session.commit()
            return user.referral_code
        return None


async def update_referral_code(user_id: int, new_code: str) -> bool:
    """Обновление реферального кода"""
    
    if not new_code or len(new_code) < 3 or len(new_code) > 32:
        return False
    
   
    allowed_chars = string.ascii_lowercase + string.ascii_uppercase + string.digits + "_"
    if not all(c in allowed_chars for c in new_code):
        return False
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.referral_code == new_code)
        )
        if result.scalar_one_or_none():
            return False
        
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.referral_code = new_code
            await session.commit()
            return True
        return False


async def get_referral_link(user_id: int) -> str:
    """Получение реферальной ссылки"""
    from config import BOT_USERNAME
    
    code = await get_or_create_referral_code(user_id)
    if code:
        return f"https://t.me/{BOT_USERNAME}?start=ref_{code}"
    return None


async def get_user_by_code(code: str):
    """Получение пользователя по реферальному коду"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.referral_code == code)
        )
        return result.scalar_one_or_none()


async def get_referral_stats(user_id: int) -> Dict[str, Any]:
    """Получение статистики по рефералам"""
    async with async_session_maker() as session:
        
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return {
                "invited_count": 0,
                "total_earned": 0.0,
                "withdrawal_method": None,
                "withdrawal_details": None,
                "referral_code": None
            }
        
        
        result = await session.execute(
            select(func.count()).select_from(User).where(User.referrer_id == user.id)
        )
        invited_count = result.scalar() or 0
        
        
        result = await session.execute(
            select(func.sum(ReferralTransaction.amount)).where(ReferralTransaction.user_id == user.id)
        )
        total_earned = result.scalar() or 0.0
        
        return {
            "invited_count": invited_count,
            "total_earned": float(total_earned),
            "withdrawal_method": user.withdrawal_method,
            "withdrawal_details": user.withdrawal_details,
            "referral_code": user.referral_code
        }


async def add_referral_earning(
    referrer_id: int,
    from_user_id: int,
    level: int,
    amount: float,
    payment_amount: float
) -> bool:
    """Начисление реферального вознаграждения"""
    try:
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == referrer_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return False
            
            user.balance += amount
            user.referral_earnings = (user.referral_earnings or 0) + amount
            
            transaction = ReferralTransaction(
                user_id=user.id,
                from_user_id=from_user_id,
                level=level,
                amount=amount,
                payment_amount=payment_amount
            )
            session.add(transaction)
            await session.commit()
            return True
            
    except Exception as e:
        logger.error(f"Ошибка начисления: {e}")
        return False


async def update_withdrawal_info(user_id: int, method: str, details: str) -> bool:
    """Обновление информации для вывода"""
    try:
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user:
                user.withdrawal_method = method
                user.withdrawal_details = details
                await session.commit()
                return True
            return False
    except Exception as e:
        logger.error(f"Ошибка обновления: {e}")
        return False


async def process_referral_payment(user_id: int, payment_amount: float) -> None:
    """Обработка реферальных начислений"""
    try:
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user or not user.referrer_id:
                return
            
            
            level1_amount = payment_amount * 0.35
            await add_referral_earning(
                referrer_id=user.referrer_id,
                from_user_id=user.telegram_id,
                level=1,
                amount=level1_amount,
                payment_amount=payment_amount
            )
            
           
            result2 = await session.execute(
                select(User).where(User.id == user.referrer_id)
            )
            referrer1 = result2.scalar_one_or_none()
            
            if referrer1 and referrer1.referrer_id:
                level2_amount = payment_amount * 0.17
                await add_referral_earning(
                    referrer_id=referrer1.referrer_id,
                    from_user_id=user.telegram_id,
                    level=2,
                    amount=level2_amount,
                    payment_amount=payment_amount
                )
                
                
                result3 = await session.execute(
                    select(User).where(User.id == referrer1.referrer_id)
                )
                referrer2 = result3.scalar_one_or_none()
                
                if referrer2 and referrer2.referrer_id:
                    level3_amount = payment_amount * 0.10
                    await add_referral_earning(
                        referrer_id=referrer2.referrer_id,
                        from_user_id=user.telegram_id,
                        level=3,
                        amount=level3_amount,
                        payment_amount=payment_amount
                    )
                    
    except Exception as e:
        logger.error(f"Ошибка обработки платежа: {e}")

async def create_withdrawal_request(user_id: int, amount: float, method: str, details: str) -> bool:
    """Создание заявки на вывод"""
    try:
        from database.db_manager import async_session_maker
        from database.models import WithdrawalRequest, User
        from sqlalchemy import select
        
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return False
            
            request = WithdrawalRequest(
                user_id=user.id,
                amount=amount,
                method=method,
                details=details,
                status="pending"
            )
            session.add(request)
            await session.commit()
            return True
    except Exception as e:
        print(f"Ошибка создания заявки: {e}")
        return False