import requests
from Utils.tools import Tools, CustomException
from Utils.querys import Querys
from Models.IntranetGraphTokenModel import IntranetGraphTokenModel as TokenModel
from datetime import datetime, timedelta
import hashlib
import traceback

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

    def _build_graph_url(self, endpoint):
        """
        Helper para construir URLs de Microsoft Graph correctamente.
        Maneja la diferencia entre endpoints /me y /users/{email}
        """
        base_url = MICROSOFT_URL_GRAPH.rstrip('/')  # Quitar barra final si existe
        if base_url.endswith('/users'):
            base_url = base_url.replace('/users', '')  # Quitar /users para endpoints /me
        return f"{base_url}/{endpoint.lstrip('/')}"

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

    # Función para sincronización inteligente de correos
    def sincronizar_correos_inteligente(self, tipo_sync='incremental'):
        """
        Sincronización inteligente de correos:
        - Obtiene correos desde Graph API
        - Compara con BD usando message_id
        - Inserta solo correos nuevos
        - Actualiza correos modificados
        """
        stats = {'nuevos': 0, 'actualizados': 0, 'sin_cambios': 0, 'respuestas_procesadas': 0}
        
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
                    # Correo nuevo - verificar si es respuesta a un hilo existente
                    conversation_id = correo_data.get('conversation_id')
                    
                    # Verificar si es respuesta usando múltiples criterios
                    ticket_existente = self._es_respuesta_a_hilo_existente(conversation_id, correo_data)
                    
                    if ticket_existente:
                        # Es una respuesta a un hilo existente
                        if self._procesar_respuesta_hilo(correo_data, ticket_existente):
                            stats['respuestas_procesadas'] += 1
                    else:
                        # Es un correo completamente nuevo, crear nuevo ticket
                        self.querys.insertar_correo(correo_data)
                        stats['nuevos'] += 1
                    
            except Exception as e:
                print(f"Error procesando correo {message_id}: {e}")
                continue
        
        return stats
    
    # Helper para preparar datos del correo
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
            'conversation_id': email_graph.get('conversationId'),  # Agregar conversationId
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

    # Helper para determinar si un correo es respuesta a un hilo existente
    def _es_respuesta_a_hilo_existente(self, conversation_id, correo_data):
        """
        Verifica si un correo entrante es respuesta a una conversación existente
        Usa múltiples criterios para detectar hilos:
        1. conversation_id (principal)
        2. Subject patterns (RE:, FW:, etc.)
        3. Análisis de remitente vs tickets existentes
        
        Returns: dict con info del ticket existente o None si es correo nuevo
        """
        
        # Criterio 1: Buscar por conversation_id (más confiable)
        if conversation_id:
            ticket_existente = self.querys.obtener_ticket_por_conversation_id(conversation_id)
            if ticket_existente:
                return ticket_existente
        
        # Criterio 2: Analizar subject para patrones de respuesta
        subject = correo_data.get('subject', '').strip()
        if subject:
            # Limpiar subject de prefijos RE:, FW:, etc.
            subject_limpio = self._limpiar_subject_respuesta(subject)
            
            if subject_limpio != subject:  # Tenía prefijos de respuesta
                # Buscar tickets con subject similar
                ticket_por_subject = self.querys.buscar_ticket_por_subject_similar(subject_limpio, 
                                                                                 correo_data.get('from_email'))
                if ticket_por_subject:
                    return ticket_por_subject
        
        # Criterio 3: Buscar por email del remitente en tickets recientes (últimos 7 días)
        from_email = correo_data.get('from_email')
        if from_email:
            ticket_reciente = self.querys.buscar_ticket_reciente_por_email(from_email, days=7)
            if ticket_reciente and subject:
                # Verificar si el subject actual contiene palabras clave del ticket original
                if self._subjects_relacionados(subject, ticket_reciente.get('subject', '')):
                    return ticket_reciente
            
        return None

    # Helper para procesar la respuesta de un hilo existente
    def _procesar_respuesta_hilo(self, correo_data, ticket_existente):
        """
        Procesa un correo que es respuesta a un hilo existente
        - Actualiza el ticket con la nueva respuesta
        - Registra la respuesta en el historial
        - NO crea un nuevo ticket
        """
        try:
            ticket_id = ticket_existente.get('id')
            
            # Registrar la respuesta en el historial del ticket
            respuesta_data = {
                'ticket_id': ticket_id,
                'message_id': correo_data.get('message_id'),
                'from_email': correo_data.get('from_email'),
                'from_name': correo_data.get('from_name'),
                'subject': correo_data.get('subject'),
                'body_content': correo_data.get('body_content'),
                'received_date': correo_data.get('received_date'),
                'tipo': 'respuesta_entrante'
            }
            
            # Registrar en el historial del ticket
            self.querys.registrar_respuesta_entrante_ticket(respuesta_data)
            
            # Actualizar la fecha de última actividad del ticket
            self.querys.actualizar_ultima_actividad_ticket(ticket_id)
            
            return True
            
        except Exception as e:
            print(f"Error procesando respuesta del hilo: {e}")
            return False

    # Helper para limpiar el subject de un correo
    def _limpiar_subject_respuesta(self, subject):
        """
        Limpia prefijos de respuesta del subject (RE:, FW:, etc.)
        Returns: subject limpio sin prefijos
        """
        import re
        
        # Patrones comunes de respuesta en diferentes idiomas
        patrones_respuesta = [
            r'^RE:\s*',     # Respuesta en inglés/español
            r'^RES:\s*',    # Respuesta en español
            r'^FW:\s*',     # Reenvío en inglés
            r'^RV:\s*',     # Reenvío en español
            r'^FWD:\s*',    # Reenvío alternativo
            r'^AW:\s*',     # Respuesta en alemán
            r'^SV:\s*',     # Respuesta en sueco/noruego
            r'^\[SPAM\]\s*' # Filtros de spam
        ]
        
        subject_limpio = subject
        for patron in patrones_respuesta:
            subject_limpio = re.sub(patron, '', subject_limpio, flags=re.IGNORECASE)
        
        return subject_limpio.strip()

    # Helper para verificar si dos subjects están relacionados
    def _subjects_relacionados(self, subject1, subject2):
        """
        Verifica si dos subjects están relacionados (mismo hilo)
        """
        if not subject1 or not subject2:
            return False
            
        # Limpiar ambos subjects
        s1_limpio = self._limpiar_subject_respuesta(subject1).lower()
        s2_limpio = self._limpiar_subject_respuesta(subject2).lower()
        
        # Verificar similitud (al menos 70% de coincidencia)
        if len(s1_limpio) == 0 or len(s2_limpio) == 0:
            return False
            
        # Algoritmo simple de similitud por palabras
        palabras1 = set(s1_limpio.split())
        palabras2 = set(s2_limpio.split())
        
        if len(palabras1.union(palabras2)) == 0:
            return False
            
        similitud = len(palabras1.intersection(palabras2)) / len(palabras1.union(palabras2))
        return similitud >= 0.7

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
            url = f"{MICROSOFT_URL_GRAPH}{EMAIL_USER}/mailFolders/{folder_id}/messages?$top=100&$select=from,subject,receivedDateTime,bodyPreview,body,conversationId,id,hasAttachments"

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

    # Función para actualizar campos específicos de un ticket
    def actualizar_ticket(self, data):
        """
        Actualiza campos específicos de un ticket
        """
        try:
            ticket_id = data.get('ticket_id')
            message_id = data.get('message_id')  # También aceptar message_id como alternativa
            campo = data.get('campo')
            valor = data.get('valor')
            
            if not (ticket_id or message_id):
                return self.tools.output(400, "Se requiere ticket_id o message_id.", {})
            
            if not campo:
                return self.tools.output(400, "Se requiere el campo a actualizar.", {})
            
            # Mapeo de campos frontend a backend
            mapeo_campos = {
                'prioridad': 'prioridad',
                'estado': 'estado',
                'tipo_soporte': 'tipo_soporte',
                'tipo_ticket': 'tipo_ticket',
                'macroproceso': 'macroproceso',
                'asignado': 'asignado',
                'fecha_vencimiento': 'fecha_vencimiento',
                'sla': 'sla'
            }
            
            campo_bd = mapeo_campos.get(campo, campo)
            
            # Validación de campo permitido
            if campo not in mapeo_campos:
                return self.tools.output(400, f"Campo '{campo}' no permitido para actualización.", {})
            
            # Preparar datos de actualización
            # Convertir valor vacío a None para campos numéricos
            if valor == "" or valor == "null":
                if campo_bd in ['prioridad', 'tipo_soporte', 'tipo_ticket', 'macroproceso', 'asignado', 'sla']:
                    valor = None
                elif campo_bd == 'fecha_vencimiento':
                    valor = None
            
            datos_actualizacion = {campo_bd: valor}
            
            # Si tenemos ticket_id, buscar el message_id
            if ticket_id and not message_id:
                ticket = self.querys.obtener_ticket_por_id(ticket_id)
                if not ticket:
                    return self.tools.output(404, "Ticket no encontrado.", {})
                message_id = ticket.get('message_id')
            
            # Actualizar en la base de datos
            resultado = self.querys.actualizar_correo(message_id, datos_actualizacion)
            
            if resultado:
                mensaje = f"Campo {campo} actualizado correctamente."
                return self.tools.output(200, mensaje, {
                    'ticket_id': ticket_id or resultado.get('id'),
                    'campo': campo,
                    'valor': valor,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                return self.tools.output(404, "No se pudo actualizar el ticket.", {})
                
        except Exception as e:
            print(f"Error actualizando ticket: {e}")
            return self.tools.output(500, f"Error interno del servidor: {str(e)}", {})

    # Función para responder un correo específico
    def responder_correo(self, data):
        """
        Responde a un correo específico usando Microsoft Graph API
        """
        try:
            message_id = data.get('message_id')
            respuesta = data.get('respuesta', '')
            ticket_id = data.get('ticket_id')
            
            if not message_id:
                return self.tools.output(400, "Se requiere message_id del correo original.", {})
            
            if not respuesta.strip():
                return self.tools.output(400, "Se requiere contenido de la respuesta.", {})
            
            # Obtener el token desde la base de datos
            result = self.querys.get_token()
            self.token = self.validar_existencia_token(result)

            if not self.token:
                return self.tools.output(400, "No se pudo obtener token de acceso.", {})

            # Obtener el correo original para extraer información necesaria
            correo_original = self.querys.obtener_correo_por_message_id(message_id)
            if not correo_original:
                return self.tools.output(404, "Correo original no encontrado.", {})

            # Preparar la respuesta
            subject = correo_original.get('subject', 'Sin asunto')
            if not subject.lower().startswith('re:'):
                subject = f"RE: {subject}"

            from_email = correo_original.get('from_email', '')
            
            # Construir payload para Microsoft Graph Reply
            # Para el endpoint /reply, el payload debe ser más simple
            payload = {
                "message": {
                    "body": {
                        "contentType": "HTML", 
                        "content": f"<div><p>{respuesta.replace(chr(10), '<br>')}</p><br><hr><p><em>Respuesta enviada desde el sistema de tickets de Avantika</em></p></div>"
                    }
                }
            }

            # Enviar respuesta usando Microsoft Graph API
            url = f"https://graph.microsoft.com/v1.0/users/{EMAIL_USER}/messages/{message_id}/reply"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, headers=headers, json=payload)

            if response.status_code in [200, 202]:
                # Registrar la respuesta en la base de datos
                self.querys.registrar_respuesta_correo(
                    message_id=message_id,
                    respuesta=respuesta,
                    ticket_id=ticket_id
                )
                
                return self.tools.output(200, "Respuesta enviada exitosamente.", {
                    "message_id": message_id,
                    "destinatario": from_email,
                    "subject": subject
                })
            else:
                print(f"Error enviando respuesta: {response.status_code} - {response.text}")
                return self.tools.output(500, "Error enviando respuesta por Graph API.", {})
                
        except Exception as e:
            print(f"Error respondiendo correo: {e}")
            return self.tools.output(500, f"Error interno del servidor: {str(e)}", {})

    # Función para obtener el hilo completo de una conversación
    def obtener_hilo_conversacion(self, data):
        """
        Obtiene el hilo completo de una conversación usando el conversation ID
        """
        try:
            message_id = data.get('message_id')
            
            if not message_id:
                return self.tools.output(400, "Se requiere message_id.", {})
            
            # Obtener el token desde la base de datos
            result = self.querys.get_token()
            self.token = self.validar_existencia_token(result)

            if not self.token:
                return self.tools.output(400, "No se pudo obtener token de acceso.", {})

            # Primero obtener el mensaje original para extraer el conversation ID
            url_original = f"https://graph.microsoft.com/v1.0/users/{EMAIL_USER}/messages/{message_id}"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            response_original = requests.get(url_original, headers=headers)

            if response_original.status_code != 200:
                print(f"Error obteniendo mensaje original: {response_original.text}")
                return self.tools.output(404, "Mensaje original no encontrado.", {})
            
            mensaje_data = response_original.json()
            conversation_id = mensaje_data.get('conversationId')
            
            if not conversation_id:
                return self.tools.output(400, "No se pudo obtener conversation ID.", {})

            # Usar método robusto: obtener mensajes recientes y filtrar localmente
            # Esto evita el problema de filtros complejos en Microsoft Graph
            url_conversacion = f"https://graph.microsoft.com/v1.0/users/{EMAIL_USER}/messages"
            params = {
                "$top": "100",  # Aumentar para asegurar que capturemos toda la conversación
                "$orderby": "receivedDateTime desc",
                "$select": "id,conversationId,subject,from,receivedDateTime,body,isRead"
            }
            
            response_hilo = requests.get(url_conversacion, headers=headers, params=params)
            
            if response_hilo.status_code == 200:
                todos_mensajes = response_hilo.json().get('value', [])
                
                # Filtrar mensajes de la misma conversación localmente
                mensajes_conversacion = [msg for msg in todos_mensajes if msg.get('conversationId') == conversation_id]
                
                # Ya están ordenados por receivedDateTime desc, así que no necesitamos reordenar
                hilo_data = {'value': mensajes_conversacion}
            else:
                print(f"Error obteniendo mensajes: {response_hilo.text}")
                return self.tools.output(500, f"No se pudo obtener el hilo de conversación: {response_hilo.status_code}", {})
            
            if response_hilo.status_code == 200:
                # hilo_data ya está asignado en el bloque anterior
                mensajes = hilo_data.get('value', [])
                
                # Procesar cada mensaje del hilo
                hilo_procesado = []
                for mensaje in mensajes:
                    mensaje_procesado = {
                        'id': mensaje.get('id'),
                        'subject': mensaje.get('subject'),
                        'from_name': mensaje.get('from', {}).get('emailAddress', {}).get('name', ''),
                        'from_email': mensaje.get('from', {}).get('emailAddress', {}).get('address', ''),
                        'receivedDateTime': mensaje.get('receivedDateTime'),
                        'body': mensaje.get('body', {}).get('content', ''),
                        'isRead': mensaje.get('isRead', False)
                    }
                    hilo_procesado.append(mensaje_procesado)
                
                return self.tools.output(200, f"Hilo de conversación obtenido. {len(hilo_procesado)} mensajes.", {
                    'conversacion_id': conversation_id,
                    'mensajes': hilo_procesado,
                    'total_mensajes': len(hilo_procesado)
                })
            else:
                print(f"Error obteniendo hilo - Status: {response_hilo.status_code}, Texto: {response_hilo.text}")
                return self.tools.output(500, f"Error obteniendo hilo de conversación: {response_hilo.status_code}", {})
                
        except Exception as e:
            print(f"Error obteniendo hilo de conversación: {e}")
            return self.tools.output(500, f"Error interno del servidor: {str(e)}", {})

    # Función para enviar respuesta automática al crear un ticket desde un correo        
    def enviar_respuesta_automatica_ticket(self, data: dict):
        """
        Envía respuesta automática al solicitante cuando se crea un ticket desde un correo.
        Esta respuesta es independiente del sistema de hilos de conversación.
        """
        
        message_id = data.get('message_id')
        ticket_id = data.get('ticket_id')
        
        if not message_id or not ticket_id:
            return {
                "status": 400,
                "message": "Se requieren message_id y ticket_id",
                "data": {}
            }
        
        # Obtenemos el token desde la base de datos
        result = self.querys.get_token()
        self.token = self.validar_existencia_token(result)

        if not self.token:
            return self.tools.output(400, "No se pudo obtener token de acceso.")
            
        try:
            # Obtener información del correo original para responder
            headers_correo = {
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            }
            
            # Obtener el correo original para saber a quién responder (usar usuario específico)
            correo_url = f"{MICROSOFT_URL_GRAPH}{EMAIL_USER}/messages/{message_id}"
            response_correo = requests.get(correo_url, headers=headers_correo)
            
            if response_correo.status_code != 200:
                print(f"Error obteniendo correo original - Status: {response_correo.status_code}")
                return self.tools.output(500, f"Error obteniendo correo original: {response_correo.status_code}")
            
            correo_data = response_correo.json()
            
            # Preparar el mensaje de respuesta automática
            mensaje_respuesta = f"""
            <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h3 style="color: #0066cc;">Confirmación de Recepción - Ticket #{ticket_id}</h3>
                
                <p>Estimado/a {correo_data.get('from', {}).get('emailAddress', {}).get('name', 'usuario')},</p>
                
                <p>Hemos recibido su solicitud <strong>(ID: {ticket_id})</strong> y nuestro equipo de soporte la está revisando.</p>
                
                <p>Su solicitud será analizada y asignada al nivel de atención correspondiente.</p>
                
                <p>Si desea agregar comentarios adicionales, por favor responda a este correo electrónico.</p>
                
                <div style="margin: 20px 0; padding: 15px; background-color: #f8f9fa; border-left: 4px solid #dc3545; border-radius: 4px;">
                    <p style="margin: 0; font-size: 14px; color: #721c24;">
                        <strong>⚠️ Nota importante:</strong> Este es un mensaje automático generado por el sistema. 
                        Para cualquier consulta adicional sobre su ticket, responda directamente a este correo 
                        o contacte a nuestro equipo de soporte.
                    </p>
                </div>
                
                <p style="margin-top: 30px;">
                    Atentamente,<br>
                    <strong>El equipo de soporte de Avantika</strong><br>
                    <span style="font-size: 12px; color: #666;">
                        Avántika Colombia S.A.S | Gestión de Tecnologías de la Información
                    </span>
                </p>
            </div>
            """
            
            # Preparar datos para la respuesta
            reply_data = {
                "comment": mensaje_respuesta
            }
            
            # URL para responder al correo (usar usuario específico)
            reply_url = f"{MICROSOFT_URL_GRAPH}{EMAIL_USER}/messages/{message_id}/reply"
            
            # Enviar la respuesta
            headers_reply = {
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            }
            
            response_reply = requests.post(reply_url, json=reply_data, headers=headers_reply)
            
            if response_reply.status_code == 202:
                return self.tools.output(200, "Respuesta automática enviada exitosamente.", {
                    'ticket_id': ticket_id,
                    'message_id': message_id,
                    'status': 'enviado'
                })
            else:
                print(f"❌ Error enviando respuesta automática - Status: {response_reply.status_code}, Response: {response_reply.text}")
                return self.tools.output(500, f"Error enviando respuesta automática: {response_reply.status_code}")
                
        except Exception as e:
            print(f"Error enviando respuesta automática: {e}")
            return self.tools.output(500, f"Error interno del servidor: {str(e)}")

    # Función optimizada para enviar respuesta automática usando datos desde frontend
    def enviar_respuesta_automatica_optimizada(self, data):
        """
        Envía respuesta automática al solicitante usando datos del correo desde frontend.
        Más eficiente porque evita consulta adicional a Microsoft Graph.
        """
        message_id = data.get('message_id')
        ticket_id = data.get('ticket_id')
        from_name = data.get('from_name', 'usuario')
        from_email = data.get('from_email')
        subject = data.get('subject', '')
        
        # Validar y limpiar message_id
        if not message_id or not ticket_id:
            return self.tools.output(400, "Se requieren message_id y ticket_id")
            
        if not from_email:
            return self.tools.output(400, "Se requiere from_email del remitente")

        # Limpiar y validar message_id
        message_id_clean = str(message_id).strip()
        
        # Verificar que el message_id tenga formato válido de Microsoft Graph
        if not message_id_clean or len(message_id_clean) < 10:
            return self.tools.output(400, f"Message ID inválido: '{message_id_clean}'")
            
        # Obtenemos el token desde la base de datos
        result = self.querys.get_token()
        self.token = self.validar_existencia_token(result)

        if not self.token:
            return self.tools.output(400, "No se pudo obtener token de acceso.")
            
        try:
            # Preparar el mensaje de respuesta automática con datos desde frontend
            mensaje_respuesta = f"""
            <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h3 style="color: #0066cc;">Confirmación de Recepción - Ticket #{ticket_id}</h3>
                
                <p>Estimado/a {from_name},</p>
                
                <p>Hemos recibido su solicitud <strong>(ID: {ticket_id})</strong> y nuestro equipo de soporte la está revisando.</p>
                
                <p><strong>Asunto:</strong> {subject}</p>
                
                <p>Su solicitud será analizada y asignada al nivel de atención correspondiente.</p>
                
                <p>Si desea agregar comentarios adicionales, por favor responda a este correo electrónico.</p>
                
                <div style="margin: 20px 0; padding: 15px; background-color: #f8f9fa; border-left: 4px solid #dc3545; border-radius: 4px;">
                    <p style="margin: 0; font-size: 14px; color: #721c24;">
                        <strong>⚠️ Nota importante:</strong> Este es un mensaje automático generado por el sistema. 
                        Para cualquier consulta adicional sobre su ticket, responda directamente a este correo 
                        o contacte a nuestro equipo de soporte.
                    </p>
                </div>
                
                <p style="margin-top: 30px;">
                    Atentamente,<br>
                    <strong>El equipo de soporte de Avantika</strong><br>
                    <span style="font-size: 12px; color: #666;">
                        Avántika Colombia S.A.S | Gestión de Tecnologías de la Información
                    </span>
                </p>
            </div>
            """
            
            # Preparar datos para la respuesta
            reply_data = {
                "comment": mensaje_respuesta
            }
            
            # URL para responder al correo (usar usuario específico)
            reply_url = f"{MICROSOFT_URL_GRAPH}{EMAIL_USER}/messages/{message_id}/reply"
            
            # Enviar la respuesta
            headers_reply = {
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            }
            
            response_reply = requests.post(reply_url, json=reply_data, headers=headers_reply)
            
            if response_reply.status_code == 202:
                print(f"✅ Respuesta automática optimizada enviada para ticket {ticket_id} a {from_email}")
                return self.tools.output(200, "Respuesta automática enviada exitosamente.", {
                    'ticket_id': ticket_id,
                    'message_id': message_id_clean,
                    'from_email': from_email,
                    'status': 'enviado'
                })
            else:
                print(f"❌ Error enviando respuesta automática - Status: {response_reply.status_code}, Response: {response_reply.text}")
                return self.tools.output(500, f"Error enviando respuesta automática: {response_reply.status_code}")
                
        except Exception as e:
            print(f"Error enviando respuesta automática optimizada: {e}")
            return self.tools.output(500, f"Error interno del servidor: {str(e)}")

    # Función para enviar un nuevo correo automático en lugar de responder al original
    def enviar_correo_nuevo_automatico(self, data):
        """
        Envía un correo nuevo automático en lugar de responder al correo existente.
        Usa como alternativa cuando el message_id del correo original es problemático.
        """
        ticket_id = data.get('ticket_id')
        from_name = data.get('from_name', 'usuario')
        from_email = data.get('from_email')
        subject_original = data.get('subject', '')
        
        if not ticket_id or not from_email:
            return self.tools.output(400, "Se requieren ticket_id y from_email")

        # Obtenemos el token desde la base de datos
        result = self.querys.get_token()
        self.token = self.validar_existencia_token(result)

        if not self.token:
            return self.tools.output(400, "No se pudo obtener token de acceso.")
            
        try:
            
            # Preparar el subject para el nuevo correo (más claro)
            if subject_original and len(subject_original.strip()) > 0:
                subject_respuesta = f"Ticket #{ticket_id} Confirmado - {subject_original}"
            else:
                subject_respuesta = f"Ticket #{ticket_id} Confirmado - Su solicitud ha sido recibida"
            
            # Preparar el mensaje de respuesta automática
            mensaje_respuesta = f"""
            <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h3 style="color: #047857;">Confirmación de Recepción - Ticket #{ticket_id}</h3>
                
                <p>Estimado/a {from_name},</p>
                
                <p>Hemos recibido su solicitud <strong>(#: {ticket_id})</strong> y nuestro equipo de soporte la está revisando.</p>
                
                <p><strong>Asunto original:</strong> {subject_original}</p>
                
                <p>Su solicitud será analizada y asignada al nivel de atención correspondiente.</p>
                
                <div style="margin: 20px 0; padding: 15px; background-color: #f8f9fa; border-left: 4px solid #dc3545; border-radius: 4px;">
                    <p style="margin: 0; font-size: 14px; color: #721c24;">
                        <strong>⚠️ Nota importante:</strong> Este es un mensaje automático generado por el sistema.
                    </p>
                </div>
                
                <p style="margin-top: 30px;">
                    Atentamente,<br>
                    <strong>El equipo de Tic de Avantika</strong><br>
                    <span style="font-size: 12px; color: #666;">
                        Avántika Colombia S.A.S
                    </span>
                </p>
            </div>
            """
            
            # Preparar datos para el nuevo correo
            email_data = {
                "message": {
                    "subject": subject_respuesta,
                    "body": {
                        "contentType": "HTML",
                        "content": mensaje_respuesta
                    },
                    "toRecipients": [
                        {
                            "emailAddress": {
                                "address": from_email,
                                "name": from_name
                            }
                        }
                    ]
                }
            }
            
            # URL para enviar correo usando usuario específico (no /me por autenticación de aplicación)
            send_url = f"{MICROSOFT_URL_GRAPH}{EMAIL_USER}/sendMail"

            # Enviar el correo
            headers_send = {
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            }
            

            response_send = requests.post(send_url, json=email_data, headers=headers_send)
            if response_send.status_code != 202:
                print(f"📋 Response body: {response_send.text}")
            
            if response_send.status_code == 202:
                return self.tools.output(200, "Correo automático enviado exitosamente.", {
                    'ticket_id_numero': ticket_id,
                    'ticket_id_display': ticket_id,
                    'from_email': from_email,
                    'subject': subject_respuesta,
                    'status': 'enviado'
                })
            else:
                print(f"❌ Error enviando correo automático - Status: {response_send.status_code}, Response: {response_send.text}")
                return self.tools.output(500, f"Error enviando correo automático: {response_send.status_code}")
                
        except Exception as e:
            print(f"Error enviando correo automático: {e}")
            return self.tools.output(500, f"Error interno del servidor: {str(e)}")
