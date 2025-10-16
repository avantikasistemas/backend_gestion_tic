import requests
from Utils.tools import Tools, CustomException
from Utils.querys import Querys
from datetime import datetime, timedelta

from Utils.constants import (
    MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, MICROSOFT_TENANT_ID,
    MICROSOFT_API_SCOPE, MICROSOFT_URL, MICROSOFT_URL_GRAPH, PARENT_FOLDER,
    TARGET_FOLDER, EMAIL_USER
)

class Dashboard:

    def __init__(self, db):
        self.db = db
        self.tools = Tools()
        self.querys = Querys(self.db)
        self.token = None

    # Función para obtener métricas del dashboard
    def obtener_metricas_dashboard(self, data=None):
        """
        Obtiene las métricas principales del dashboard:
        - Total de tickets (activo=1, ticket=1)
        - Gestión (tipo_ticket=1)
        - Estratégicos (tipo_ticket=2)
        - Prioridad alta (prioridad=3)
        - Estados: Abiertos (estado=1), En proceso (estado=2), Completados (estado=3)
        """
        try:
            # Obtener filtros de fecha si se proporcionan
            filtros = data or {}
            fecha_inicio = filtros.get('fecha_inicio')
            fecha_fin = filtros.get('fecha_fin')
            
            # Obtener métricas usando query directo
            metricas = self.querys.obtener_metricas_dashboard(fecha_inicio, fecha_fin)
            
            return self.tools.output(200, "Métricas del dashboard obtenidas exitosamente.", metricas)
                
        except Exception as e:
            print(f"Error obteniendo métricas del dashboard: {e}")
            return self.tools.output(500, "Error obteniendo métricas del dashboard.", {})
        
    