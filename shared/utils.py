"""Utility functions for the application"""
import json
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone
import hashlib
import uuid

logger = logging.getLogger(__name__)

def generate_transaction_id() -> str:
    """Generate a unique transaction ID"""
    return f"tx_{uuid.uuid4().hex[:16]}"

def format_stars(amount: int) -> str:
    """Format Stars amount with comma separators"""
    return f"{amount:,}"

def safe_json_loads(json_str: str) -> Optional[Dict[str, Any]]:
    """Safely load JSON string"""
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        logger.error(f"Failed to parse JSON: {json_str}")
        return None

def parse_gift_attributes(attributes: Dict[str, Any]) -> Dict[str, Any]:
    """Parse and normalize gift attributes"""
    result = {
        "backdrop": attributes.get("backdrop", ""),
        "symbol": attributes.get("symbol", ""),
        "number": attributes.get("number", 0),
        "pattern": attributes.get("pattern", "")
    }
    return result

def calculate_discount_pct(original_price: int, current_price: int) -> float:
    """Calculate discount percentage"""
    if original_price <= 0:
        return 0.0
    return ((original_price - current_price) / original_price) * 100

def is_within_time_window(
    start_time: Optional[str], 
    end_time: Optional[str],
    current_time: Optional[datetime] = None
) -> bool:
    """Check if current time is within the specified window"""
    if not start_time and not end_time:
        return True
    
    if current_time is None:
        current_time = datetime.now(timezone.utc)
    
    if start_time:
        start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        if current_time < start:
            return False
    
    if end_time:
        end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        if current_time > end:
            return False
    
    return True

def hash_gift_data(gift_data: Dict[str, Any]) -> str:
    """Create a hash of gift data for deduplication"""
    # Create a consistent string representation
    data_str = json.dumps(gift_data, sort_keys=True)
    return hashlib.md5(data_str.encode()).hexdigest()