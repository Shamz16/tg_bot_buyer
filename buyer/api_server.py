"""FastAPI server for buyer service API endpoints"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import asyncio
import logging
from datetime import datetime

from buyer.buyer_service import BuyerService
from database.models import RunMode
from shared.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(title="Gift Buyer API", version="1.0.0")

# Global buyer service instance
buyer_service = None


class ArmRequest(BaseModel):
    ruleset_id: int
    mode: str = "live"  # or "dry"


class StatusResponse(BaseModel):
    is_armed: bool
    current_run_id: Optional[int]
    active_ruleset: Optional[str]
    purchases_this_hour: int
    spent_today: int


@app.on_event("startup")
async def startup_event():
    """Initialize buyer service"""
    global buyer_service
    buyer_service = BuyerService()
    await buyer_service.initialize()
    logger.info("Buyer API server started")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown buyer service"""
    if buyer_service:
        await buyer_service.shutdown()
    logger.info("Buyer API server stopped")


@app.get("/status")
async def get_status() -> Dict[str, Any]:
    """Get current system status"""
    if not buyer_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    return {
        "is_armed": buyer_service.state.is_armed,
        "current_run_id": buyer_service.state.current_run_id,
        "active_ruleset": buyer_service.state.active_ruleset.name if buyer_service.state.active_ruleset else None,
        "purchases_this_hour": buyer_service.state.purchases_this_hour,
        "spent_today": buyer_service.state.spent_today,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/balance")
async def get_balance() -> Dict[str, Any]:
    """Get Stars balance"""
    if not buyer_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        balance = await buyer_service.client.get_stars_balance()
        return {
            "stars_balance": balance,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to fetch balance: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch balance")


@app.post("/arm")
async def arm_buyer(request: ArmRequest) -> Dict[str, Any]:
    """Arm the buyer with a ruleset"""
    if not buyer_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        mode = RunMode.LIVE if request.mode == "live" else RunMode.DRY
        result = await buyer_service.arm(request.ruleset_id, mode)
        return result
    except Exception as e:
        logger.error(f"Failed to arm buyer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/disarm")
async def disarm_buyer() -> Dict[str, Any]:
    """Disarm the buyer"""
    if not buyer_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        result = await buyer_service.disarm()
        return result
    except Exception as e:
        logger.error(f"Failed to disarm buyer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/dry_run/{ruleset_id}")
async def dry_run(ruleset_id: int) -> Dict[str, Any]:
    """Execute a dry run with a ruleset"""
    if not buyer_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        result = await buyer_service.dry_run(ruleset_id)
        return result
    except Exception as e:
        logger.error(f"Failed to execute dry run: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
