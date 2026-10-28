from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UsuarioCreate(BaseModel):
    nombre: str
    correo: EmailStr
    pais: str
    genero: str
    dispositivo: str

class UsuarioUpdate(BaseModel):
    nombre: Optional[str] = None
    pais: Optional[str] = None
    genero: Optional[str] = None
    dispositivo: Optional[str] = None