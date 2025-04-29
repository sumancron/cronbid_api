from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    db_host: str
    db_port: int = 3306
    db_user: str
    db_password: str
    db_name: str
    secret_key: str

    model_config = {
        "env_file": ".env"
    }

settings = Settings()
