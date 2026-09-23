"""Google OIDC bearer-token boundary for the User API."""

from __future__ import annotations

from dataclasses import dataclass
import os
import time
from typing import Any, Callable, Mapping, Protocol
from uuid import UUID

from fastapi import HTTPException, Request, status


GOOGLE_ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})


class UserResolver(Protocol):
    def resolve_user(self, google_sub: str, email: str) -> UUID: ...


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: UUID
    google_sub: str
    email: str


@dataclass(frozen=True)
class AuthenticatedAdmin:
    google_sub: str
    email: str


class GoogleUserAuthenticator:
    def __init__(
        self,
        audience: str,
        resolver: UserResolver,
        *,
        allowed_emails: frozenset[str] = frozenset(),
        verifier: Callable[[str, str], Mapping[str, Any]] | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.audience = audience.strip()
        self.resolver = resolver
        self.allowed_emails = frozenset(value.strip().lower() for value in allowed_emails)
        self.verifier = verifier or self._verify_google_token
        self.clock = clock

    def __call__(self, request: Request) -> AuthenticatedUser:
        if not self.audience:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "authentication unavailable")
        scheme, _, token = request.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
        try:
            claims = dict(self.verifier(token, self.audience))
            issuer = str(claims.get("iss", ""))
            audience = claims.get("aud")
            audiences = {audience} if isinstance(audience, str) else set(audience or ())
            subject = str(claims.get("sub", "")).strip()
            email = str(claims.get("email", "")).strip().lower()
            if issuer not in GOOGLE_ISSUERS or self.audience not in audiences:
                raise ValueError("wrong token issuer or audience")
            if int(claims.get("exp", 0)) <= int(self.clock()):
                raise ValueError("expired token")
            if not subject or claims.get("email_verified") is not True:
                raise ValueError("unverified account")
        except Exception as error:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid Google credential") from error
        if self.allowed_emails and email not in self.allowed_emails:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "account is not allowed")
        return AuthenticatedUser(self.resolver.resolve_user(subject, email), subject, email)

    @staticmethod
    def _verify_google_token(token: str, audience: str) -> Mapping[str, Any]:
        from google.auth.transport import requests
        from google.oauth2 import id_token

        return id_token.verify_oauth2_token(token, requests.Request(), audience)


class GoogleAdminAuthenticator:
    """Separate Google bearer-token boundary for Admin and legacy Core routes."""

    def __init__(self, audience: str, allowed_emails: frozenset[str], *,
                 verifier: Callable[[str, str], Mapping[str, Any]] | None = None,
                 clock: Callable[[], float] = time.time) -> None:
        self.audience = audience.strip()
        self.allowed_emails = frozenset(value.strip().lower() for value in allowed_emails if value.strip())
        self.verifier = verifier or GoogleUserAuthenticator._verify_google_token
        self.clock = clock

    def __call__(self, request: Request) -> AuthenticatedAdmin:
        if not self.audience or not self.allowed_emails:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "admin authentication unavailable")
        scheme, _, token = request.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "admin authentication required")
        try:
            claims = dict(self.verifier(token, self.audience))
            raw_audience = claims.get("aud")
            audiences = {raw_audience} if isinstance(raw_audience, str) else set(raw_audience or ())
            subject = str(claims.get("sub", "")).strip()
            email = str(claims.get("email", "")).strip().lower()
            if str(claims.get("iss", "")) not in GOOGLE_ISSUERS or self.audience not in audiences:
                raise ValueError("wrong token issuer or audience")
            if int(claims.get("exp", 0)) <= int(self.clock()) or claims.get("email_verified") is not True:
                raise ValueError("expired or unverified identity")
            if not subject or not email:
                raise ValueError("missing admin identity")
        except Exception as error:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid admin credential") from error
        if email not in self.allowed_emails:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "admin account is not allowed")
        return AuthenticatedAdmin(subject, email)


def allowed_user_emails() -> frozenset[str]:
    return frozenset(value.strip() for value in os.getenv("GOOGLE_USER_ALLOWED_EMAILS", "").split(",") if value.strip())


def allowed_admin_emails() -> frozenset[str]:
    return frozenset(value.strip() for value in os.getenv("GOOGLE_ADMIN_ALLOWED_EMAILS", "").split(",") if value.strip())
