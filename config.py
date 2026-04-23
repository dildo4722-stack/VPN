import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///vpn_bot.db")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
BOT_USERNAME = os.getenv("BOT_USERNAME", "your_bot_username")


CRYPTOPAY_TOKEN = os.getenv("CRYPTOPAY_TOKEN", "")
CRYPTOPAY_TESTNET = os.getenv("CRYPTOPAY_TESTNET", "True").lower() == "true"

PLATEGA_MERCHANT_ID = os.getenv("PLATEGA_MERCHANT_ID")
PLATEGA_SECRET = os.getenv("PLATEGA_SECRET")

MAX_DEVICES = 6
TRIAL_DAYS = 3
TRIAL_TRAFFIC_GB = 10
TRIAL_DEVICES = 2

TARIFFS = {
    1: {"price": 9, "base_devices": 1, "device_price": 10},
    30: {"price": 149, "base_devices": 1, "device_price": 30},
    90: {"price": 399, "base_devices": 1, "device_price": 60},
    180: {"price": 599, "base_devices": 1, "device_price": 120},
    360: {"price": 999, "base_devices": 1, "device_price": 150},
}

BOT_NAME = "VPN Бот"