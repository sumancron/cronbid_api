from fastapi import Header, HTTPException
from config import settings

async def verify_api_key(x_api_key: str = Header(default=None)):
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=400, detail="NOT FOUND")

async def double_key(x_api_key: str = Header(default=None)):
    key_one = "f87f754c7ccdfb93f5b115ec0d5f4090"
    key_two = "9797dhfuehfg47yrf74f4fg74gf74gf47"

    if x_api_key == key_one:
        return 1
    elif x_api_key == key_two:
        return 2
    else:
        # If it matches neither, raise an error
        raise HTTPException(status_code=403, detail="NOT FOUND")