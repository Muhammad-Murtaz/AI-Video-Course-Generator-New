from pydantic import BaseModel, EmailStr, validator
from typing import Optional


class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None


class UserCreate(UserBase):
    """For traditional email/password signup"""
    password: str

    @validator("password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserCreateClerk(UserBase):
    """For Clerk OAuth users (Google, Facebook, etc.)"""
    clerk_id: str
    username: str
    # No password required!


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None


class UserResponse(UserBase):
    id: int
    credits: int

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ChangePassword(BaseModel):
    current_password: str
    new_password: str

    @validator("new_password")
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v