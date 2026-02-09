from __future__ import annotations

import os
import re
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, status
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

# IMPORTANT: adapte ces imports à ton projet
# - Base : declarative_base()
# - get_db : dépendance qui retourne Session
from db import get_db  # <- si ton fichier s'appelle autrement, change ici
from models import Bar  # <- si ton modèle Bar est dans models.py
from models import PartnerInvite, PartnerMembership, PartnerUser

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = os.getenv("TORE_JWT_SECRET", "dev-secret-change-me")
JWT_ALG = "HS256"
TOKEN_MINUTES = int(os.getenv("TOKEN_MINUTES", "43200"))  # 30 jours


# -----------------------
# SCHEMAS (Pydantic)
# -----------------------

class ManagerSignupIn(BaseModel):
    bar_name: str = Field(min_length=2, max_length=80)
    city: str = Field(min_length=2, max_length=80)
    manager_name: str = Field(min_length=2, max_length=80)
    pin: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")


class LoginIn(BaseModel):
    bar_id: int
    display_name: str = Field(min_length=2, max_length=80)
    pin: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")


class InviteCreateIn(BaseModel):
    role: str = Field(default="bartender")
    max_uses: int = Field(default=25, ge=1, le=1000)
    expires_days: Optional[int] = Field(default=30, ge=1, le=365)


class StaffJoinIn(BaseModel):
    invite_code: str = Field(min_length=4, max_length=16)
    display_name: str = Field(min_length=2, max_length=80)
    pin: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")


class AuthOut(BaseModel):
    token: str
    bar_id: int
    role: str
    display_name: str


class MeOut(BaseModel):
    user_id: int
    bar_id: int
    role: str
    display_name: str


# -----------------------
# HELPERS
# -----------------------

def _normalize_pin(pin) -> str:
    """
    PIN partenaire = exactement 4 chiffres.
    Protège contre l'erreur classique: passer un objet (payload complet)
    au lieu de data.pin -> str(objet) devient très long -> bcrypt plante (72 bytes).
    """
    if pin is None:
        raise ValueError("pin is required")

    # Si quelqu'un passe un modèle / objet avec attribut .pin, on récupère la vraie valeur
    if not isinstance(pin, (str, int)) and hasattr(pin, "pin"):
        pin = getattr(pin, "pin")

    # int -> string
    if isinstance(pin, int):
        pin = f"{pin:04d}"  # 7 -> "0007"
    elif not isinstance(pin, str):
        raise ValueError(f"pin must be a 4-digit string, got {type(pin).__name__}")

    pin = pin.strip()

    if not re.fullmatch(r"\d{4}", pin):
        raise ValueError("pin must be exactly 4 digits")

    # sécurité anti-72 bytes (ne devrait jamais arriver avec 4 digits)
    if len(pin.encode("utf-8")) > 72:
        raise ValueError("pin too long")

    return pin


def _hash_pin(pin) -> str:
    pin_str = _normalize_pin(pin)
    # bcrypt a une limite 72 bytes — ici PIN 4 chiffres donc OK, mais on garde un garde-fou
    if len(pin_str.encode("utf-8")) > 72:
        raise ValueError("PIN too long")
    return pwd_context.hash(pin_str)


def _verify_pin(pin, pin_hash: str) -> bool:
    try:
        pin_str = _normalize_pin(pin)
    except Exception:
        return False
    return pwd_context.verify(pin_str, pin_hash)


