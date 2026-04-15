from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, BigInteger, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    balance = Column(Float, default=0.0)
    
    balance_rub = Column(Float, default=0.0)
    balance_stars = Column(Integer, default=0)
    balance_usdt = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    is_admin = Column(Boolean, default=False)
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    referral_earnings = Column(Float, default=0.0)
    withdrawal_method = Column(String(50), nullable=True)
    withdrawal_details = Column(Text, nullable=True)
    referral_code = Column(String(50), nullable=True, unique=True)
    
    subscriptions = relationship("Subscription", back_populates="user")
    devices = relationship("Device", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    referrer = relationship("User", remote_side=[id], backref="referrals")
    referral_transactions = relationship("ReferralTransaction", foreign_keys="ReferralTransaction.user_id", back_populates="user")
    withdrawal_requests = relationship("WithdrawalRequest", back_populates="user")


class ReferralTransaction(Base):
    __tablename__ = "referral_transactions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    level = Column(Integer, default=1)
    amount = Column(Float, nullable=False)
    payment_amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", foreign_keys=[user_id], back_populates="referral_transactions")
    from_user = relationship("User", foreign_keys=[from_user_id])


class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tariff_days = Column(Integer)
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=False)
    total_traffic_gb = Column(Float, default=0.0)
    used_traffic_gb = Column(Float, default=0.0)
    devices_limit = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    is_trial = Column(Boolean, default=False)
    
    user = relationship("User", back_populates="subscriptions")
    devices = relationship("Device", back_populates="subscription")
    
    @property
    def remaining_traffic_gb(self):
        return max(0, self.total_traffic_gb - self.used_traffic_gb)
    
    @property
    def remaining_days(self):
        delta = self.end_date - datetime.utcnow()
        return max(0, delta.days)


class Device(Base):
    __tablename__ = "devices"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    device_type = Column(String(50))
    device_name = Column(String(100), nullable=True)
    config_link = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="devices")
    subscription = relationship("Subscription", back_populates="devices")


class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(20))
    payment_method = Column(String(50))
    status = Column(String(20), default="pending")
    external_id = Column(String(200), nullable=True)
    tariff_days = Column(Integer, nullable=True)
    devices_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="payments")


class TariffConfig(Base):
    __tablename__ = "tariff_configs"
    
    id = Column(Integer, primary_key=True)
    days = Column(Integer, unique=True, nullable=False)
    base_price = Column(Float, nullable=False)
    base_devices = Column(Integer, default=1)
    device_price = Column(Float, nullable=False)
    
    @classmethod
    def get_defaults(cls):  
        return [
            {"days": 1, "base_price": 10, "base_devices": 1, "device_price": 10},
            {"days": 30, "base_price": 150, "base_devices": 1, "device_price": 30},
            {"days": 90, "base_price": 400, "base_devices": 1, "device_price": 60},
            {"days": 180, "base_price": 600, "base_devices": 1, "device_price": 120},
            {"days": 360, "base_price": 999, "base_devices": 1, "device_price": 150},
        ]


class CurrencyRate(Base):
    __tablename__ = "currency_rates"
    
    id = Column(Integer, primary_key=True)
    currency = Column(String(20), unique=True)
    rate_to_rub = Column(Float, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class WithdrawalRequest(Base):
    __tablename__ = "withdrawal_requests"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    method = Column(String(50), nullable=False)
    details = Column(Text, nullable=False)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="withdrawal_requests")

class Coupon(Base):
    __tablename__ = "coupons"
    
    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)
    type = Column(String(20), nullable=False)
    discount_percent = Column(Integer, nullable=True)
    tariff_days = Column(Integer, nullable=True)
    devices = Column(Integer, nullable=True)
    amount = Column(Float, nullable=True)  # 👈 ИЗМЕНИТЕ С nullable=False на nullable=True
    max_uses = Column(Integer, default=1)
    used_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

