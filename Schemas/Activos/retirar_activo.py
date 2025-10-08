from typing import Optional
from pydantic import BaseModel

class RetirarActivo(BaseModel):
    codigo: str = None
