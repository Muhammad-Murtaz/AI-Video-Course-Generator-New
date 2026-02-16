from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from app.db.model import User
from app.schemas.user import UserCreate, UserCreateClerk
from app.core.security import get_password_hash
from typing import Optional


class UserService:
    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def get_user_by_clerk_id(db: Session, clerk_id: str) -> Optional[User]:
        return db.query(User).filter(User.clerk_id == clerk_id).first()

    @staticmethod
    def create_user(db: Session, user_data: UserCreate) -> User:
        if UserService.get_user_by_email(db, user_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )
        db_user = User(
            email=user_data.email,
            name=user_data.name,
            hashed_password=get_password_hash(user_data.password),
            credits=10,
        )
        try:
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            return db_user
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User creation failed")

    @staticmethod
    def create_clerk_user(db: Session, user_data: UserCreateClerk) -> User:
        # Return existing by clerk_id
        existing = UserService.get_user_by_clerk_id(db, user_data.clerk_id)
        if existing:
            return existing

        # Link clerk_id to existing email account
        existing = UserService.get_user_by_email(db, user_data.email)
        if existing:
            existing.clerk_id = user_data.clerk_id
            db.commit()
            db.refresh(existing)
            return existing

        # Create new OAuth user
        db_user = User(
            email=user_data.email,
            name=user_data.username,
            clerk_id=user_data.clerk_id,
            hashed_password=None,
            credits=10,
        )
        try:
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            return db_user
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User creation failed")