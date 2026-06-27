from pydantic_settings import BaseSettings
from pydantic import computed_field
from functools import lru_cache
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.parent

class Settings(BaseSettings):
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    redis_url: str = "redis://localhost:6379"

    anthropic_api_key: str = ""

    app_name: str = "Incident Whisperer"
    debug: bool = False

    @computed_field
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}"
            f"/{self.postgres_db}"
        )
    
    class Config:
        env_file = str(ROOT_DIR / ".env")
        env_file_encoding = "utf-8"

@lru_cache()
# everytime some part of our app needs config, it calls get_settings
def get_settings() -> Settings:
    return Settings()