def _make_token(user_id: int, bar_id: int, role: str, display_name: str) -> str:
    exp = datetime.utcnow() + timedelta(minutes=TOKEN_MINUTES)
    payload = {
        "sub": str(user_id),
        "bar_id": bar_id,
        "role": role,
        "name": display_name,
        "exp": exp,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def _generate_code(n: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def _generate_partner_code(prefix: str = "BAR", n: int = 8) -> str:
    # Exemple: BAR-1A2B3C4D
    return f"{prefix}-{_generate_code(n)}"


def current_identity(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = int(payload.get("sub"))
    bar_id = int(payload.get("bar_id"))
    role = payload.get("role")
    name = payload.get("name")

    # Vérifie que membership existe encore
    m = (
        db.query(PartnerMembership)
        .filter(PartnerMembership.user_id == user_id, PartnerMembership.bar_id == bar_id)
        .first()
    )
    if not m:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Membership not found")

    return {"user_id": user_id, "bar_id": bar_id, "role": role, "display_name": name}


def require_role(required: str):
    def _dep(identity=Depends(current_identity)):
        if identity["role"] != required:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return identity
    return _dep


# -----------------------
# ROUTES
# -----------------------

@router.post("/manager/signup", response_model=AuthOut)
def manager_signup(data: ManagerSignupIn, db: Session = Depends(get_db)):
    """
    Important: partner_code est unique.
    En cas de signups concurrents, on peut avoir une collision malgré un check pre-insert.
    On rend donc l'opération robuste en retryant si le commit échoue sur IntegrityError.
    """
    try:
        # 1) Crée le bar avec retry si collision sur partner_code (unique)
        bar = None
        max_attempts = 10
        for _ in range(max_attempts):
            try:
                bar = Bar(
                    name=data.bar_name,
                    city=data.city,
                    partner_code=_generate_partner_code(),
                )
                db.add(bar)
                db.commit()
                db.refresh(bar)
                break
            except IntegrityError:
                # collision (ex: unique constraint sur partner_code)
                db.rollback()
                continue

        if bar is None or getattr(bar, "id", None) is None:
            raise HTTPException(
                status_code=500,
                detail="Impossible de générer un partner_code unique, réessaie.",
            )

        # 2) Crée l'utilisateur manager
        user = PartnerUser(display_name=data.manager_name, pin_hash=_hash_pin(data.pin))
        db.add(user)
        db.commit()
        db.refresh(user)

        # 3) Membership manager
        m = PartnerMembership(
            user_id=user.id,
            bar_id=bar.id,
            role="manager",
            display_name=data.manager_name,
        )
        db.add(m)
        db.commit()

        token = _make_token(user.id, bar.id, "manager", data.manager_name)
        return AuthOut(token=token, bar_id=bar.id, role="manager", display_name=data.manager_name)

    except HTTPException:
        db.rollback()
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"DB error: {repr(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Staff join error: {repr(e)}")


@router.post("/login", response_model=AuthOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    m = (
        db.query(PartnerMembership)
        .filter(
            PartnerMembership.bar_id == data.bar_id,
            PartnerMembership.display_name == data.display_name,
        )
        .first()
    )
    if not m:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable pour ce bar")

    user = db.query(PartnerUser).filter(PartnerUser.id == m.user_id).first()
    if not user or not _verify_pin(data.pin, user.pin_hash):
        raise HTTPException(status_code=401, detail="PIN incorrect")

    token = _make_token(user.id, data.bar_id, m.role, m.display_name)
    return AuthOut(token=token, bar_id=data.bar_id, role=m.role, display_name=m.display_name)


@router.post("/invites", response_model=dict)
def create_invite(
    data: InviteCreateIn,
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    code = _generate_code(6)
    # évite collision
    while db.query(PartnerInvite).filter(PartnerInvite.code == code).first():
        code = _generate_code(6)

    expires_at = None
    if data.expires_days:
        expires_at = datetime.utcnow() + timedelta(days=data.expires_days)

    inv = PartnerInvite(
        bar_id=identity["bar_id"],
        code=code,
        role=data.role,
        max_uses=data.max_uses,
        uses_count=0,
        expires_at=expires_at,
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)

    return {
        "code": inv.code,
        "bar_id": inv.bar_id,
        "role": inv.role,
        "max_uses": inv.max_uses,
        "expires_at": inv.expires_at,
    }


@router.post("/staff/join", response_model=AuthOut)
def staff_join(data: StaffJoinIn, db: Session = Depends(get_db)):
    try:
        inv = db.query(PartnerInvite).filter(PartnerInvite.code == data.invite_code).first()
        if not inv:
            raise HTTPException(status_code=400, detail="Code invalide")

        if inv.expires_at and datetime.utcnow() > inv.expires_at:
            raise HTTPException(status_code=400, detail="Code expiré")

        if inv.uses_count >= inv.max_uses:
            raise HTTPException(status_code=400, detail="Code épuisé")

        # Empêche doublon de nom dans le même bar
        existing = (
            db.query(PartnerMembership)
            .filter(
                PartnerMembership.bar_id == inv.bar_id,
                PartnerMembership.display_name == data.display_name,
            )
            .first()
        )
        if existing:
            raise HTTPException(status_code=400, detail="Nom déjà utilisé dans ce bar")

        user = PartnerUser(display_name=data.display_name, pin_hash=_hash_pin(data.pin))
        db.add(user)
        db.commit()
        db.refresh(user)

        m = PartnerMembership(
            user_id=user.id,
            bar_id=inv.bar_id,
            role=inv.role,
            display_name=data.display_name,
        )
        db.add(m)

        inv.uses_count += 1
        db.add(inv)
        db.commit()

        token = _make_token(user.id, inv.bar_id, inv.role, data.display_name)
        return AuthOut(token=token, bar_id=inv.bar_id, role=inv.role, display_name=data.display_name)

    except HTTPException:
        db.rollback()
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"DB error: {repr(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Signup error: {repr(e)}")


@router.get("/me", response_model=MeOut)
def me(identity=Depends(current_identity)):
    return MeOut(
        user_id=identity["user_id"],
        bar_id=identity["bar_id"],
        role=identity["role"],
        display_name=identity["display_name"],
    )
