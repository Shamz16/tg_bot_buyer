"""Main buyer service with scheduler and purchase pipeline"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.config import settings
from shared.rules_engine import RulesEngine
from database.models import (
    Base, Ruleset, Run, RunMode, RunStatus,
    Purchase, PurchaseStatus, GiftSource,
    OperationEvent, EventType, SpendTracking
)
from buyer.mtproto_client import GiftBuyerClient

logger = logging.getLogger(__name__)

# Database setup
engine = create_async_engine(settings.database_url)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@dataclass
class BuyerState:
    """Current state of the buyer service"""
    is_armed: bool = False
    current_run_id: Optional[int] = None
    active_ruleset: Optional[Ruleset] = None
    rules_engine: Optional[RulesEngine] = None
    purchases_this_hour: int = 0
    spent_today: int = 0
    last_purchase_ms: int = 0


class BuyerService:
    """Main buyer service orchestrator"""
    
    def __init__(self):
        self.client = GiftBuyerClient()
        self.scheduler = AsyncIOScheduler()
        self.state = BuyerState()
        self._purchase_lock = asyncio.Lock()
    
    async def initialize(self):
        """Initialize the service"""
        # Connect MTProto client
        await self.client.connect()
        
        # Initialize database
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Setup scheduler jobs
        self._setup_scheduler()
        
        logger.info("Buyer service initialized")
    
    def _setup_scheduler(self):
        """Setup scheduled jobs"""
        # Primary discovery job
        self.scheduler.add_job(
            self._scan_primary_gifts,
            IntervalTrigger(seconds=settings.default_polling_interval),
            id="scan_primary",
            replace_existing=True
        )
        
        # Resale discovery job
        self.scheduler.add_job(
            self._scan_resale_listings,
            IntervalTrigger(seconds=settings.default_polling_interval * 2),
            id="scan_resale",
            replace_existing=True
        )
        
        # Stats reset job (hourly)
        self.scheduler.add_job(
            self._reset_hourly_stats,
            IntervalTrigger(hours=1),
            id="reset_hourly",
            replace_existing=True
        )
        
        # Stats reset job (daily)
        self.scheduler.add_job(
            self._reset_daily_stats,
            IntervalTrigger(days=1),
            id="reset_daily",
            replace_existing=True
        )
    
    async def arm(self, ruleset_id: int, mode: RunMode = RunMode.LIVE) -> Dict[str, Any]:
        """
        Arm the buyer with a specific ruleset
        
        Args:
            ruleset_id: ID of the ruleset to use
            mode: Run mode (dry or live)
        
        Returns:
            Result dictionary
        """
        if self.state.is_armed:
            return {"success": False, "error": "Buyer already armed"}
        
        async with async_session() as session:
            # Load ruleset
            ruleset = await session.get(Ruleset, ruleset_id)
            if not ruleset or not ruleset.active:
                return {"success": False, "error": "Invalid or inactive ruleset"}
            
            # Create new run
            new_run = Run(
                ruleset_id=ruleset_id,
                mode=mode.value,
                status=RunStatus.RUNNING.value
            )
            session.add(new_run)
            await session.commit()
            
            self.state.current_run_id = new_run.id
            self.state.active_ruleset = ruleset
            self.state.rules_engine = RulesEngine(ruleset.rules)
            self.state.is_armed = True
        
        # Start scheduler
        self.scheduler.start()
        
        logger.info(f"Buyer armed with ruleset {ruleset_id} in {mode} mode")
        return {"success": True, "run_id": new_run.id}
    
    async def disarm(self) -> Dict[str, Any]:
        """Disarm the buyer and stop operations"""
        if not self.state.is_armed:
            return {"success": False, "error": "Buyer not armed"}
        
        # Stop scheduler
        self.scheduler.shutdown(wait=False)
        
        # Update run status
        async with async_session() as session:
            run = await session.get(Run, self.state.current_run_id)
            if run:
                run.status = RunStatus.COMPLETED.value
                run.ended_at = datetime.now(timezone.utc)
                await session.commit()
        
        # Reset state
        self.state.is_armed = False
        self.state.current_run_id = None
        self.state.active_ruleset = None
        self.state.rules_engine = None
        
        logger.info("Buyer disarmed")
        return {"success": True}
    
    async def _scan_primary_gifts(self):
        """Scan primary gift drops"""
        if not self.state.is_armed:
            return
        
        try:
            gifts = await self.client.get_primary_gifts()
            
            for gift in gifts:
                # Skip sold out gifts
                if gift.get("sold_out", False):
                    continue
                
                await self._evaluate_and_purchase(gift, is_resale=False)
                
        except Exception as e:
            logger.error(f"Error scanning primary gifts: {e}")
    
    async def _scan_resale_listings(self):
        """Scan resale marketplace"""
        if not self.state.is_armed:
            return
        
        try:
            listings = await self.client.get_resale_listings()
            
            for listing in listings:
                await self._evaluate_and_purchase(listing, is_resale=True)
                
        except Exception as e:
            logger.error(f"Error scanning resale listings: {e}")
    
    async def _evaluate_and_purchase(self, gift: Dict[str, Any], is_resale: bool):
        """
        Evaluate a gift against rules and purchase if matched
        
        Args:
            gift: Gift data
            is_resale: Whether this is a resale listing
        """
        if not self.state.rules_engine:
            return
        
        # Evaluate against rules
        evaluation = self.state.rules_engine.evaluate(gift, is_resale)
        
        # Log evaluation event
        await self._log_event(
            EventType.EVALUATION,
            {
                "gift_id": gift.get("id"),
                "title": gift.get("title"),
                "result": evaluation.result.value,
                "reasons": evaluation.reasons
            }
        )
        
        # If not matched, skip
        if evaluation.result != "match":
            return
        
        # Check safety limits
        current_stats = {
            "spent_today": self.state.spent_today,
            "purchases_this_hour": self.state.purchases_this_hour,
            "last_purchase_ms": self.state.last_purchase_ms
        }
        
        is_safe, reason = self.state.rules_engine.check_safety_limits(current_stats)
        
        if not is_safe:
            await self._log_event(
                EventType.SAFETY_BLOCK,
                {"gift_id": gift.get("id"), "reason": reason}
            )
            logger.warning(f"Safety block: {reason}")
            return
        
        # Execute purchase
        await self._execute_purchase(gift, is_resale)
    
    async def _execute_purchase(self, gift: Dict[str, Any], is_resale: bool):
        """Execute the actual purchase"""
        async with self._purchase_lock:
            # Pre-flight check - refetch gift to ensure it's still available
            # In production, would refetch here
            
            # Log purchase attempt
            await self._log_event(
                EventType.PURCHASE_ATTEMPT,
                {"gift_id": gift.get("id"), "price_stars": gift.get("price_stars", gift.get("stars"))}
            )
            
            # Execute purchase
            result = await self.client.purchase_gift(gift, is_resale)
            
            # Record purchase in database
            async with async_session() as session:
                purchase = Purchase(
                    run_id=self.state.current_run_id,
                    gift_id=gift.get("id"),
                    gift_slug=gift.get("slug"),
                    gift_title=gift.get("title"),
                    source=GiftSource.RESALE.value if is_resale else GiftSource.PRIMARY.value,
                    price_stars=gift.get("price_stars", gift.get("stars", 0)),
                    seller_id=gift.get("seller_id"),
                    transaction_id=result.get("transaction_id"),
                    status=PurchaseStatus.SUCCESS.value if result["success"] else PurchaseStatus.FAILED.value,
                    error_message=result.get("error"),
                    rarity_attributes=gift.get("attributes", {})
                )
                session.add(purchase)
                
                # Update run stats
                if self.state.current_run_id:
                    run = await session.get(Run, self.state.current_run_id)
                    if run and result["success"]:
                        run.total_purchased += 1
                        run.total_spent_stars += purchase.price_stars
                
                await session.commit()
            
            # Update state
            if result["success"]:
                self.state.purchases_this_hour += 1
                self.state.spent_today += gift.get("price_stars", gift.get("stars", 0))
                self.state.last_purchase_ms = int(datetime.now().timestamp() * 1000)
                
                await self._log_event(
                    EventType.PURCHASE_SUCCESS,
                    {
                        "gift_id": gift.get("id"),
                        "transaction_id": result.get("transaction_id"),
                        "price_stars": gift.get("price_stars", gift.get("stars"))
                    }
                )
                
                logger.info(f"Purchase successful: {gift.get('title')} for {gift.get('price_stars', gift.get('stars'))} Stars")
            else:
                await self._log_event(
                    EventType.PURCHASE_FAIL,
                    {
                        "gift_id": gift.get("id"),
                        "error": result.get("error")
                    }
                )
                
                logger.error(f"Purchase failed: {result.get('error')}")
    
    async def _log_event(self, event_type: EventType, payload: Dict[str, Any]):
        """Log an operation event"""
        if not self.state.current_run_id:
            return
        
        async with async_session() as session:
            event = OperationEvent(
                run_id=self.state.current_run_id,
                event_type=event_type.value,
                payload=payload
            )
            session.add(event)
            await session.commit()
    
    async def _reset_hourly_stats(self):
        """Reset hourly statistics"""
        self.state.purchases_this_hour = 0
        logger.info("Hourly stats reset")
    
    async def _reset_daily_stats(self):
        """Reset daily statistics"""
        self.state.spent_today = 0
        logger.info("Daily stats reset")
    
    async def dry_run(self, ruleset_id: int) -> Dict[str, Any]:
        """
        Execute a dry run to test rules
        
        Args:
            ruleset_id: Ruleset to test
        
        Returns:
            Dry run results
        """
        async with async_session() as session:
            ruleset = await session.get(Ruleset, ruleset_id)
            if not ruleset:
                return {"success": False, "error": "Invalid ruleset"}
        
        rules_engine = RulesEngine(ruleset.rules)
        
        # Fetch current gifts
        primary_gifts = await self.client.get_primary_gifts()
        resale_listings = await self.client.get_resale_listings()
        
        matches = []
        total_cost = 0
        
        # Evaluate primary gifts
        for gift in primary_gifts:
            if gift.get("sold_out", False):
                continue
            
            evaluation = rules_engine.evaluate(gift, is_resale=False)
            if evaluation.result == "match":
                matches.append({
                    "gift": gift,
                    "source": "primary",
                    "reasons": evaluation.reasons
                })
                total_cost += gift.get("stars", 0)
        
        # Evaluate resale listings
        for listing in resale_listings:
            evaluation = rules_engine.evaluate(listing, is_resale=True)
            if evaluation.result == "match":
                matches.append({
                    "gift": listing,
                    "source": "resale",
                    "reasons": evaluation.reasons
                })
                total_cost += listing.get("price_stars", 0)
        
        return {
            "success": True,
            "total_evaluated": len(primary_gifts) + len(resale_listings),
            "matches": matches,
            "total_cost": total_cost
        }
    
    async def shutdown(self):
        """Shutdown the service"""
        await self.disarm()
        await self.client.disconnect()
        logger.info("Buyer service shut down")


async def main():
    """Main entry point for buyer service"""
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    service = BuyerService()
    
    try:
        await service.initialize()
        
        # Keep service running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await service.shutdown()


if __name__ == "__main__":
    asyncio.run(main())