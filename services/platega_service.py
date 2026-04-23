import aiohttp
import json
from config import PLATEGA_MERCHANT_ID, PLATEGA_SECRET


class PlategaAPI:
    def __init__(self):
        self.base_url = "https://app.platega.io"
        self.merchant_id = PLATEGA_MERCHANT_ID
        self.secret = PLATEGA_SECRET

    async def create_invoice(self, amount: float, order_id: str, description: str = "", telegram_id: int = None, payment_method: int = 2) -> dict:
        """Создание счета на оплату с выбором метода"""
        
        if telegram_id:
            description = f"TgId:{telegram_id} | {description}"
        
        payload = {
            "paymentMethod": payment_method,
            "paymentDetails": {
                "amount": amount,
                "currency": "RUB"
            },
            "description": description[:255],
            "return": f"https://t.me/ShadowRouteVPNBot",
            "failedUrl": f"https://t.me/ShadowRouteVPNBot",
            "payload": order_id
        }
        
        headers = {
            "Content-Type": "application/json",
            "X-MerchantId": self.merchant_id,
            "X-Secret": self.secret
        }

        print(f"DEBUG: Создаём платеж с методом {payment_method}, сумма {amount}")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/transaction/process",
                json=payload,
                headers=headers
            ) as response:
                response_text = await response.text()
                print(f"DEBUG Status: {response.status}")
                print(f"DEBUG Response: {response_text}")
                
                if response.status == 200:
                    try:
                        data = json.loads(response_text)
                        return {
                            "status": "success",
                            "transaction_id": data.get("transactionId"),
                            "payment_url": data.get("redirect"),
                        }
                    except Exception as e:
                        print(f"DEBUG Ошибка парсинга: {e}")
                        return {"status": "error", "message": "Ошибка парсинга ответа"}
                else:
                    try:
                        error_data = json.loads(response_text)
                        error_msg = error_data.get("message", response_text)
                    except:
                        error_msg = response_text
                    
                    return {"status": "error", "message": f"Ошибка {response.status}: {error_msg}"}

    async def check_payment(self, transaction_id: str) -> dict:
        """Проверка статуса оплаты по ID транзакции (UUID)"""
        headers = {
            "X-MerchantId": self.merchant_id,
            "X-Secret": self.secret
        }

        async with aiohttp.ClientSession() as session:
            # GET /transaction/{id}
            async with session.get(
                f"{self.base_url}/transaction/{transaction_id}",
                headers=headers
            ) as response:
                response_text = await response.text()
                print(f"DEBUG Status check: {response.status}")
                print(f"DEBUG Response check: {response_text}")
                
                if response.status == 200:
                    try:
                        data = json.loads(response_text)
                        status = data.get("status")
                        return {
                            "status": "success",
                            "paid": status == "CONFIRMED",
                            "transaction_status": status
                        }
                    except Exception as e:
                        print(f"Ошибка парсинга: {e}")
                        return {"status": "error", "message": "Ошибка парсинга ответа"}
                else:
                    return {"status": "error", "message": f"HTTP {response.status}"}


platega = PlategaAPI()