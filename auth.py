from fastapi import Header, HTTPException
from config import settings

async def verify_api_key(x_api_key: str = Header(default=None)):
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="API KEY IS NOT VALID")
