from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "YottaFlex Smart Collections"
    app_env: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    database_url: str = (
        "postgresql+psycopg://collections_user:"
        "collections_dev_password@localhost:5432/collections_db"
    )
    generator_seed: int = 20261022

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()
