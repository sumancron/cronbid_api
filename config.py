from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    db_host: str
    db_port: int = 3306
    db_user: str
    db_password: str
    db_name: str
    secret_key: str
    api_key: str
    
    
    # Secret key for signing JWTs. Keep this truly secret!
    jwt_secret_key: str


    model_config = {
        "env_file": ".env"
    }

settings = Settings()
