from fastapi import APIRouter, Request, Depends, Query
from sqlalchemy.orm import Session
from Class.Graph import Graph
from Utils.decorator import http_decorator
from Config.db import get_db

graph_router = APIRouter()

@graph_router.post('/obtener_correos', tags=["TIC"], response_model=dict)
@http_decorator
def obtener_correos(request: Request, db: Session = Depends(get_db)):
    """
    Sincroniza correos de Microsoft Graph y los retorna desde BD
    Implementa sincronización inteligente (solo nuevos correos)
    """
    data = getattr(request.state, "json_data", {})
    forzar_sync = data.get('forzar_sync', False)
    response = Graph(db).obtener_correos(forzar_sync)
    return response

@graph_router.get('/obtener_correos_bd', tags=["TIC"], response_model=dict)
def obtener_correos_bd(
    request: Request, 
    db: Session = Depends(get_db),
    limite: int = Query(100, description="Número máximo de correos a obtener"),
    offset: int = Query(0, description="Número de correos a saltar"),
    estado: str = Query(None, description="Filtrar por estado (nuevo, procesado, convertido_ticket)")
):
    """
    Obtiene correos únicamente desde la base de datos (sin sincronizar)
    Útil para cargas rápidas y paginación
    """
    response = Graph(db).obtener_correos_bd_solo(limite, offset, estado)
    return response

@graph_router.post('/sincronizar_correos', tags=["TIC"], response_model=dict)
@http_decorator
def sincronizar_correos(request: Request, db: Session = Depends(get_db)):
    """
    Fuerza una sincronización completa de correos desde Microsoft Graph
    """
    response = Graph(db).obtener_correos(forzar_sync=True)
    return response

@graph_router.post('/marcar_correo_procesado', tags=["TIC"], response_model=dict)
@http_decorator
def marcar_correo_procesado(request: Request, db: Session = Depends(get_db)):
    """
    Marca un correo como procesado o cambia su estado
    """
    data = getattr(request.state, "json_data", {})
    response = Graph(db).marcar_correo_procesado(data)
    return response

@graph_router.post('/descartar_correo', tags=["TIC"], response_model=dict)
@http_decorator
def descartar_correo(request: Request, db: Session = Depends(get_db)):
    """
    Descarta un correo marcándolo con activo 0 para que no aparezca en la bandeja
    """
    data = getattr(request.state, "json_data", {})
    response = Graph(db).descartar_correo(data)
    return response

@graph_router.post('/convertir_correo_ticket', tags=["TIC"], response_model=dict)
@http_decorator
def convertir_correo_ticket(request: Request, db: Session = Depends(get_db)):
    """
    Convierte un correo a ticket marcándolo con ticket = 1
    """
    data = getattr(request.state, "json_data", {})
    response = Graph(db).convertir_correo_ticket(data)
    return response

@graph_router.post('/obtener_tickets_correos', tags=["TIC"], response_model=dict)
@http_decorator
def obtener_tickets_correos(request: Request, db: Session = Depends(get_db)):
    """
    Obtiene correos convertidos en tickets con filtrado optimizado por vista
    Incluye información del estado (id y nombre)
    """
    data = getattr(request.state, "json_data", {})
    response = Graph(db).obtener_tickets_correos(data)
    return response

@graph_router.get('/obtener_estados_tickets', tags=["TIC"], response_model=dict)
def obtener_estados_tickets(db: Session = Depends(get_db)):
    """
    Obtiene todos los estados de tickets disponibles
    """
    response = Graph(db).obtener_estados_tickets()
    return response

@graph_router.get('/obtener_tecnicos_gestion_tic', tags=["TIC"], response_model=dict)
def obtener_tecnicos_gestion_tic(db: Session = Depends(get_db)):
    """
    Obtiene todos los técnicos de gestión TIC disponibles
    """
    response = Graph(db).obtener_tecnicos_gestion_tic()
    return response

@graph_router.post('/obtener_attachments', tags=["TIC"], response_model=dict)
@http_decorator
def obtener_attachments(request: Request, db: Session = Depends(get_db)):
    """
    Obtiene los attachments de un correo específico
    """
    data = getattr(request.state, "json_data", {})
    response = Graph(db).obtener_attachments(data)
    return response

@graph_router.post('/obtener_prioridades', tags=["TIC"], response_model=dict)
def obtener_prioridades(db: Session = Depends(get_db)):
    """
    Obtiene todas las prioridades disponibles
    """
    response = Graph(db).obtener_prioridades()
    return response

@graph_router.post('/obtener_tipo_soporte', tags=["TIC"], response_model=dict)
def obtener_tipo_soporte(db: Session = Depends(get_db)):
    """
    Obtiene todos los tipos de soporte disponibles
    """
    response = Graph(db).obtener_tipo_soporte()
    return response

@graph_router.post('/obtener_tipo_ticket', tags=["TIC"], response_model=dict)
def obtener_tipo_ticket(db: Session = Depends(get_db)):
    """
    Obtiene todos los tipos de ticket disponibles
    """
    response = Graph(db).obtener_tipo_ticket()
    return response

@graph_router.post('/obtener_macroprocesos', tags=["TIC"], response_model=dict)
def obtener_macroprocesos(db: Session = Depends(get_db)):
    """
    Obtiene todos los macroprocesos disponibles
    """
    response = Graph(db).obtener_macroprocesos()
    return response
