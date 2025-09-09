"""API client for communicating with buyer service"""

import aiohttp
import json
import logging
from typing import Dict, Any, Optional
from shared.config import settings

logger = logging.getLogger(__name__)


class BuyerAPIClient:
    """Client for buyer service API"""
    
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to buyer API"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with self.session.request(method, url, **kwargs) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"API request failed: {response.status} - {error_text}")
                    raise Exception(f"API request failed: {response.status}")
        except Exception as e:
            logger.error(f"Request to {url} failed: {e}")
            raise
    
    async def get_status(self) -> Dict[str, Any]:
        """Get system status"""
        return await self._make_request("GET", "/status")
    
    async def get_balance(self) -> Dict[str, Any]:
        """Get Stars balance"""
        return await self._make_request("GET", "/balance")
    
    async def arm_buyer(self, ruleset_id: int, mode: str = "live") -> Dict[str, Any]:
        """Arm the buyer"""
        data = {"ruleset_id": ruleset_id, "mode": mode}
        return await self._make_request("POST", "/arm", json=data)
    
    async def disarm_buyer(self) -> Dict[str, Any]:
        """Disarm the buyer"""
        return await self._make_request("POST", "/disarm")
    
    async def dry_run(self, ruleset_id: int) -> Dict[str, Any]:
        """Execute dry run"""
        return await self._make_request("POST", f"/dry_run/{ruleset_id}")
