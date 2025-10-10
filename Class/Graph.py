import requests
from Utils.tools import Tools, CustomException
from Utils.querys import Querys
from Models.IntranetGraphTokenModel import IntranetGraphTokenModel as TokenModel
from datetime import datetime, timedelta
import hashlib

from Utils.constants import (
    MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, MICROSOFT_TENANT_ID,
    MICROSOFT_API_SCOPE, MICROSOFT_URL, MICROSOFT_URL_GRAPH, PARENT_FOLDER,
    TARGET_FOLDER, EMAIL_USER
)

class Graph:

    def __init__(self, db):
        self.db = db
        self.tools = Tools()
        self.querys = Querys(self.db)
        self.token = None

    # Función para obtener correos con sincronización inteligente
    def obtener_correos(self, forzar_sync=False):
        """
        Obtiene correos implementando sincronización inteligente:
        1. Si no hay correos en BD o forzar_sync=True -> Sync completo
        2. Si hay correos en BD -> Solo sincronizar nuevos
        3. Retorna correos desde BD
        """
        
        # Obtenemos el token desde la base de datos
        result = self.querys.get_token()
        self.token = self.validar_existencia_token(result)

        if not self.token:
            return self.tools.output(400, "No se pudo obtener token de acceso.", {'emails': []})

        try:
            # Determinar tipo de sincronización
            correos_existentes = self.querys.obtener_correos_bd(limite=1)
            tipo_sync = 'completo' if (not correos_existentes or forzar_sync) else 'incremental'
            
            # Iniciar log de sincronización
            log_id = self.querys.crear_log_sync(tipo_sync)
            
            # Ejecutar sincronización
            stats_sync = self.sincronizar_correos_inteligente(tipo_sync)
            
            # Finalizar log
            if log_id:
                self.querys.finalizar_log_sync(
                    log_id, 
                    correos_nuevos=stats_sync.get('nuevos', 0),
                    correos_actualizados=stats_sync.get('actualizados', 0),
                    estado=1
                )
            
            # Obtener correos desde BD para retornar
            correos_bd = self.querys.obtener_correos_bd(limite=100)
            
            # Preparar respuesta
            result = {
                'token': self.token, 
                'emails': correos_bd,
                'sync_stats': stats_sync,
                'tipo_sync': tipo_sync
            }

            return self.tools.output(200, f"Sincronización {tipo_sync} completada.", result)
            
        except Exception as e:
            # Log de error
            if 'log_id' in locals() and log_id:
                self.querys.finalizar_log_sync(log_id, estado=0, mensaje_error=str(e))
            
            print(f"Error en sincronización: {e}")
            
            # Fallback: retornar correos existentes en BD
            correos_bd = self.querys.obtener_correos_bd(limite=100)
            return self.tools.output(200, "Error en sync, mostrando correos locales.", {'emails': correos_bd})

    def sincronizar_correos_inteligente(self, tipo_sync='incremental'):
        """
        Sincronización inteligente de correos:
        - Obtiene correos desde Graph API
        - Compara con BD usando message_id
        - Inserta solo correos nuevos
        - Actualiza correos modificados
        """
        stats = {'nuevos': 0, 'actualizados': 0, 'sin_cambios': 0}
        
        # Obtener correos desde Microsoft Graph
        folder_id = self.get_folder_id(TARGET_FOLDER)
        if not folder_id:
            return stats
            
        emails_graph = self.extraer_correos(folder_id)
        if not emails_graph:
            return stats
        
        # Filtrar correos spam
        emails_filtrados = [
            email for email in emails_graph
            if not email['from']['emailAddress']['address'].lower().startswith(('postmaster', 'noreply'))
            and not email['subject'].startswith(('[!!Spam]', '[!!Massmail]'))
        ]
        
        # Obtener message_ids existentes en BD para comparación rápida
        message_ids_existentes = self.querys.obtener_message_ids_existentes()
        
        for email_graph in emails_filtrados:
            try:
                message_id = email_graph.get('id')
                if not message_id:
                    continue
                
                # Preparar datos del correo para BD
                correo_data = self._preparar_datos_correo(email_graph)
                
                if message_id in message_ids_existentes:
                    # Correo existe, verificar si hay cambios
                    correo_existente = self.querys.obtener_correo_por_message_id(message_id)
                    if correo_existente:
                        # Comparar hash para detectar cambios
                        hash_nuevo = self.querys.generar_hash_contenido(
                            correo_data.get('subject', ''),
                            correo_data.get('body_preview', ''),
                            correo_data.get('from_email', '')
                        )
                        
                        if hash_nuevo != correo_existente.get('hash_contenido'):
                            # Hay cambios, actualizar
                            self.querys.actualizar_correo(message_id, correo_data)
                            stats['actualizados'] += 1
                        else:
                            stats['sin_cambios'] += 1
                else:
                    # Correo nuevo, insertar
                    self.querys.insertar_correo(correo_data)
                    stats['nuevos'] += 1
                    
            except Exception as e:
                print(f"Error procesando correo {message_id}: {e}")
                continue
        
        return stats
    
    def _preparar_datos_correo(self, email_graph):
        """Convierte un correo de Graph API al formato de BD"""
        from_data = email_graph.get('from', {}).get('emailAddress', {})
        
        # Contar attachments si están disponibles
        attachments_count = 0
        has_attachments = 0
        if 'hasAttachments' in email_graph:
            has_attachments = 1 if email_graph['hasAttachments'] else 0
        
        return {
            'message_id': email_graph.get('id'),
            'subject': email_graph.get('subject', ''),
            'from_email': from_data.get('address', ''),
            'from_name': from_data.get('name', ''),
            'received_date': datetime.fromisoformat(
                email_graph.get('receivedDateTime', '').replace('Z', '+00:00')
            ) if email_graph.get('receivedDateTime') else datetime.now(),
            'body_preview': email_graph.get('bodyPreview', ''),
            'body_content': email_graph.get('body', {}).get('content', '') if email_graph.get('body') else '',
            'estado': 1,
            'attachments_count': attachments_count,
            'has_attachments': has_attachments
        }

    # Función para validar si el token existe y si está vigente
    def validar_existencia_token(self, result: dict):
        
        # Si hay un token en BD, validar si aún está vigente
        if result:
            fecha_vencimiento_str = result.get('fecha_vencimiento')
            if fecha_vencimiento_str:
                # Convertir string a datetime si es necesario
                if isinstance(fecha_vencimiento_str, str):
                    fecha_vencimiento = datetime.fromisoformat(fecha_vencimiento_str.replace('Z', '+00:00'))
                else:
                    fecha_vencimiento = fecha_vencimiento_str
                
                # Comparar con tiempo actual
                ahora = datetime.now()
                print(f"Fecha vencimiento: {fecha_vencimiento}")
                print(f"Fecha actual: {ahora}")
                
                if ahora < fecha_vencimiento:
                    # Token aún vigente
                    print("Token vigente, retornando desde BD")
                    return result['token']
                else:
                    # Token expirado, desactivar
                    print("Token expirado, desactivando...")
                    token_id = result.get('id')
                    if token_id:
                        # Crear nueva instancia de Querys para desactivar token
                        self.querys.desactivar_token(token_id)
                        print(f"Token {token_id} desactivado")

        # Si no hay token válido, obtener uno nuevo desde Microsoft Graph
        print("Obteniendo nuevo token desde Microsoft Graph API...")
        return self._crear_nuevo_token()

    # Función para obtener el ID de una carpeta específica
    def get_folder_id(self, target_folder: str):

        """Obtiene el ID de una carpeta específica dentro del correo del usuario."""
        result = None
        url = f"{MICROSOFT_URL_GRAPH}{EMAIL_USER}/mailFolders/{target_folder}"
        data = self._make_request(url)
        if data:
            result = data['id']
        return result

    # Función para extraer correos de una carpeta específica
    def extraer_correos(self, folder_id: str):
        """Recupera correos electrónicos de una carpeta específica."""
        emails = []
        max_iterations = 100
        iteration = 0

        if folder_id:
            url = f"{MICROSOFT_URL_GRAPH}{EMAIL_USER}/mailFolders/{folder_id}/messages?$top=100&$select=from,subject,receivedDateTime,bodyPreview,body"

            while url and iteration < max_iterations:
                print(f"Haciendo solicitud a: {url}")
                data = self._make_request(url)
                if not data:
                    break

                new_emails = data.get('value', [])
                if not new_emails:
                    print("No se recuperaron nuevos correos. Deteniendo.")
                    break

                emails.extend(new_emails)
                url = data.get('@odata.nextLink')  # Paginación
                iteration += 1

        return emails

    # Función para realizar peticiones a la API de Microsoft Graph
    def _make_request(self, endpoint):
        """Realiza una petición GET a Microsoft Graph API."""
        if not self.token:
            print("No se pudo obtener el token de acceso.")
            return None

        headers = {'Authorization': f'Bearer {self.token}'}
        response = requests.get(endpoint, headers=headers)

        if response.status_code == 200:
            return response.json()
        print(f"Error en la solicitud: {response.status_code} - {response.text}")
        return None

    # Función para crear un nuevo token desde Microsoft Graph API
    def _crear_nuevo_token(self):
        """Crea un nuevo token desde Microsoft Graph API."""
        url = f"{MICROSOFT_URL}{MICROSOFT_TENANT_ID}/oauth2/v2.0/token"
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = {
            'client_id': MICROSOFT_CLIENT_ID,
            'scope': ' '.join(MICROSOFT_API_SCOPE),
            'client_secret': MICROSOFT_CLIENT_SECRET,
            'grant_type': 'client_credentials'
        }
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            token = response.json().get('access_token')
            expires_in = response.json().get('expires_in')
            
            data_insert = {
                "token": token,
                "fecha_vencimiento": datetime.now() + timedelta(seconds=expires_in)
            }
            # Crear nueva instancia de Querys para insertar token
            self.querys.insertar_datos(TokenModel, data_insert)
            return token
        
        print(f"Error obteniendo el token: {response.status_code} - {response.text}")
        return None

    # Función para obtener los attachments de un correo específico
    def obtener_attachments(self, data: dict):
        
        messageId = data['messageId']
        self.token = data['token']
        attachments = list()

        if messageId:
            url = f"{MICROSOFT_URL_GRAPH}{EMAIL_USER}/messages/{messageId}/attachments"
            data = self._make_request(url)
            if data:
                attachments = data.get('value', [])

        return self.tools.output(200, "Datos encontrados.", attachments)
    
    # Función para obtener correos solo desde BD (sin sincronizar)
    def obtener_correos_bd_solo(self, limite=100, offset=0, estado=None):
        """
        Obtiene correos únicamente desde la base de datos sin sincronizar
        Útil para cargas rápidas y paginación
        """
        try:
            correos = self.querys.obtener_correos_bd(limite, offset, estado)
            ultimo_sync = self.querys.obtener_ultimo_sync_exitoso()
            
            result = {
                'emails': correos,
                'ultimo_sync': ultimo_sync,
                'total_mostrados': len(correos)
            }
            
            return self.tools.output(200, "Correos obtenidos desde BD.", result)
            
        except Exception as e:
            print(f"Error obteniendo correos desde BD: {e}")
            return self.tools.output(500, "Error obteniendo correos.", {'emails': []})
    
    # Función para marcar correo como procesado
    def marcar_correo_procesado(self, data: dict):
        """
        Marca un correo como procesado o cambia su estado
        """
        message_id = data.get('messageId')
        nuevo_estado = data.get('estado', 2)
        
        if not message_id:
            return self.tools.output(400, "messageId es requerido.", {})
        
        try:
            resultado = self.querys.marcar_correo_procesado(message_id, nuevo_estado)
            
            if resultado:
                return self.tools.output(200, f"Correo marcado como {nuevo_estado}.", resultado)
            else:
                return self.tools.output(404, "Correo no encontrado.", {})
                
        except Exception as e:
            print(f"Error marcando correo como procesado: {e}")
            return self.tools.output(500, "Error actualizando correo.", {})
    
    # Función para descartar correo
    def descartar_correo(self, data: dict):
        """
        Descarta un correo marcándolo con estado 0 para que no aparezca en la bandeja
        """
        message_id = data.get('messageId') or data.get('id')
        
        if not message_id:
            return self.tools.output(400, "messageId o id es requerido.", {})
        
        try:
            resultado = self.querys.descartar_correo(message_id)
            
            if resultado:
                return self.tools.output(200, "Correo descartado exitosamente.", resultado)
            else:
                return self.tools.output(404, "Correo no encontrado.", {})
                
        except Exception as e:
            print(f"Error descartando correo: {e}")
            return self.tools.output(500, "Error descartando correo.", {})
    
    # Función para convertir correo a ticket
    def convertir_correo_ticket(self, data: dict):
        """
        Convierte un correo a ticket marcándolo con ticket = 1
        """
        message_id = data.get('messageId') or data.get('id')
        
        if not message_id:
            return self.tools.output(400, "messageId o id es requerido.", {})
        
        try:
            resultado = self.querys.convertir_correo_ticket(message_id)
            
            if resultado:
                return self.tools.output(200, "Correo convertido a ticket exitosamente.", resultado)
            else:
                return self.tools.output(404, "Correo no encontrado.", {})
                
        except Exception as e:
            print(f"Error convirtiendo correo a ticket: {e}")
            return self.tools.output(500, "Error convirtiendo correo a ticket.", {})
    
    # Función para obtener tickets desde correos
    def obtener_tickets_correos(self, data: dict):
        """
        Obtiene correos convertidos en tickets con filtrado optimizado por vista
        Incluye información del estado (id y nombre) y soporte para filtros por técnico
        """
        vista = data.get('vista', 'todos')
        limite = data.get('limite', 100)
        offset = data.get('offset', 0)
        tecnico_id = data.get('tecnico_id', None)
        
        try:
            resultado = self.querys.obtener_tickets_correos(vista, limite, offset, tecnico_id)
            
            # Mensaje dinámico según filtros aplicados
            mensaje = f"Tickets obtenidos para vista '{vista}'"
            if tecnico_id:
                mensaje += f" filtrado por técnico ID {tecnico_id}"
            
            return self.tools.output(200, mensaje, resultado)
                
        except Exception as e:
            print(f"Error obteniendo tickets de correos: {e}")
            return self.tools.output(500, "Error obteniendo tickets.", {})
    
    # Función para obtener estados de tickets
    def obtener_estados_tickets(self):
        """
        Obtiene todos los estados de tickets disponibles
        """
        try:
            estados = self.querys.obtener_estados_tickets()
            
            return self.tools.output(200, "Estados de tickets obtenidos.", estados)
                
        except Exception as e:
            print(f"Error obteniendo estados de tickets: {e}")
            return self.tools.output(500, "Error obteniendo estados.", {})
    
    # Función para obtener técnicos de gestión TIC
    def obtener_tecnicos_gestion_tic(self):
        """
        Obtiene todos los técnicos de gestión TIC disponibles
        """
        try:
            tecnicos = self.querys.obtener_tecnicos_gestion_tic()
            
            return self.tools.output(200, "Técnicos de gestión TIC obtenidos.", tecnicos)
                
        except Exception as e:
            print(f"Error obteniendo técnicos de gestión TIC: {e}")
            return self.tools.output(500, "Error obteniendo técnicos.", {})

    # Función para obtener todas las prioridades disponibles
    def obtener_prioridades(self):
        """
        Obtiene todas las prioridades disponibles
        """
        try:
            prioridades = self.querys.obtener_prioridades()
            
            return self.tools.output(200, "Prioridades obtenidas.", prioridades)
                
        except Exception as e:
            print(f"Error obteniendo prioridades: {e}")
            return self.tools.output(500, "Error obteniendo prioridades.", {})

    # Función para obtener todos los tipos de soporte disponibles
    def obtener_tipo_soporte(self):
        """
        Obtiene todos los tipos de soporte disponibles
        """
        try:
            tipos_soporte = self.querys.obtener_tipo_soporte()
            
            return self.tools.output(200, "Tipos de soporte obtenidos.", tipos_soporte)
                
        except Exception as e:
            print(f"Error obteniendo tipos de soporte: {e}")
            return self.tools.output(500, "Error obteniendo tipos de soporte.", {})

    # Función para obtener todos los tipos de ticket disponibles
    def obtener_tipo_ticket(self):
        """
        Obtiene todos los tipos de ticket disponibles
        """
        try:
            tipos_ticket = self.querys.obtener_tipo_ticket()
            
            return self.tools.output(200, "Tipos de ticket obtenidos.", tipos_ticket)
                
        except Exception as e:
            print(f"Error obteniendo tipos de ticket: {e}")
            return self.tools.output(500, "Error obteniendo tipos de ticket.", {})

    # Función para obtener todos los macroprocesos disponibles
    def obtener_macroprocesos(self):
        """
        Obtiene todos los macroprocesos disponibles
        """
        try:
            macroprocesos = self.querys.obtener_macroprocesos()
            
            return self.tools.output(200, "Macroprocesos obtenidos.", macroprocesos)
                
        except Exception as e:
            print(f"Error obteniendo macroprocesos: {e}")
            return self.tools.output(500, "Error obteniendo macroprocesos.", {})

    # Función para filtrar tickets con parámetros específicos (Backend Filtering)
    def filtrar_tickets(self, data: dict):
        """
        Filtra tickets usando los campos reales de la tabla intranet_correos_microsoft
        
        Parámetros del frontend:
        - q: str - Búsqueda de texto libre
        - fEstado: int - ID del estado (se mapea a campo 'estado')
        - fAsignado: int - ID del usuario asignado (se mapea a campo 'asignado')
        - fTipoSoporte: int - ID del tipo de soporte (se mapea a campo 'tipo_soporte')
        - fMacro: int - ID del macroproceso (se mapea a campo 'macroproceso')
        - fTipoTicket: int - ID del tipo de ticket (se mapea a campo 'tipo_ticket')
        - vista: str - Vista base (todos, sin, abiertos, proceso, comp, tecnico_X)
        - limite: int - Límite de resultados
        - offset: int - Desplazamiento para paginación
        """
        try:
            # Extraer parámetros con nombres del frontend
            filtros = {
                'vista': data.get('vista', 'todos'),
                'q': data.get('q', '').strip() if data.get('q') else None,
                'estado': data.get('fEstado') if data.get('fEstado') else None,
                'asignado': data.get('fAsignado') if data.get('fAsignado') else None,
                'tipo_soporte': data.get('fTipoSoporte') if data.get('fTipoSoporte') else None,
                'macroproceso': data.get('fMacro') if data.get('fMacro') else None,
                'tipo_ticket': data.get('fTipoTicket') if data.get('fTipoTicket') else None,
                'limite': data.get('limite', 100),
                'offset': data.get('offset', 0)
            }
            
            # Llamar al query optimizado
            resultado = self.querys.filtrar_tickets_optimizado(filtros)
            
            # Contar filtros activos para mensaje
            filtros_activos = sum(1 for k, v in filtros.items() 
                                if k not in ['vista', 'limite', 'offset'] and v is not None)
            
            mensaje = f"Tickets filtrados para vista '{filtros['vista']}'"
            if filtros_activos > 0:
                mensaje += f" con {filtros_activos} filtro(s) aplicado(s)"
            
            return self.tools.output(200, mensaje, resultado)
                
        except Exception as e:
            print(f"Error filtrando tickets: {e}")
            return self.tools.output(500, "Error aplicando filtros.", {})
