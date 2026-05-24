from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import create_db_and_tables
from app.routes.admin import router as admin_router
from app.routes.clusters import router as clusters_router
from app.routes.grievances import router as grievances_router
from app.routes.health import router as health_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(title="Janavani API", lifespan=lifespan)
app.include_router(health_router)
app.include_router(grievances_router)
app.include_router(clusters_router)
app.include_router(admin_router)
