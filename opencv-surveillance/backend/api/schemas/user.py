# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
from pydantic import BaseModel
from pydantic import ConfigDict


class UserBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    username: str
    email: str | None = None


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int
    is_active: bool