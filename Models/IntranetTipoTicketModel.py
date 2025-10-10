from Config.db import BASE
from sqlalchemy import Column, String, BigInteger, Text, Integer, DateTime, Index
from datetime import datetime

class IntranetTipoTicketModel(BASE):

    __tablename__= "intranet_tipo_ticket"
    
    id = Column(BigInteger, primary_key=True)
    nombre = Column(String(100))
    estado = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.now)

    def __init__(self, data: dict):
        self.nombre = data['nombre']

    def to_dict(self):
        """Convierte el modelo a diccionario para serialización JSON"""
        return {
            'id': self.id,
            'nombre': self.nombre
        }
