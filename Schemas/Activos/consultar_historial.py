from typing import Optional
from pydantic import BaseModel

class ConsultarHistorial(BaseModel):
    codigo: str = None
