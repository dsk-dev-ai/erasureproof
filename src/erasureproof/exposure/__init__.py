"""Authorized, passive exposure discovery.

Collectors only read public sources and explicit URLs supplied by the operator.
Nothing here bypasses authentication, exploits a target or downloads breach
dumps. Use it on your own identities or with documented authorization.
"""

from .models import ExposureHit, ExposureReport, ExposureTarget
from .service import ExposureService

__all__ = ["ExposureHit", "ExposureReport", "ExposureService", "ExposureTarget"]
