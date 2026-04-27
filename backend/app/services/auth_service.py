from __future__ import annotations

from fastapi import HTTPException

from backend.app.schemas.research import AuthResponse, SignInRequest, SignUpRequest
from backend.app.services.research_store import ResearchStore


class AuthService:
    def __init__(self, store: ResearchStore) -> None:
        self.store = store

    def sign_up(self, request: SignUpRequest) -> AuthResponse:
        display_name = (request.display_name or "").strip() or request.email.split("@", 1)[0]
        try:
            user = self.store.create_user(request.email, request.password, display_name)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Unable to create user. Email may already exist.") from exc
        token = self.store.issue_token(user.user_id)
        return AuthResponse(token=token, user=user)

    def sign_in(self, request: SignInRequest) -> AuthResponse:
        user = self.store.authenticate(request.email, request.password)
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid credentials.")
        token = self.store.issue_token(user.user_id)
        return AuthResponse(token=token, user=user)

    def sign_out(self, token: str) -> None:
        self.store.revoke_token(token)
