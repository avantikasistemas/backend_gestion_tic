from fastapi import APIRouter, Request, Depends, Query
from sqlalchemy.orm import Session
from Class.Dashboard import Dashboard
from Utils.decorator import http_decorator
from Config.db import get_db

dashboard_router = APIRouter()

@dashboard_router.post('/obtener_metricas_dashboard', tags=["DASHBOARD"], response_model=dict)
@http_decorator
def obtener_metricas_dashboard(request: Request, db: Session = Depends(get_db)):
    """Obtiene métricas principales del dashboard: totales, tipos, prioridades y estados"""
    data = getattr(request.state, "json_data", {})
    response = Dashboard(db).obtener_metricas_dashboard(data)
    return response
