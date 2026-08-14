import os
from dataclasses import dataclass


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    use_mock_gpu_data: bool
    frontend_origins: tuple[str, ...]
    database_path: str
    admin_secret_key: str
    admin_access_minutes: int
    admin_refresh_days: int
    initial_admin_email: str
    initial_admin_password: str
    initial_admin_name: str


def get_settings() -> Settings:
    origins = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    return Settings(
        use_mock_gpu_data=_as_bool(os.getenv("USE_MOCK_GPU_DATA")),
        frontend_origins=tuple(origin.strip() for origin in origins.split(",") if origin.strip()),
        database_path=os.getenv("DATABASE_PATH", "./gpu_monitoring.db"),
        admin_secret_key=os.getenv("ADMIN_SECRET_KEY", "change-me-in-production"),
        admin_access_minutes=int(os.getenv("ADMIN_ACCESS_MINUTES", "30")),
        admin_refresh_days=int(os.getenv("ADMIN_REFRESH_DAYS", "7")),
        initial_admin_email=os.getenv("INITIAL_ADMIN_EMAIL", "admin@example.com"),
        initial_admin_password=os.getenv("INITIAL_ADMIN_PASSWORD", "Admin1234!"),
        initial_admin_name=os.getenv("INITIAL_ADMIN_NAME", "System Administrator"),
    )
