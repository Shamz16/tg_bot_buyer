"""API client for communication between bot and buyer service"""

import asyncio
import json
from typing import Dict, Any, Optional
import aiohttp
from shared.config import settings

class BuyerAPIClient:
    """Client for communicating with buyer service"""
    
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def arm_buyer(self, ruleset_id: int, mode: str = "live") -> Dict[str, Any]:
        """Arm the buyer with specified ruleset"""
        async with self.session.post(
            f"{self.base_url}/arm",
            json={"ruleset_id": ruleset_id, "mode": mode}
        ) as resp:
            return await resp.json()
    
    async def disarm_buyer(self) -> Dict[str, Any]:
        """Disarm the buyer"""
        async with self.session.post(f"{self.base_url}/disarm") as resp:
            return await resp.json()
    
    async def dry_run(self, ruleset_id: int) -> Dict[str, Any]:
        """Execute dry run"""
        async with self.session.post(
            f"{self.base_url}/dry_run",
            json={"ruleset_id": ruleset_id}
        ) as resp:
            return await resp.json()
    
    async def get_status(self) -> Dict[str, Any]:
        """Get buyer service status"""
        async with self.session.get(f"{self.base_url}/status") as resp:
            return await resp.json()
    
    async def get_balance(self) -> Dict[str, Any]:
        """Get Stars balance"""
        async with self.session.get(f"{self.base_url}/balance") as resp:
            return await resp.json()