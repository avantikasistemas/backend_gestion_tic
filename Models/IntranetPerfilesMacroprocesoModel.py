from Config.db import BASE
from sqlalchemy import Column, String, BigInteger, Text, Integer, DateTime, Index
from datetime import datetime

class IntranetPerfilesMacroprocesoModel(BASE):

    __tablename__= "intranet_perfiles_macroproceso"
    
    id = Column(BigInteger, primary_key=True)
    codigo = Column(String(3))
    nombre = Column(String(100))
    nombre_carpeta = Column(Text)
    estado = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.now)

    def __init__(self, data: dict):
        self.codigo = data['codigo']
        self.nombre = data['nombre']
        self.nombre_carpeta = data['nombre_carpeta']
    
    def to_dict(self):
        """Convierte el modelo a diccionario para serialización JSON"""
        return {
            'id': self.id,
            'nombre': self.nombre
        }
