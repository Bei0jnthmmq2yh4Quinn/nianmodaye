#!/usr/bin/env python3

"""
Core Exception Classes

This module provides essential exception classes for the application.
"""

from typing import Optional

from .enums import ErrorReason


class BaseError(Exception):
    """Base exception class for the application"""

    def __init__(
        self,
        message: str,
        reason: ErrorReason = ErrorReason.UNKNOWN,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.reason = reason
        self.cause = cause

    def is_retryable(self) -> bool:
        """Check if error is retryable based on reason"""
        return self.reason.is_retryable()


class NetworkError(BaseError):
    """Network-related errors"""

    def __init__(self, message: str, reason: ErrorReason = ErrorReason.NETWORK_ERROR, **kwargs):
        super().__init__(message=message, reason=reason, **kwargs)


class ValidationError(BaseError):
    """Input validation errors"""

    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            reason=ErrorReason.BAD_REQUEST,
            **kwargs,
        )
        self.field = field


# Additional exception classes for core functionality
class CoreException(BaseError):
    """Core system exception"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message=message, **kwargs)


class BusinessLogicError(BaseError):
    """Business logic errors"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message=message, **kwargs)


class ProcessingError(BaseError):
    """Processing-related errors"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message=message, **kwargs)


class RetrievalError(BaseError):
    """Data retrieval errors"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message=message, **kwargs)


class ConfigurationError(BaseError):
    """Configuration-related errors"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message=message, **kwargs)
