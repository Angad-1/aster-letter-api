import logging

logging.basicConfig(level=logging.WARNING, force=True)

# Silence noisy libraries
# for name in ["fontTools", "fontTools.subset", "fontTools.ttLib", "weasyprint"]:
#     logger = logging.getLogger(name)
#     logger.setLevel(logging.CRITICAL)
#     logger.propagate = False
#     logger.handlers.clear()
#     logger.addHandler(logging.NullHandler())
import os
import asyncio
from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from sqlmodel import SQLModel
from sqlalchemy import event
from core.db import engine
from utilities.utils import MyHTTPException,hash_password,file_stem
from core.db import engine
from models.models import Users
from routes import api_router
from services.letterServices import worker, PDF_WORKERS


load_dotenv()
ENV = os.getenv("ENV", "development")

origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()]


@event.listens_for(engine.sync_engine, "connect")
def register_sqlite_functions(dbapi_connection, connection_record):
    dbapi_connection.create_function("file_stem", 1, file_stem)

# =========================
# LIFESPAN
# =========================
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
            # Db Init
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        # ---------- INSERT DEFAULT USER IF EMPTY ----------
        async with AsyncSession(engine) as session:
            result = await session.exec(select(Users))
            user = result.first()

            if not user:
                admin_user = Users(
                    first_name="Super",
                    last_name="Admin",
                    username="superadmin",
                    pwd=hash_password("superadmin"),
                    dsg="System Administrator",
                    role="s",
                    gender="m",
                )

                session.add(admin_user)
                await session.commit()
        # Start background workers
        workers = []
        for _ in range(PDF_WORKERS):
            task = asyncio.create_task(worker())
            workers.append(task)

        app.state.worker_tasks = workers
        yield
    finally:
        # ---------- SHUTDOWN ----------
        for task in getattr(app.state, "worker_tasks", []):
            task.cancel()

        # Allow graceful cancellation
        await asyncio.gather(
            *app.state.worker_tasks,
            return_exceptions=True
        )
        # Dispose engine even if create_all() failed
        await engine.dispose()


# =========================
# APP
# =========================

app = FastAPI(
    title="Aster Letter Generation Backend",
    debug=False,
    # docs_url="/docs" if ENV != "production" else None,
    redoc_url=None,
    lifespan=lifespan
)


app.mount("/assets", StaticFiles(directory="assets",check_dir=False), name="assets")
app.mount("/uploads", StaticFiles(directory="uploads",check_dir=False), name="uploads")

def custom_exception_handler(request: Request, exc: MyHTTPException) -> JSONResponse:
    content = exc.content.model_dump() if hasattr(exc.content, "model_dump") else exc.content
    return JSONResponse(
        status_code=exc.status_code,
        content=content
    )

app.add_exception_handler(MyHTTPException, custom_exception_handler)

# =========================
# CORS
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://192.168.1.37:90",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# ROUTES
# =========================
app.include_router(api_router)

