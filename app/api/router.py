from fastapi import APIRouter

from app.api.routes import chat, health, personas, speech

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(personas.router)
api_router.include_router(chat.router)
api_router.include_router(speech.router)
