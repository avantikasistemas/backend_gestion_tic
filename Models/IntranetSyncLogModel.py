from Config.db import BASE
from sqlalchemy import Column, String, BigInteger, Text, Integer, DateTime, Index
from datetime import datetime

class IntranetSyncLogModel(BASE):

    __tablename__= "intranet_sync_log"
    
    id = Column(BigInteger, primary_key=True)
    tipo_sync = Column(String(50))  # 'incremental', 'completo'
    fecha_inicio = Column(DateTime)
    fecha_fin = Column(DateTime)
    correos_nuevos = Column(Integer, default=0)
    correos_actualizados = Column(Integer, default=0)
    correos_eliminados = Column(Integer, default=0)
    estado = Column(Integer, default=1)
    mensaje_error = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    
    # Índices para mejorar performance
    __table_args__ = (
        Index('idx_tipo_sync', 'tipo_sync'),
        Index('idx_estado', 'estado'),
        Index('idx_fecha_inicio', 'fecha_inicio'),
    )

    def __init__(self, data: dict):
        self.tipo_sync = data.get('tipo_sync', 'incremental')
        self.fecha_inicio = data.get('fecha_inicio', datetime.now())
        self.fecha_fin = data.get('fecha_fin')
        self.correos_nuevos = data.get('correos_nuevos', 0)
        self.correos_actualizados = data.get('correos_actualizados', 0)
        self.correos_eliminados = data.get('correos_eliminados', 0)
        self.estado = data.get('estado', 1)
        self.mensaje_error = data.get('mensaje_error')

    def to_dict(self):
        """Convierte el modelo a diccionario para serialización JSON"""
        return {
            'id': self.id,
            'tipo_sync': self.tipo_sync,
            'fecha_inicio': self.fecha_inicio.isoformat() if self.fecha_inicio else None,
            'fecha_fin': self.fecha_fin.isoformat() if self.fecha_fin else None,
            'correos_nuevos': self.correos_nuevos,
            'correos_actualizados': self.correos_actualizados,
            'correos_eliminados': self.correos_eliminados,
            'estado': self.estado,
            'mensaje_error': self.mensaje_error,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
