from fastapi import APIRouter, Depends, Header, HTTPException

from backend.app.core.dependencies import get_auth_service, get_current_user
from backend.app.schemas.research import AuthResponse, SignInRequest, SignUpRequest, UserProfile
from backend.app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse)
def signup(request: SignUpRequest, service: AuthService = Depends(get_auth_service)) -> AuthResponse:
    return service.sign_up(request)


@router.post("/signin", response_model=AuthResponse)
def signin(request: SignInRequest, service: AuthService = Depends(get_auth_service)) -> AuthResponse:
    return service.sign_in(request)


@router.post("/signout")
def signout(
    authorization: str | None = Header(default=None),
    auth=Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    service.sign_out(auth["token"])
    return {"status": "ok"}


@router.get("/me", response_model=UserProfile)
def me(auth=Depends(get_current_user)) -> UserProfile:
    return auth["user"]
