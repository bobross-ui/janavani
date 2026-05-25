from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import create_db_and_tables
from app.routes.admin import router as admin_router
from app.routes.clusters import router as clusters_router
from app.routes.evals import router as evals_router
from app.routes.grievances import router as grievances_router
from app.routes.health import router as health_router
from app.routes.tts import router as tts_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(title="Janavani API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(tts_router)
app.include_router(grievances_router)
app.include_router(clusters_router)
app.include_router(admin_router)
app.include_router(evals_router)
