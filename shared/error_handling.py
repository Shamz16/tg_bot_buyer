"""Error handling and retry utilities"""

import asyncio
import logging
from typing import Callable, Any, Optional, Type
from functools import wraps
import random

logger = logging.getLogger(__name__)

class RetryableError(Exception):
    """Error that should be retried"""
    pass

class PermanentError(Exception):
    """Error that should not be retried"""
    pass

def with_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple = (RetryableError, asyncio.TimeoutError)
):
    """Decorator for adding retry logic to async functions"""
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt == max_attempts - 1:
                        break
                    
                    wait_time = delay * (backoff ** attempt)
                    if jitter:
                        wait_time *= (0.5 + random.random() * 0.5)
                    
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {e}. Retrying in {wait_time:.2f}s"
                    )
                    await asyncio.sleep(wait_time)
                except Exception as e:
                    logger.error(f"Non-retryable error: {e}")
                    raise
            
            raise last_exception
        
        return wrapper
    return decorator

class ErrorHandler:
    """Centralized error handling"""
    
    @staticmethod
    def categorize_purchase_error(error: Exception) -> str:
        """Categorize purchase errors for appropriate handling"""
        error_str = str(error).lower()
        
        if any(x in error_str for x in ["sold out", "not available", "expired"]):
            return "sold_out"
        elif any(x in error_str for x in ["price changed", "different price"]):
            return "price_changed"
        elif any(x in error_str for x in ["insufficient balance", "not enough stars"]):
            return "insufficient_balance"
        elif any(x in error_str for x in ["verification needed", "2fa", "confirm"]):
            return "verification_needed"
        elif any(x in error_str for x in ["rate limit", "too many requests"]):
            return "rate_limited"
        elif any(x in error_str for x in ["network", "connection", "timeout"]):
            return "network_error"
        else:
            return "unknown_error"