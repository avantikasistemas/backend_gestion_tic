from fastapi import APIRouter, Request, Depends, Query
from sqlalchemy.orm import Session
from Class.Tickets import Tickets
from Utils.decorator import http_decorator
from Config.db import get_db

tickets_router = APIRouter()

@tickets_router.post('/convertir_correo_ticket', tags=["TICKETS"], response_model=dict)
@http_decorator
def convertir_correo_ticket(request: Request, db: Session = Depends(get_db)):
    """Convierte un correo a ticket marcándolo con ticket = 1"""
    data = getattr(request.state, "json_data", {})
    response = Tickets(db).convertir_correo_ticket(data)
    return response

@tickets_router.post('/obtener_tickets_correos', tags=["TICKETS"], response_model=dict)
@http_decorator
def obtener_tickets_correos(request: Request, db: Session = Depends(get_db)):
    """Obtiene correos convertidos en tickets con filtrado optimizado por vista"""
    data = getattr(request.state, "json_data", {})
    response = Tickets(db).obtener_tickets_correos(data)
    return response

@tickets_router.get('/obtener_estados_tickets', tags=["TICKETS"], response_model=dict)
def obtener_estados_tickets(db: Session = Depends(get_db)):
    """Obtiene todos los estados de tickets disponibles"""
    response = Tickets(db).obtener_estados_tickets()
    return response

@tickets_router.get('/obtener_tecnicos_gestion_tic', tags=["TICKETS"], response_model=dict)
def obtener_tecnicos_gestion_tic(db: Session = Depends(get_db)):
    """Obtiene todos los técnicos de gestión TIC disponibles"""
    response = Tickets(db).obtener_tecnicos_gestion_tic()
    return response

@tickets_router.post('/obtener_prioridades', tags=["TICKETS"], response_model=dict)
def obtener_prioridades(db: Session = Depends(get_db)):
    """Obtiene todas las prioridades disponibles"""
    response = Tickets(db).obtener_prioridades()
    return response

@tickets_router.post('/obtener_tipo_soporte', tags=["TICKETS"], response_model=dict)
def obtener_tipo_soporte(db: Session = Depends(get_db)):
    """Obtiene todos los tipos de soporte disponibles"""
    response = Tickets(db).obtener_tipo_soporte()
    return response

@tickets_router.post('/obtener_tipo_ticket', tags=["TICKETS"], response_model=dict)
def obtener_tipo_ticket(db: Session = Depends(get_db)):
    """Obtiene todos los tipos de ticket disponibles"""
    response = Tickets(db).obtener_tipo_ticket()
    return response

@tickets_router.post('/obtener_macroprocesos', tags=["TICKETS"], response_model=dict)
def obtener_macroprocesos(db: Session = Depends(get_db)):
    """Obtiene todos los macroprocesos disponibles"""
    response = Tickets(db).obtener_macroprocesos()
    return response

@tickets_router.post('/filtrar_tickets', tags=["TICKETS"], response_model=dict)
@http_decorator
def filtrar_tickets(request: Request, db: Session = Depends(get_db)):
    """Filtra tickets con parámetros específicos usando los campos reales de la tabla"""
    data = getattr(request.state, "json_data", {})
    response = Tickets(db).filtrar_tickets(data)
    return response

@tickets_router.post('/actualizar_ticket', tags=["TICKETS"], response_model=dict)
@http_decorator
def actualizar_ticket(request: Request, db: Session = Depends(get_db)):
    """Actualiza campos específicos de un ticket en la tabla intranet_correos_microsoft"""
    data = getattr(request.state, "json_data", {})
    response = Tickets(db).actualizar_ticket(data)
    return response

# Endpoints para respuestas automáticas y comunicación

@tickets_router.post('/responder_correo', tags=["TICKETS"], response_model=dict)
@http_decorator
def responder_correo(request: Request, db: Session = Depends(get_db)):
    """Responde a un correo específico usando Microsoft Graph API"""
    data = getattr(request.state, "json_data", {})
    response = Tickets(db).responder_correo(data)
    return response

@tickets_router.post('/obtener_hilo_conversacion', tags=["TICKETS"], response_model=dict)
@http_decorator
def obtener_hilo_conversacion(request: Request, db: Session = Depends(get_db)):
    """Obtiene el hilo completo de una conversación de correo"""
    data = getattr(request.state, "json_data", {})
    response = Tickets(db).obtener_hilo_conversacion(data)
    return response

@tickets_router.post('/enviar_respuesta_automatica_ticket', tags=["TICKETS"], response_model=dict)
@http_decorator
def enviar_respuesta_automatica_ticket(request: Request, db: Session = Depends(get_db)):
    """Envía respuesta automática al solicitante cuando se convierte un correo a ticket"""
    data = getattr(request.state, "json_data", {})
    response = Tickets(db).enviar_respuesta_automatica_ticket(data)
    return response

@tickets_router.post('/enviar_respuesta_automatica_optimizada', tags=["TICKETS"], response_model=dict)
@http_decorator
def enviar_respuesta_automatica_optimizada(request: Request, db: Session = Depends(get_db)):
    """Envía respuesta automática optimizada usando datos del correo desde frontend"""
    data = getattr(request.state, "json_data", {})
    response = Tickets(db).enviar_respuesta_automatica_optimizada(data)
    return response

@tickets_router.post('/enviar_correo_nuevo_automatico', tags=["TICKETS"], response_model=dict)
@http_decorator
def enviar_correo_nuevo_automatico(request: Request, db: Session = Depends(get_db)):
    """Envía un correo nuevo automático en lugar de responder al correo existente"""
    data = getattr(request.state, "json_data", {})
    response = Tickets(db).enviar_correo_nuevo_automatico(data)
    return response
