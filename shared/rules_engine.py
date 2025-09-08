"""Rules engine for evaluating gift purchase criteria"""

import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum


class EvaluationResult(Enum):
    MATCH = "match"
    REJECT = "reject"
    SKIP = "skip"


@dataclass
class RuleEvaluation:
    """Result of rule evaluation with explanation"""
    result: EvaluationResult
    reasons: List[str] = field(default_factory=list)
    matched_criteria: List[str] = field(default_factory=list)
    rejected_criteria: List[str] = field(default_factory=list)
    
    def add_match(self, criterion: str, reason: str):
        self.matched_criteria.append(criterion)
        self.reasons.append(f"✓ {reason}")
    
    def add_reject(self, criterion: str, reason: str):
        self.rejected_criteria.append(criterion)
        self.reasons.append(f"✗ {reason}")
        self.result = EvaluationResult.REJECT


class RulesEngine:
    """Evaluates gifts against configurable rules"""
    
    def __init__(self, rules: Dict[str, Any]):
        self.rules = rules
        self._validate_rules()
    
    def _validate_rules(self):
        """Validate rule structure"""
        # Add validation logic here
        pass
    
    def evaluate(self, gift: Dict[str, Any], is_resale: bool = False) -> RuleEvaluation:
        """
        Evaluate a gift against rules
        
        Args:
            gift: Gift data dictionary
            is_resale: Whether this is a resale listing
        
        Returns:
            RuleEvaluation with result and explanations
        """
        eval_result = RuleEvaluation(result=EvaluationResult.MATCH)
        
        # Check source
        if "source" in self.rules:
            allowed_sources = self.rules["source"]
            source = "resale" if is_resale else "primary"
            if source not in allowed_sources:
                eval_result.add_reject("source", f"Source '{source}' not in allowed: {allowed_sources}")
                return eval_result
            eval_result.add_match("source", f"Source '{source}' is allowed")
        
        # Check price
        if "price" in self.rules:
            price_rules = self.rules["price"]
            gift_price = gift.get("price_stars", gift.get("stars", 0))
            
            if "max_stars" in price_rules and gift_price > price_rules["max_stars"]:
                eval_result.add_reject("price", f"Price {gift_price} exceeds max {price_rules['max_stars']}")
                return eval_result
            
            if "min_stars" in price_rules and gift_price < price_rules["min_stars"]:
                eval_result.add_reject("price", f"Price {gift_price} below min {price_rules['min_stars']}")
                return eval_result
            
            eval_result.add_match("price", f"Price {gift_price} within range")
        
        # Check rarity attributes
        if "rarity" in self.rules:
            rarity_rules = self.rules["rarity"]
            gift_attrs = gift.get("attributes", {})
            
            # Check symbol
            if "symbols_allowlist" in rarity_rules:
                symbol = gift_attrs.get("symbol")
                if symbol not in rarity_rules["symbols_allowlist"]:
                    eval_result.add_reject("rarity.symbol", 
                        f"Symbol '{symbol}' not in allowlist: {rarity_rules['symbols_allowlist']}")
                    return eval_result
                eval_result.add_match("rarity.symbol", f"Symbol '{symbol}' is allowed")
            
            # Check backdrop
            if "backdrop_allowlist" in rarity_rules:
                backdrop = gift_attrs.get("backdrop")
                if backdrop not in rarity_rules["backdrop_allowlist"]:
                    eval_result.add_reject("rarity.backdrop",
                        f"Backdrop '{backdrop}' not in allowlist: {rarity_rules['backdrop_allowlist']}")
                    return eval_result
                eval_result.add_match("rarity.backdrop", f"Backdrop '{backdrop}' is allowed")
            
            # Check number
            if "numbers_allowlist" in rarity_rules:
                number = gift_attrs.get("number")
                if number not in rarity_rules["numbers_allowlist"]:
                    eval_result.add_reject("rarity.number",
                        f"Number '{number}' not in allowlist: {rarity_rules['numbers_allowlist']}")
                    return eval_result
                eval_result.add_match("rarity.number", f"Number '{number}' is allowed")
        
        # Check models
        if "models_allowlist" in self.rules:
            model = gift.get("model", gift.get("title"))
            if model not in self.rules["models_allowlist"]:
                eval_result.add_reject("model", 
                    f"Model '{model}' not in allowlist: {self.rules['models_allowlist']}")
                return eval_result
            eval_result.add_match("model", f"Model '{model}' is allowed")
        
        if "models_blocklist" in self.rules:
            model = gift.get("model", gift.get("title"))
            if model in self.rules["models_blocklist"]:
                eval_result.add_reject("model", f"Model '{model}' is blocked")
                return eval_result
        
        # Check sale window (for primary drops)
        if "sale_window" in self.rules and not is_resale:
            window = self.rules["sale_window"]
            now = datetime.now(timezone.utc)
            
            if "utc_start" in window:
                start = datetime.fromisoformat(window["utc_start"].replace("Z", "+00:00"))
                if now < start:
                    eval_result.add_reject("sale_window", 
                        f"Current time {now.isoformat()} before window start {start.isoformat()}")
                    return eval_result
            
            if "utc_end" in window:
                end = datetime.fromisoformat(window["utc_end"].replace("Z", "+00:00"))
                if now > end:
                    eval_result.add_reject("sale_window",
                        f"Current time {now.isoformat()} after window end {end.isoformat()}")
                    return eval_result
            
            eval_result.add_match("sale_window", "Within sale window")
        
        # Check resale-specific rules
        if is_resale and "resale" in self.rules:
            resale_rules = self.rules["resale"]
            
            if "max_price_stars" in resale_rules:
                price = gift.get("price_stars", 0)
                if price > resale_rules["max_price_stars"]:
                    eval_result.add_reject("resale.price",
                        f"Resale price {price} exceeds max {resale_rules['max_price_stars']}")
                    return eval_result
                eval_result.add_match("resale.price", f"Resale price {price} acceptable")
            
            if "min_discount_pct" in resale_rules:
                original = gift.get("original_price", 0)
                current = gift.get("price_stars", 0)
                if original > 0:
                    discount_pct = ((original - current) / original) * 100
                    if discount_pct < resale_rules["min_discount_pct"]:
                        eval_result.add_reject("resale.discount",
                            f"Discount {discount_pct:.1f}% below min {resale_rules['min_discount_pct']}%")
                        return eval_result
                    eval_result.add_match("resale.discount", f"Discount {discount_pct:.1f}% acceptable")
        
        return eval_result
    
    def check_safety_limits(self, current_stats: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Check if purchase would violate safety limits
        
        Args:
            current_stats: Current spending/purchase statistics
        
        Returns:
            (is_safe, rejection_reason)
        """
        if "safety" not in self.rules:
            return True, None
        
        safety = self.rules["safety"]
        
        # Check daily spend limit
        if "max_spend_per_day" in safety:
            if current_stats.get("spent_today", 0) >= safety["max_spend_per_day"]:
                return False, f"Daily spend limit reached: {safety['max_spend_per_day']} Stars"
        
        # Check hourly purchase limit
        if "max_purchases_per_hour" in safety:
            if current_stats.get("purchases_this_hour", 0) >= safety["max_purchases_per_hour"]:
                return False, f"Hourly purchase limit reached: {safety['max_purchases_per_hour']}"
        
        # Check cooldown
        if "cooldown_ms_between_purchases" in safety:
            last_purchase = current_stats.get("last_purchase_ms", 0)
            now_ms = int(datetime.now().timestamp() * 1000)
            elapsed = now_ms - last_purchase
            cooldown = safety["cooldown_ms_between_purchases"]
            if elapsed < cooldown:
                return False, f"Cooldown active: {cooldown - elapsed}ms remaining"
        
        return True, None


def create_example_rules() -> Dict[str, Any]:
    """Create example rules for testing"""
    return {
        "source": ["primary", "resale"],
        "price": {
            "max_stars": 2500,
            "min_stars": 100
        },
        "rarity": {
            "symbols_allowlist": ["Coin", "Crown", "Star"],
            "backdrop_allowlist": ["Aurora", "Nebula", "Galaxy"],
            "numbers_allowlist": [1, 7, 77, 777, 1337]
        },
        "models_allowlist": ["Evil Eye", "Space Cat", "Lucky Charm"],
        "sale_window": {
            "utc_start": "2025-09-08T17:59:50Z",
            "utc_end": "2025-09-08T20:00:00Z"
        },
        "resale": {
            "max_price_stars": 1800,
            "min_discount_pct": 10
        },
        "safety": {
            "max_purchases_per_hour": 3,
            "max_spend_per_day": 6000,
            "cooldown_ms_between_purchases": 800
        }
    }