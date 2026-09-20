from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    news_api_key: str
    guardian_api_key: str
    openai_api_key: str = ""
    db_path: str = "news.db"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
