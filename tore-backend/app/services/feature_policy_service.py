"""Deployment gates for capabilities requiring external approval."""

import os

from fastapi import HTTPException


def value_predictions_enabled() -> bool:
    return os.getenv("TORE_VALUE_PREDICTIONS_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def require_value_predictions_enabled() -> None:
    if not value_predictions_enabled():
        raise HTTPException(status_code=403, detail={
            "reason": "feature_disabled",
            "code": "VALUE_PREDICTIONS_DISABLED",
            "message": "Les participations avec Credits sont désactivées.",
        })
