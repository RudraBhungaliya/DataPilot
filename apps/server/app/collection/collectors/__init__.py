"""
Collectors Module.
"""

from app.collection.collectors.base import BaseCollector, CollectorException, CaptchaChallengeDetected
from app.collection.collectors.http import HTTPCollector
from app.collection.collectors.api import APICollector
from app.collection.collectors.browser import BrowserCollector
from app.collection.collectors.zyte import ZyteAdapter

__all__ = [
    "BaseCollector",
    "CollectorException",
    "CaptchaChallengeDetected",
    "HTTPCollector",
    "APICollector",
    "BrowserCollector",
    "ZyteAdapter",
]
