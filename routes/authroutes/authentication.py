from fastapi import APIRouter, HTTPException, Request
from services.authapis.register_service import handle_register_user
from services.authapis.login_service import handle_login_user

router = APIRouter()

@router.post("/register")
async def register_user(request: Request):
    try:
        result = await handle_register_user(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.post("/login")
async def login_user(request: Request):
    try:
        result = await handle_login_user(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
