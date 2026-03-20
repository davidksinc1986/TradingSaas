from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Multi Market Quant Suite v3"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 720
    database_url: str = "sqlite:///./quant_suite.db"
    credentials_key: str = "replace-with-32-url-safe-base64-key"
    static_version: str = "2"

    admin_email: str = "davidksinc@gmail.com"
    admin_name: str = "davidksinc"
    admin_password: str = "M@davi19!"

    telegram_admin_chat_id: str = "6902163541"
    telegram_admin_bot_token: str = "8550578940:AAFRio825HETZLIbSR22wN8j_xD5u9D_rWA"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)


settings = Settings()
