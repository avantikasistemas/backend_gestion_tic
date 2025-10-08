from typing import Optional
from pydantic import BaseModel

class GuardarOrdenTrabajo(BaseModel):
    activo_id: int = None
    tipo_mantenimiento: int = None
    fecha_programacion: str = None
    tecnico_asignado: int = None
    descripcion: str = None
