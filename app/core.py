from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Multi Market Quant Suite v3"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 720
    database_url: str = "sqlite:///./quant_suite.db"
    credentials_key: str = "replace-with-32-url-safe-base64-key"

    admin_email: str = "admin@example.com"
    admin_name: str = "Admin"
    admin_password: str = "ChangeMe123!"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)


settings = Settings()
