"""Circuit breaker pattern for external service calls."""

import time
import logging
from enum import Enum
from functools import wraps
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failures threshold reached, rejecting calls
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""

    pass


class CircuitBreaker:
    """
    Circuit breaker implementation for external services.

    Prevents cascading failures by:
    - Opening circuit after failure threshold
    - Rejecting requests while open
    - Testing service recovery in half-open state
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        name: str = "circuit_breaker",
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before testing recovery
            expected_exception: Exception type that triggers circuit
            name: Circuit breaker name for logging
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name

        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args, **kwargs: Function arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenError: If circuit is open
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker '{self.name}' entering half-open state")
            else:
                raise CircuitBreakerOpenError(f"Circuit breaker '{self.name}' is open")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        return (
            self.last_failure_time is not None
            and time.time() - self.last_failure_time >= self.recovery_timeout
        )

    def _on_success(self):
        """Handle successful call."""
        if self.state == CircuitState.HALF_OPEN:
            logger.info(f"Circuit breaker '{self.name}' recovered, closing circuit")
            self.state = CircuitState.CLOSED

        self.failure_count = 0

    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(
                f"Circuit breaker '{self.name}' opened after "
                f"{self.failure_count} failures"
            )

    def reset(self):
        """Manually reset circuit breaker."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        logger.info(f"Circuit breaker '{self.name}' manually reset")


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: type = Exception,
    name: Optional[str] = None,
):
    """
    Decorator for circuit breaker pattern.

    Usage:
        @circuit_breaker(failure_threshold=3, recovery_timeout=30)
        def call_external_service():
            # Service call that might fail
            pass
    """

    def decorator(func: Callable) -> Callable:
        breaker_name = name or func.__name__
        breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
            name=breaker_name,
        )

        @wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)

        # Attach breaker for manual control
        wrapper.circuit_breaker = breaker

        return wrapper

    return decorator


# Example usage with retry logic
def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
):
    """
    Retry decorator with exponential backoff.

    Usage:
        @retry_with_backoff(max_retries=3)
        @circuit_breaker(failure_threshold=5)
        def call_jira_api():
            # API call
            pass
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            delay = base_delay

            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except CircuitBreakerOpenError:
                    # Don't retry if circuit is open
                    raise
                except Exception as e:
                    retries += 1
                    if retries >= max_retries:
                        logger.error(
                            f"Function '{func.__name__}' failed after "
                            f"{max_retries} retries: {e}"
                        )
                        raise

                    logger.warning(
                        f"Function '{func.__name__}' failed (attempt {retries}), "
                        f"retrying in {delay}s: {e}"
                    )
                    time.sleep(delay)
                    delay = min(delay * exponential_base, max_delay)

        return wrapper

    return decorator
