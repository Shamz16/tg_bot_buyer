"""HTTP API server for buyer service control"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import asyncio
import uvicorn
from buyer.buyer_service import BuyerService

app = FastAPI(title="Gift Buyer API")
buyer_service: Optional[BuyerService] = None

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

@app.on_event("shutdown")
async def shutdown():
    if buyer_service:
        await buyer_service.shutdown()

@app.post("/arm")
async def arm_buyer(request: ArmRequest) -> Dict[str, Any]:
    if not buyer_service:
        raise HTTPException(status_code=500, detail="Buyer service not initialized")
    return await buyer_service.arm(request.ruleset_id, request.mode)

@app.post("/disarm")
async def disarm_buyer() -> Dict[str, Any]:
    if not buyer_service:
        raise HTTPException(status_code=500, detail="Buyer service not initialized")
    return await buyer_service.disarm()

@app.post("/dry_run")
async def dry_run(request: DryRunRequest) -> Dict[str, Any]:
    if not buyer_service:
        raise HTTPException(status_code=500, detail="Buyer service not initialized")
    return await buyer_service.dry_run(request.ruleset_id)

@app.get("/status")
async def get_status() -> Dict[str, Any]:
    if not buyer_service:
        raise HTTPException(status_code=500, detail="Buyer service not initialized")
    return {
        "is_armed": buyer_service.state.is_armed,
        "current_run_id": buyer_service.state.current_run_id,
        "purchases_this_hour": buyer_service.state.purchases_this_hour,
        "spent_today": buyer_service.state.spent_today
    }

@app.get("/balance")
async def get_balance() -> Dict[str, Any]:
    if not buyer_service:
        raise HTTPException(status_code=500, detail="Buyer service not initialized")
    balance = await buyer_service.client.get_stars_balance()
    return {"stars_balance": balance}

def run_api_server():
    uvicorn.run(app, host="0.0.0.0", port=8001)

if __name__ == "__main__":
    run_api_server()