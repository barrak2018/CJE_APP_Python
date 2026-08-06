from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from security import create_access_token, verify_credentials

router = APIRouter(
    prefix="/token",
    tags=["Autenticación"]
)


@router.post("/", response_model=Dict[str, str])
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if not verify_credentials(form_data.username, form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(form_data.username)
    return {"access_token": access_token, "token_type": "bearer"}
