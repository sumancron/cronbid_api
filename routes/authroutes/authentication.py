from fastapi import APIRouter, HTTPException
from services.authapis.register_service import handle_register_user

router = APIRouter()

@router.post("/register")
async def register_user():
    try:
        result = await handle_register_user()
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))