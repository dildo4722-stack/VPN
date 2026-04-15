from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update, delete
from config import DATABASE_URL
from database.models import Base, User, Subscription, Device, Payment, TariffConfig, CurrencyRate, Coupon
from datetime import datetime


engine = create_async_engine(DATABASE_URL, echo=True)
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Инициализация базы данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    



async def init_default_data():
    """Заполнение таблиц начальными данными"""
    async with async_session_maker() as session:
        for tariff in TariffConfig.get_defaults():
            result = await session.execute(
                select(TariffConfig).where(TariffConfig.days == tariff["days"])
            )
            if not result.scalar_one_or_none():
                session.add(TariffConfig(**tariff))
        
        rates = [
            {"currency": "usd", "rate_to_rub": 78.3},
            {"currency": "star", "rate_to_rub": 1.0},
        ]
        for rate in rates:
            result = await session.execute(
                select(CurrencyRate).where(CurrencyRate.currency == rate["currency"])
            )
            if not result.scalar_one_or_none():
                session.add(CurrencyRate(**rate))
        
        await session.commit()


async def get_user(telegram_id: int):
    """Получение пользователя по telegram_id"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()


async def create_user(telegram_id: int, username: str = None, first_name: str = None, referrer_id: int = None):
    """Создание нового пользователя"""
    async with async_session_maker() as session:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            referrer_id=referrer_id
        )
        session.add(user)
        await session.commit()
        return user


async def update_user_balance(user_id: int, amount: float):
    """Обновление баланса пользователя"""
    async with async_session_maker() as session:
        await session.execute(
            update(User).where(User.id == user_id).values(balance=User.balance + amount)
        )
        await session.commit()


async def get_active_subscription(user_id: int):
    """Получение активной подписки пользователя"""
    async with async_session_maker() as session:
        from datetime import datetime
        result = await session.execute(
            select(Subscription).where(
                Subscription.user_id == user_id,
                Subscription.is_active == True,
                Subscription.end_date > datetime.utcnow()
            ).order_by(Subscription.end_date.desc())
        )
        return result.scalar_one_or_none()


async def create_subscription(
    user_id: int, 
    tariff_days: int, 
    devices_limit: int = 1,
    total_traffic_gb: float = 0,
    is_trial: bool = False
):
    """Создание подписки"""
    from datetime import datetime, timedelta
    
    async with async_session_maker() as session:
        await session.execute(
            update(Subscription)
            .where(Subscription.user_id == user_id)
            .values(is_active=False)
        )
        
        end_date = datetime.utcnow() + timedelta(days=tariff_days)
        
        subscription = Subscription(
            user_id=user_id,
            tariff_days=tariff_days,
            end_date=end_date,
            total_traffic_gb=total_traffic_gb,
            devices_limit=devices_limit,
            is_trial=is_trial,
            is_active=True
        )
        session.add(subscription)
        await session.commit()
        return subscription
    
async def create_payment(user_id: int, amount: float, currency: str, payment_method: str, external_id: str, tariff_days: int, devices_count: int):
    async with async_session_maker() as session:
        payment = Payment(
            user_id=user_id,
            amount=amount,
            currency=currency,
            payment_method=payment_method,
            status="pending",
            external_id=external_id,
            tariff_days=tariff_days,
            devices_count=devices_count
        )
        session.add(payment)
        await session.commit()
        return payment

async def update_payment_status(external_id: str, status: str):
    async with async_session_maker() as session:
        await session.execute(
            update(Payment).where(Payment.external_id == external_id).values(
                status=status,
                completed_at=datetime.utcnow()
            )
        )
        await session.commit()

async def get_usd_rate() -> float:
    """Получение текущего курса USD из БД"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(CurrencyRate).where(CurrencyRate.currency == "usd")
        )
        rate = result.scalar_one_or_none()
        if rate:
            return rate.rate_to_rub
        default_rate = CurrencyRate(currency="usd", rate_to_rub=78.3)
        session.add(default_rate)
        await session.commit()
        return 78.3


async def update_usd_rate(new_rate: float) -> bool:
    """Обновление курса USD"""
    try:
        async with async_session_maker() as session:
            result = await session.execute(
                select(CurrencyRate).where(CurrencyRate.currency == "usd")
            )
            rate = result.scalar_one_or_none()
            
            if rate:
                rate.rate_to_rub = new_rate
            else:
                rate = CurrencyRate(currency="usd", rate_to_rub=new_rate)
                session.add(rate)
            
            await session.commit()
            return True
    except Exception as e:
        print(f"Ошибка обновления курса: {e}")
        return False
    
async def get_coupon(code: str):
    async with async_session_maker() as session:
        result = await session.execute(
            select(Coupon).where(Coupon.code == code, Coupon.is_active == True)
        )
        return result.scalar_one_or_none()

async def use_coupon(coupon_id: int, user_id: int):
    async with async_session_maker() as session:
        await session.execute(
            update(Coupon)
            .where(Coupon.id == coupon_id)
            .values(used_by=user_id, used_at=datetime.utcnow(), is_active=False)
        )
        await session.commit()

async def get_user_by_telegram_id(telegram_id: int):
    """Получение пользователя по telegram_id"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()


async def transfer_subscription(from_user_id: int, to_user_id: int, tariff_days: int, devices_limit: int):
    """Перевод подписки другому пользователю"""
    async with async_session_maker() as session:
        await session.execute(
            update(Subscription)
            .where(Subscription.user_id == to_user_id)
            .values(is_active=False)
        )
        
        from datetime import datetime, timedelta
        end_date = datetime.utcnow() + timedelta(days=tariff_days)
        
        subscription = Subscription(
            user_id=to_user_id,
            tariff_days=tariff_days,
            end_date=end_date,
            total_traffic_gb=0,
            devices_limit=devices_limit,
            is_active=True,
            is_trial=False
        )
        session.add(subscription)
        await session.commit()
        return subscription
    
async def get_user_balances(telegram_id: int):
    """Получение всех балансов пользователя"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user:
            return {
                "rub": user.balance_rub,
                "stars": user.balance_stars,
                "usdt": user.balance_usdt
            }
        return {"rub": 0, "stars": 0, "usdt": 0}
    
async def update_user_balance_rub(user_id: int, amount: float):
    """Обновление рублевого баланса"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.balance_rub += amount
            await session.commit()
            return True
        return False


async def update_user_balance_stars(user_id: int, amount: int):
    """Обновление баланса Stars"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.balance_stars += amount
            await session.commit()
            return True
        return False


async def update_user_balance_usdt(user_id: int, amount: float):
    """Обновление баланса USDT"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.balance_usdt += amount
            await session.commit()
            return True
        return False