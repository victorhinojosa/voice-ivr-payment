from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from core.database import close_pool
from core.exceptions import register_exception_handlers
from customers.router import router as customers_router
from calls.router import router as calls_router
from conversation.router import router as conversation_router

env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_pool()
    print("Database connection pool closed")


def create_app() -> FastAPI:
    app = FastAPI(title="Voice IVR PoC", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify your frontend domain
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(customers_router)
    app.include_router(calls_router)
    app.include_router(conversation_router)

    @app.get("/")
    async def root():
        return {"status": "ok", "service": "Voice IVR"}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)