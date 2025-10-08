from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from Class.Graph import Graph
from Utils.decorator import http_decorator
from Config.db import get_db

graph_router = APIRouter()

@graph_router.post('/obtener_correos', tags=["TIC"], response_model=dict)
@http_decorator
def obtener_correos(request: Request, db: Session = Depends(get_db)):
    response = Graph(db).obtener_correos()
    return response
