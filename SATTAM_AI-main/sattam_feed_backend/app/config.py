from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MONGO_URI: str
    DB_NAME: str = "sattam_ai"
    APP_ENV: str = "development"
    APP_PORT: int = 8001

    class Config:
        env_file = ".env"

settings = Settings()