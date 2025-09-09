"""API client for buyer service communication"""

import asyncio
import json
from typing import Dict, Any, Optional
import aiohttp
from contextlib import asynccontextmanager

from shared.config import settings
from shared.logging_config import setup_logging

logger = setup_logging("api_client")


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
    
    async def get_balance(self) -> Dict[str, Any]:
        """Get current Stars balance"""
        try:
            async with self.session.get(f"{self.base_url}/api/balance") as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    return {"stars_balance": 0, "error": f"HTTP {resp.status}"}
        except Exception as e:
            logger.error(f"Balance fetch failed: {e}")
            return {"stars_balance": 0, "error": str(e)}
    
    async def dry_run(self, ruleset_id: int) -> Dict[str, Any]:
        """Execute dry run"""
        try:
            async with self.session.post(
                f"{self.base_url}/api/dry-run",
                json={"ruleset_id": ruleset_id}
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error_text = await resp.text()
                    return {"success": False, "error": f"HTTP {resp.status}: {error_text}"}
        except Exception as e:
            logger.error(f"Dry run failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def arm_buyer(self, ruleset_id: int, mode: str = "live") -> Dict[str, Any]:
        """Arm the buyer"""
        try:
            async with self.session.post(
                f"{self.base_url}/api/arm",
                json={"ruleset_id": ruleset_id, "mode": mode}
            ) as resp:
                return await resp.json()
        except Exception as e:
            logger.error(f"Arm failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def disarm_buyer(self) -> Dict[str, Any]:
        """Disarm the buyer"""
        try:
            async with self.session.post(f"{self.base_url}/api/disarm") as resp:
                return await resp.json()
        except Exception as e:
            logger.error(f"Disarm failed: {e}")
            return {"success": False, "error": str(e)}
