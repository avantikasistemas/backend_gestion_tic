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

@graph_router.post('/obtener_attachments', tags=["TIC"], response_model=dict)
@http_decorator
def obtener_attachments(request: Request, db: Session = Depends(get_db)):
    """
    Obtiene los attachments de un correo específico
    """
    data = getattr(request.state, "json_data", {})
    response = Graph(db).obtener_attachments(data)
    return response
