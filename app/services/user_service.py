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
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def create_user(db: Session, user_data: UserCreate) -> User:
        """Traditional email/password signup"""
        existing_user = UserService.get_user_by_email(db=db, email=user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )

        hashed_password = get_password_hash(user_data.password)
        db_user = User(
            email=user_data.email,
            name=user_data.name,
            hashed_password=hashed_password,
            credits=10,
        )

        try:
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            return db_user
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="User creation failed"
            )

    @staticmethod
    def create_clerk_user(db: Session, user_data: UserCreateClerk) -> User:
        """Clerk OAuth signup (Google, Facebook, etc.)"""
        # Check by clerk_id first
        existing_user = UserService.get_user_by_clerk_id(db=db, clerk_id=user_data.clerk_id)
        if existing_user:
            return existing_user  # User already exists, return them
        
        # Check by email
        existing_user = UserService.get_user_by_email(db=db, email=user_data.email)
        if existing_user:
            print("User found ",existing_user)
            # Update with clerk_id
            existing_user.clerk_id = user_data.clerk_id
            db.commit()
            db.refresh(existing_user)
            return existing_user

        # Create new user (no password needed)
        db_user = User(
            email=user_data.email,
            name=user_data.username,
            clerk_id=user_data.clerk_id,
            hashed_password=None,  # No password for OAuth users
            credits=10,
        )

        try:
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            return db_user
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="User creation failed"
            )