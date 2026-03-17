from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from sqlalchemy import text

router = APIRouter()


# ADD USER (ADMIN)
@router.post("/admin/add-user")
def add_user(phone: str, db: Session = Depends(get_db)):

    check = db.execute(
        text("SELECT * FROM authorized_users WHERE phone=:phone"),
        {"phone": phone}
    ).fetchone()

    if check:
        return {"success": False, "message": "Phone already exists"}

    db.execute(
        text("INSERT INTO authorized_users (phone) VALUES (:phone)"),
        {"phone": phone}
    )

    db.commit()

    return {"success": True, "message": "User added"}


# GET USERS (ADMIN PANEL)
@router.get("/admin/users")
def get_users(db: Session = Depends(get_db)):

    result = db.execute(
        text("SELECT * FROM authorized_users ORDER BY created_at DESC")
    )

    users = result.fetchall()

    return [
        {
            "id": str(row.id),
            "phone": row.phone,
            "created_at": row.created_at
        }
        for row in users
    ]


# VERIFY PHONE (LAUNCHER)
@router.post("/verify-phone")
def verify_phone(phone: str, db: Session = Depends(get_db)):

    user = db.execute(
        text("SELECT * FROM authorized_users WHERE phone=:phone"),
        {"phone": phone}
    ).fetchone()

    if user:
        return {"authorized": True}

    return {"authorized": False}
