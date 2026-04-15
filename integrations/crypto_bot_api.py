import logging
import aiohttp
from decimal import Decimal
from typing import Optional, Dict, Any

from config import CRYPTOPAY_TOKEN, CRYPTOPAY_TESTNET
from database.db_manager import create_payment, update_payment_status

logger = logging.getLogger(__name__)


class CryptoBotAPI:
    """Интеграция с Crypto Pay API (@send) - прямая работа с API"""
    
    def __init__(self):
        if CRYPTOPAY_TESTNET:
            self.base_url = "https://testnet-pay.crypt.bot/api"
        else:
            self.base_url = "https://pay.crypt.bot/api"
        
        self.headers = {
            "Crypto-Pay-API-Token": CRYPTOPAY_TOKEN,
            "Content-Type": "application/json"
        }
        self.session = None
    
    async def _request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Выполнение запроса к API"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            async with self.session.request(method, url, headers=self.headers, json=data) as response:
                result = await response.json()
                
                if response.status == 401:
                    logger.error(f"Ошибка 401: Неверный токен API. Проверьте CRYPTOPAY_TOKEN")
                    return {"ok": False, "error": "Unauthorized"}
                
                if not result.get("ok"):
                    logger.error(f"API ошибка: {result.get('error')}")
                    return {"ok": False, "error": result.get("error")}
                
                return result
                
        except Exception as e:
            logger.error(f"Ошибка запроса: {e}")
            return {"ok": False, "error": str(e)}
    
    async def get_me(self):
        """Проверка токена"""
        return await self._request("GET", "getMe")
    
    async def create_invoice(
        self,
        user_id: int,
        amount_rub: float,
        tariff_days: int,
        devices_count: int,
        usd_rate: float  
    ) -> Optional[Dict[str, Any]]:
        """Создание счета на оплату"""
        try:
            usdt_amount = Decimal(str(amount_rub)) / Decimal(str(usd_rate))
            usdt_amount = round(usdt_amount, 2)
            
            import time
            payload = f"{user_id}_{tariff_days}_{devices_count}_{int(time.time())}"
            
            data = {
                "asset": "USDT",
                "amount": str(usdt_amount),
                "description": f"VPN подписка на {tariff_days} дней",
                "payload": payload,
                "expires_in": 3600,
                "allow_comments": False,
                "allow_anonymous": True
            }
            
            result = await self._request("POST", "createInvoice", data)
            
            if not result.get("ok"):
                logger.error(f"Ошибка создания инвойса: {result}")
                return {"success": False, "error": result.get("error")}
            
            invoice = result["result"]
            
            await create_payment(
                user_id=user_id,
                amount=amount_rub,
                currency="USDT",
                payment_method="crypto",
                external_id=str(invoice["invoice_id"]),
                tariff_days=tariff_days,
                devices_count=devices_count
            )
            
            logger.info(f"Создан инвойс #{invoice['invoice_id']} на {usdt_amount} USDT")
            
            return {
                "success": True,
                "invoice_id": invoice["invoice_id"],
                "pay_url": invoice["bot_invoice_url"],
                "amount_usdt": float(usdt_amount),
                "amount_rub": amount_rub
            }
            
        except Exception as e:
            logger.error(f"Ошибка создания инвойса: {e}")
            return {"success": False, "error": str(e)}
    
    async def check_payment(self, invoice_id: int) -> Dict[str, Any]:
        """Проверка статуса оплаты"""
        try:
            result = await self._request("GET", f"getInvoices?invoice_ids={invoice_id}")
            
            if not result.get("ok"):
                return {"status": "error", "paid": False}
            
            invoices = result.get("result", [])
            if not invoices:
                return {"status": "not_found", "paid": False}
            
            invoice = invoices[0]
            status = invoice.get("status")
            
            if status == "paid":
                await update_payment_status(str(invoice_id), "success")
                
                payload = invoice.get("payload", "")
                parts = payload.split("_")
                
                if len(parts) >= 3:
                    return {
                        "status": "paid",
                        "paid": True,
                        "user_id": int(parts[0]),
                        "tariff_days": int(parts[1]),
                        "devices_count": int(parts[2])
                    }
                return {"status": "paid", "paid": True}
            
            elif status == "expired":
                return {"status": "expired", "paid": False}
            else:
                return {"status": "active", "paid": False}
                
        except Exception as e:
            logger.error(f"Ошибка проверки платежа: {e}")
            return {"status": "error", "paid": False}
    
    async def close(self):
        if self.session:
            await self.session.close()


crypto_bot = CryptoBotAPI()