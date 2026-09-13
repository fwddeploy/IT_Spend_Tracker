"""Users, roles and sessions — plain and small.

* Passwords: bcrypt (passlib).
* Session: a signed cookie `it_session` (itsdangerous, 30 days) carrying the user id.
* Scripts / tests may instead send `X-Access-Key: $APP_ACCESS_KEY` (if that env var is set); such a caller
  is a "script principal" that may open every company as owner.
* `current_user`      -> FastAPI dependency, 401 when nobody is logged in.
* `require_company(role)` -> dependency for company-scoped routes: 404 if the company doesn't exist,
  403 if the user is not a member with at least `role`.
"""
from __future__ import annotations
import os
import secrets
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models as m
from app.db import get_db

COOKIE = "it_session"
SESSION_DAYS = 30
ROLES = ("viewer", "accountant", "owner")
_RANK = {r: i for i, r in enumerate(ROLES)}

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _secret() -> str:
    s = os.environ.get("SECRET_KEY")
    if not s:
        import logging
        logging.getLogger("ittracker").warning("SECRET_KEY not set — using a per-process random key (logins won't survive a restart)")
        s = os.environ["SECRET_KEY"] = secrets.token_urlsafe(32)
    return s


def hash_password(pw: str) -> str:
    return _pwd.hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return _pwd.verify(pw, hashed)
    except ValueError:
        return False


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_secret(), salt="it-session")


def set_session(response: Response, user_id: int):
    token = _serializer().dumps({"uid": user_id})
    response.set_cookie(COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax",
                        secure=os.environ.get("COOKIE_SECURE", "0") == "1")


def clear_session(response: Response):
    response.delete_cookie(COOKIE)


@dataclass
class Principal:
    """Who is calling. `user` is None for the access-key script principal."""
    user: m.User | None
    is_script: bool = False

    @property
    def label(self) -> str:
        return self.user.email if self.user else "script"

    @property
    def id(self) -> int | None:
        return self.user.id if self.user else None


def _user_from_cookie(request: Request, db: Session) -> m.User | None:
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    try:
        data = _serializer().loads(token, max_age=SESSION_DAYS * 86400)
    except (BadSignature, SignatureExpired):
        return None
    return db.get(m.User, int(data.get("uid", 0)))


def access_key_ok(request: Request) -> bool:
    expected = os.environ.get("APP_ACCESS_KEY", "")
    return bool(expected) and secrets.compare_digest(request.headers.get("X-Access-Key", ""), expected)


def current_user(request: Request, db: Session = Depends(get_db)) -> Principal:
    u = _user_from_cookie(request, db)
    if u:
        return Principal(user=u)
    if access_key_ok(request):
        return Principal(user=None, is_script=True)
    raise HTTPException(401, "Please log in")


def optional_user(request: Request, db: Session = Depends(get_db)) -> Principal | None:
    try:
        return current_user(request, db)
    except HTTPException:
        return None


def membership(db: Session, user_id: int, company_id: int) -> m.Membership | None:
    return db.execute(select(m.Membership).where(m.Membership.user_id == user_id, m.Membership.company_id == company_id)).scalar_one_or_none()


def role_for(db: Session, p: Principal, company_id: int) -> str | None:
    if p.is_script:
        return "owner"
    mem = membership(db, p.user.id, company_id)
    return mem.role if mem else None


def require_company(role: str = "viewer"):
    """Dependency factory: `company: m.Company = Depends(require_company("accountant"))`."""
    need = _RANK[role]

    def dep(company_id: int, p: Principal = Depends(current_user), db: Session = Depends(get_db)) -> m.Company:
        c = db.get(m.Company, company_id)
        if not c:
            raise HTTPException(404, "Company not found")
        have = role_for(db, p, company_id)
        if have is None:
            raise HTTPException(403, "You don't have access to this company")
        if _RANK[have] < need:
            raise HTTPException(403, f"This needs the {role} role (you are {have})")
        return c
    return dep


def companies_for(db: Session, p: Principal) -> list[tuple[m.Company, str]]:
    if p.is_script:
        return [(c, "owner") for c in db.execute(select(m.Company).order_by(m.Company.id)).scalars()]
    rows = db.execute(select(m.Company, m.Membership.role).join(m.Membership, m.Membership.company_id == m.Company.id)
                      .where(m.Membership.user_id == p.user.id).order_by(m.Company.id)).all()
    return [(c, r) for c, r in rows]


def temp_password() -> str:
    return secrets.token_urlsafe(8)
