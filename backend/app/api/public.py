from fastapi import APIRouter

from ..config import get_settings
from ..schemas import PublicConfigResponse


router = APIRouter(prefix="/public", tags=["public"])


@router.get("/config", response_model=PublicConfigResponse)
def public_config():
    settings = get_settings()
    return PublicConfigResponse(
        app_name=settings.app_name,
        app_short_name=settings.app_short_name,
        app_icon=settings.app_icon,
        app_tagline=settings.app_tagline,
        app_description=settings.app_description,
        assistant_name=settings.assistant_name,
        knowledge_label=settings.knowledge_label,
        profile_label=settings.profile_label,
        welcome_title=settings.welcome_title,
        welcome_description=settings.welcome_description,
        disclaimer=settings.app_disclaimer,
        enable_turtle_module=settings.enable_turtle_module,
        ai_provider=settings.ai_provider,
        ai_configured=bool(settings.ai_api_key),
    )
