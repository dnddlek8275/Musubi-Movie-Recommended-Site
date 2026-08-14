from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .admin_dependencies import database
from .admin_routes import create_admin_router
from .gpu_service import GpuNotFoundError, GpuService, GpuUnavailableError, now_seoul
from .schemas import GpuListResponse, GpuResponse, HealthResponse, ProcessListResponse

settings = get_settings()
gpu_service = GpuService(settings.use_mock_gpu_data)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    database.initialize(settings)
    gpu_service.initialize()
    yield
    gpu_service.shutdown()


app = FastAPI(title="NVIDIA GPU Monitoring API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.frontend_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(create_admin_router(gpu_service))


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(status_code=exc.status_code, content={"state": "error", "message": detail})


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(state="success", message="GPU monitoring server is running")


@app.get("/api/gpus", response_model=GpuListResponse)
def list_gpus() -> GpuListResponse:
    try:
        return GpuListResponse(state="success", timestamp=now_seoul(), data=gpu_service.list_gpus())
    except GpuUnavailableError:
        return GpuListResponse(
            state="unavailable",
            timestamp=now_seoul(),
            message="NVIDIA GPU or NVML is not available",
            data=[],
        )


@app.get("/api/gpus/{gpu_index}", response_model=GpuResponse)
def get_gpu(gpu_index: int) -> GpuResponse:
    try:
        return GpuResponse(state="success", timestamp=now_seoul(), data=gpu_service.get_gpu(gpu_index))
    except GpuNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"GPU index {gpu_index} was not found") from exc
    except GpuUnavailableError as exc:
        raise HTTPException(status_code=503, detail="NVIDIA GPU or NVML is not available") from exc


@app.get("/api/gpus/{gpu_index}/processes", response_model=ProcessListResponse)
def get_gpu_processes(gpu_index: int) -> ProcessListResponse:
    try:
        return ProcessListResponse(
            state="success", timestamp=now_seoul(), data=gpu_service.get_processes(gpu_index)
        )
    except GpuNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"GPU index {gpu_index} was not found") from exc
    except GpuUnavailableError as exc:
        raise HTTPException(status_code=503, detail="NVIDIA GPU or NVML is not available") from exc
