from Config.db import BASE
from sqlalchemy import Column, String, BigInteger, Text, Integer, DateTime, DECIMAL, Date
from datetime import datetime

class IntranetGraphTokenModel(BASE):

    __tablename__= "intranet_graph_token"
    
    id = Column(BigInteger, primary_key=True)
    token = Column(Text)
    fecha_vencimiento = Column(DateTime)
    estado = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.now())

    def __init__(self, data: dict):
        self.token = data['token']
        self.fecha_vencimiento = data['fecha_vencimiento']

    def to_dict(self):
        """Convierte el modelo a diccionario para serialización JSON"""
        return {
            'id': self.id,
            'token': self.token,
            'fecha_vencimiento': str(self.fecha_vencimiento.isoformat()) if self.fecha_vencimiento else None,
            'estado': self.estado,
            'created_at': str(self.created_at.isoformat()) if self.created_at else None
        }
