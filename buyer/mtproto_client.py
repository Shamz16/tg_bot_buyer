"""MTProto client for gift discovery and purchasing"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pathlib import Path

from telethon import TelegramClient, events
from telethon.tl.functions.payments import (
    GetStarGiftsRequest,
    GetPaymentFormRequest, 
    SendPaymentFormRequest
)
from telethon.tl.types import InputInvoiceStarGift

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.config import settings

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
            result = await self.client(GetStarGiftsRequest())
            
            gifts = []
            for gift in result.gifts:
                # Normalize gift data
                gift_data = {
                    "id": gift.id,
                    "title": getattr(gift, "title", "Unknown"),
                    "slug": getattr(gift, "slug", ""),
                    "stars": gift.stars,
                    "limited": getattr(gift, "limited", False),
                    "total_count": getattr(gift, "total", 0),
                    "sold_out": getattr(gift, "sold_out", False),
                    "first_sale_date": getattr(gift, "first_sale_date", None),
                    "last_sale_date": getattr(gift, "last_sale_date", None),
                    "model": getattr(gift, "model", ""),
                    "attributes": {
                        "backdrop": getattr(gift, "backdrop", ""),
                        "symbol": getattr(gift, "symbol", ""),
                        "number": getattr(gift, "number", 0),
                        "pattern": getattr(gift, "pattern", "")
                    }
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
        # This would use the appropriate resale API methods
        # For now, returning mock data for demonstration
        logger.info("Fetching resale listings...")
        
        # In production, implement actual resale API calls
        mock_listings = [
            {
                "id": "resale_001",
                "gift_id": "gift_123",
                "title": "Evil Eye #777",
                "model": "Evil Eye",
                "price_stars": 1800,
                "original_price": 2000,
                "seller_id": "seller_456",
                "can_resell_at": datetime.now(timezone.utc),
                "attributes": {
                    "backdrop": "Aurora",
                    "symbol": "Coin",
                    "number": 777
                }
            }
        ]
        
        return mock_listings
    
    async def get_unique_gift_details(self, gift_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific unique gift
        
        Args:
            gift_id: Gift ID or slug
        
        Returns:
            Detailed gift information
        """
        # Implement gift details fetching
        pass
    
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
            
            # Create invoice based on gift type
            if is_resale:
                # For resale, use appropriate invoice type
                # This is simplified - actual implementation would differ
                invoice = InputInvoiceStarGift(gift_id=gift["id"])
            else:
                # For primary drops
                invoice = InputInvoiceStarGift(gift_id=gift["id"])
            
            # Get payment form
            payment_form = await self.client(GetPaymentFormRequest(
                invoice=invoice
            ))
            
            # Process payment with Stars
            result = await self.client(SendPaymentFormRequest(
                form_id=payment_form.form_id,
                invoice=invoice
            ))
            
            purchase_result = {
                "success": True,
                "transaction_id": getattr(result, "transaction_id", ""),
                "gift_id": gift["id"],
                "price_stars": gift.get("price_stars", gift.get("stars", 0)),
                "timestamp": datetime.now(timezone.utc)
            }
            
            logger.info(f"Purchase successful: {purchase_result['transaction_id']}")
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
        # Implement Stars balance fetching
        # This would use the appropriate API call
        return 15432  # Mock balance
    
    async def get_owned_gifts(self) -> List[Dict[str, Any]]:
        """Get list of owned gifts"""
        # Implement owned gifts fetching
        return []
    
    async def disconnect(self):
        """Disconnect the client"""
        await self.client.disconnect()
        logger.info("MTProto client disconnected")