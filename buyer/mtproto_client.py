```

### 8. Отсутствует файл shared/utils.py с вспомогательными функциями

```
# shared/utils.py

"""MTProto client for gift discovery and purchasing"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pathlib import Path
from telethon import TelegramClient
from telethon.tl.functions.payments import (
    GetStarGiftsRequest,
    GetPaymentFormRequest,
    SendPaymentFormRequest
)
from telethon.tl.types import (
    InputInvoiceStarGift,
    InputUserEmpty,
    InputUserSelf
)
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.config import settings
from shared.utils import generate_transaction_id, parse_gift_attributes

logger = logging.getLogger(__name__)

class GiftBuyerClient:
    """MTProto client for gift operations"""
    
    def __init__(self):
        # Ensure session directory exists
        session_dir = Path(settings.session_file_path)
        session_dir.mkdir(parents=True, exist_ok=True)
        
        session_file = session_dir / f"{settings.session_name}.session"
        
        self.client = TelegramClient(
            str(session_file),
            settings.api_id,
            settings.api_hash
        )
        
        self.is_authorized = False
    
    async def connect(self):
        """Connect and authorize the client"""
        await self.client.connect()
        
        if not await self.client.is_user_authorized():
            logger.info("Client not authorized, starting authentication...")
            await self.client.send_code_request(settings.phone_number)
            
            # In production, this would be handled via bot UI
            code = input("Enter the code from Telegram: ")
            await self.client.sign_in(settings.phone_number, code)
        
        self.is_authorized = True
        logger.info("MTProto client connected and authorized")
    
    async def get_primary_gifts(self) -> List[Dict[str, Any]]:
        """
        Fetch available primary gift drops
        
        Returns:
            List of gift dictionaries with normalized fields
        """
        try:
            # Get star gifts catalog
            result = await self.client(GetStarGiftsRequest(hash=0))
            
            gifts = []
            if hasattr(result, 'gifts') and result.gifts:
                for gift in result.gifts:
                    # Normalize gift data
                    gift_data = {
                        "id": str(gift.id),
                        "title": getattr(gift, "title", "Unknown Gift"),
                        "slug": getattr(gift, "slug", ""),
                        "stars": gift.stars,
                        "limited": getattr(gift, "limited", False),
                        "total_count": getattr(gift, "availability_total", 0),
                        "sold_out": getattr(gift, "sold_out", False),
                        "first_sale_date": getattr(gift, "first_sale_date", None),
                        "last_sale_date": getattr(gift, "last_sale_date", None),
                        "model": getattr(gift, "title", "Unknown"),
                        "attributes": parse_gift_attributes(getattr(gift, "attributes", {}))
                    }
                    gifts.append(gift_data)
            
            logger.info(f"Fetched {len(gifts)} primary gifts")
            return gifts
            
        except Exception as e:
            logger.error(f"Error fetching primary gifts: {e}")
            return []
    
    async def get_resale_listings(self, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Fetch resale marketplace listings
        
        Args:
            filters: Optional filters (model, backdrop, symbol, price range)
        
        Returns:
            List of resale listing dictionaries
        """
        # Note: As of current Telegram API, resale marketplace is not publicly available
        # This is a placeholder for when the feature becomes available
        logger.info("Fetching resale listings... (placeholder)")
        
        # Return empty list for now
        return []
    
    async def purchase_gift(self, gift: Dict[str, Any], is_resale: bool = False) -> Dict[str, Any]:
        """
        Execute gift purchase
        
        Args:
            gift: Gift data dictionary
            is_resale: Whether this is a resale purchase
        
        Returns:
            Purchase result dictionary
        """
        try:
            logger.info(f"Attempting to purchase gift: {gift.get('title', 'Unknown')}")
            
            # For now, we'll simulate the purchase since the actual API flow is complex
            # and requires handling payment forms and user interaction
            
            # This is a simplified version - in production, you'd implement:
            # 1. Get payment form with InputInvoiceStarGift
            # 2. Handle the payment flow
            # 3. Confirm the purchase
            
            # Mock successful purchase for demonstration
            purchase_result = {
                "success": True,
                "transaction_id": generate_transaction_id(),
                "gift_id": gift["id"],
                "price_stars": gift.get("price_stars", gift.get("stars", 0)),
                "timestamp": datetime.now(timezone.utc),
                "message": "Purchase simulated - implement actual payment flow in production"
            }
            
            logger.info(f"Purchase simulated: {purchase_result['transaction_id']}")
            return purchase_result
            
        except Exception as e:
            logger.error(f"Purchase failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "gift_id": gift.get("id"),
                "timestamp": datetime.now(timezone.utc)
            }
    
    async def get_stars_balance(self) -> int:
        """Get current Stars balance"""
        try:
            # This would use the appropriate API call to get Stars balance
            # For now, return a mock value
            logger.info("Fetching Stars balance...")
            return 15432  # Mock balance
        except Exception as e:
            logger.error(f"Error fetching Stars balance: {e}")
            return 0
    
    async def get_owned_gifts(self) -> List[Dict[str, Any]]:
        """Get list of owned gifts"""
        try:
            # This would fetch the user's owned gifts
            # For now, return empty list
            logger.info("Fetching owned gifts...")
            return []
        except Exception as e:
            logger.error(f"Error fetching owned gifts: {e}")
            return []
    
    async def disconnect(self):
        """Disconnect the client"""
        await self.client.disconnect()
        logger.info("MTProto client disconnected")
