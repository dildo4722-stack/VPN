from handlers.start import router as start_router
from handlers.menu import router as menu_router
from handlers.devices import router as devices_router
from handlers.profile import router as profile_router
from handlers.tariffs import router as tariffs_router
from handlers.admin import router as admin_router

__all__ = [
    "start_router",
    "menu_router", 
    "devices_router",
    "profile_router",
    "tariffs_router",
    "admin_router"
]