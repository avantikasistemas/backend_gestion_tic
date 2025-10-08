from typing import Optional
from pydantic import BaseModel

class ConsultarActivo(BaseModel):
    codigo: str = None
