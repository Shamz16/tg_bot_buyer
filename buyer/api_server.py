"""FastAPI server for buyer service control"""

import asyncio
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from buyer.buyer_service import BuyerService
from shared.config import settings
from shared.logging_config import setup_logging

logger = setup_logging("buyer_api")

# Global buyer service instance
buyer_service: BuyerService = None

app = FastAPI(title="Gift Buyer API", version="1.0.0")


class ArmRequest(BaseModel):
    ruleset_id: int
    mode: str = "live"


class DryRunRequest(BaseModel):
    ruleset_id: int


@app.on_event("startup")
async def startup():
    global buyer_service
    buyer_service = BuyerService()
    await buyer_service.initialize()
    logger.info("Buyer API server started")


@app.on_event("shutdown")
async def shutdown():
    if buyer_service:
        await buyer_service.shutdown()
    logger.info("Buyer API server shutdown")


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "buyer_api"}


@app.get("/api/balance")
async def get_balance():
    """Get Stars balance"""
    try:
        balance = await buyer_service.client.get_stars_balance()
        return {"stars_balance": balance}
    except Exception as e:
        logger.error(f"Balance fetch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/arm")
async def arm_buyer(request: ArmRequest):
    """Arm the buyer with a ruleset"""
    try:
        from database.models import RunMode
        mode = RunMode.LIVE if request.mode == "live" else RunMode.DRY
        result = await buyer_service.arm(request.ruleset_id, mode)
        return result
    except Exception as e:
        logger.error(f"Arm failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/disarm")
async def disarm_buyer():
    """Disarm the buyer"""
    try:
        result = await buyer_service.disarm()
        return result
    except Exception as e:
        logger.error(f"Disarm failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/dry-run")
async def dry_run(request: DryRunRequest):
    """Execute dry run"""
    try:
        result = await buyer_service.dry_run(request.ruleset_id)
        return result
    except Exception as e:
        logger.error(f"Dry run failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status")
async def get_status():
    """Get buyer service status"""
    return {
        "is_armed": buyer_service.state.is_armed,
        "current_run_id": buyer_service.state.current_run_id,
        "active_ruleset": buyer_service.state.active_ruleset.name if buyer_service.state.active_ruleset else None,
        "purchases_this_hour": buyer_service.state.purchases_this_hour,
        "spent_today": buyer_service.state.spent_today
    }


if __name__ == "__main__":
    uvicorn.run(
        "buyer.api_server:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.is_development
    )
