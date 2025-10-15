from Config.db import BASE
from sqlalchemy import Column, String, BigInteger, Text, Integer, DateTime, Date, Index
from datetime import datetime

class IntranetCorreosMicrosoftModel(BASE):

    __tablename__= "intranet_correos_microsoft"
    
    id = Column(BigInteger, primary_key=True)
    message_id = Column(String(255), unique=True, nullable=False)  # ID único de Microsoft
    conversation_id = Column(String(255))  # ID de conversación de Microsoft Graph
    subject = Column(String(500))
    from_email = Column(String(255))
    from_name = Column(String(255))
    received_date = Column(DateTime)
    body_preview = Column(Text)
    body_content = Column(Text)
    estado = Column(Integer, default=1)
    hash_contenido = Column(String(64))  # Para detectar cambios
    attachments_count = Column(Integer, default=0)
    has_attachments = Column(Integer, default=0)  # 0=No, 1=Sí
    ticket = Column(Integer, default=0)
    asignado = Column(BigInteger, default=None)
    prioridad = Column(BigInteger, default=0)
    tipo_soporte = Column(BigInteger, default=0)
    tipo_ticket = Column(BigInteger, default=0)
    macroproceso = Column(BigInteger, default=0)
    fecha_vencimiento = Column(Date, default=None)
    sla = Column(Integer, default=0)
    activo = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Índices para mejorar performance
    __table_args__ = (
        Index('idx_message_id', 'message_id'),
        Index('idx_estado', 'estado'),
        Index('idx_received_date', 'received_date'),
        Index('idx_from_email', 'from_email'),
        Index('idx_conversation_id', 'conversation_id'),
    )

    def __init__(self, data: dict):
        self.message_id = data.get('message_id')
        self.conversation_id = data.get('conversation_id')
        self.subject = data.get('subject', '')
        self.from_email = data.get('from_email', '')
        self.from_name = data.get('from_name', '')
        self.received_date = data.get('received_date')
        self.body_preview = data.get('body_preview', '')
        self.body_content = data.get('body_content', '')
        self.estado = data.get('estado', 1)
        self.ticket = data.get('ticket', 0)
        self.asignado = data.get('asignado', None)
        self.hash_contenido = data.get('hash_contenido', '')
        self.attachments_count = data.get('attachments_count', 0)
        self.has_attachments = data.get('has_attachments', 0)
        self.prioridad = data.get('prioridad', None)
        self.tipo_soporte = data.get('tipo_soporte', None)
        self.tipo_ticket = data.get('tipo_ticket', None)
        self.macroproceso = data.get('macroproceso', None)
        self.fecha_vencimiento = data.get('fecha_vencimiento', None)
        self.sla = data.get('sla', None)

    def to_dict(self):
        """Convierte el modelo a diccionario para serialización JSON"""
        return {
            'id': self.id,
            'message_id': self.message_id,
            'conversation_id': self.conversation_id,
            'subject': self.subject,
            'from_email': self.from_email,
            'from_name': self.from_name,
            'received_date': self.received_date.isoformat() if self.received_date else None,
            'body_preview': self.body_preview,
            'body_content': self.body_content,
            'estado': self.estado,
            'hash_contenido': self.hash_contenido,
            'attachments_count': self.attachments_count,
            'has_attachments': self.has_attachments,
            'activo': self.activo,
            'asignado': self.asignado,
            'ticket': self.ticket,
            'prioridad': self.prioridad,
            'tipo_soporte': self.tipo_soporte,
            'tipo_ticket': self.tipo_ticket,
            'macroproceso': self.macroproceso,
            'fecha_vencimiento': self.fecha_vencimiento,
            'sla': self.sla,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def to_frontend_format(self):
        """Convierte al formato que espera el frontend actual"""
        return {
            'id': self.message_id,  # El frontend usa esto como ID
            'ticket_id': self.id,  # Número puro para uso interno
            'ticket_id_display': f"TCK-{self.id:04d}" if self.ticket == 1 else None,  # Formato display para UI
            'subject': self.subject,
            'from_name': f"{self.from_name}" if self.from_name else '',
            'from_email': f"{self.from_email}" if self.from_email else '',
            'receivedAt': self.received_date.date().isoformat() if self.received_date else None,
            'preview': self.body_preview,
            'body': self.body_content,
            'estado': self.estado,
            'ticket': self.ticket,
            'asignado': self.asignado,
            'prioridad': self.prioridad,
            'tipo_soporte': self.tipo_soporte,
            'tipo_ticket': self.tipo_ticket,
            'macroproceso': self.macroproceso,
            'fecha_vencimiento': self.fecha_vencimiento.isoformat() if self.fecha_vencimiento else None,
            'sla': self.sla,
            'hasAttachments': bool(self.has_attachments),
            'attachmentsCount': self.attachments_count,
            'created_at': self.created_at.date().isoformat() if self.created_at else None,
            'updated_at': self.updated_at.date().isoformat() if self.updated_at else None,
        }
