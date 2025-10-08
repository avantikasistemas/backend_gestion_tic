from typing import Optional
from pydantic import BaseModel

class GuardarActivo(BaseModel):
    codigo: str = None
    descripcion: str = None
    modelo: Optional[str] = None
    serie: Optional[str] = None
    marca: Optional[str] = None
    estado: int = None
    vida_util: Optional[int] = None
    proveedor: int = None
    tercero: int = None
    docto_compra: str = None
    fecha_compra: str = None
    caracteristicas: Optional[str] = None
    sede: int = None
    centro: int = None
    grupo: str = None
    macroproceso_encargado: int = None
    macroproceso: int = None
    costo_compra: float = None
