from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings

router = APIRouter(tags=["health"])

SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/health")
async def health(settings: SettingsDep) -> dict[str, str]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }
