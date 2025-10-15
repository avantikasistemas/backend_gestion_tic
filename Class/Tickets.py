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

class Tickets:

    def __init__(self, db):
        self.db = db
        self.tools = Tools()
        self.querys = Querys(self.db)
        self.token = None

    # Función auxiliar para validar token (compartida con Graph)
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
                
                if ahora < fecha_vencimiento:
                    # Token aún vigente
                    return result['token']
                else:
                    # Token expirado, desactivar
                    token_id = result.get('id')
                    if token_id:
                        self.querys.desactivar_token(token_id)

        # Si no hay token válido, obtener uno nuevo desde Microsoft Graph
        return self._crear_nuevo_token()

    # Función auxiliar para crear nuevo token
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
            self.querys.insertar_datos(TokenModel, data_insert)
            return token
        
        print(f"Error obteniendo el token: {response.status_code} - {response.text}")
        return None

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

    # Función para responder a correos con respuestas manuales personalizadas
    def responder_correo(self, data):
        """
        Responde a un correo con un mensaje personalizado usando Microsoft Graph API
        """
        try:
            message_id = data.get('message_id')
            respuesta = data.get('respuesta')
            ticket_id = data.get('ticket_id')
            
            if not message_id or not respuesta:
                return self.tools.output(400, "Se requieren message_id y respuesta.", {})

            # Obtener el token desde la base de datos
            result = self.querys.get_token()
            self.token = self.validar_existencia_token(result)

            if not self.token:
                return self.tools.output(400, "No se pudo obtener token de acceso.", {})

            # Obtener información del correo original para la respuesta
            url_correo = f"https://graph.microsoft.com/v1.0/users/{EMAIL_USER}/messages/{message_id}"
            headers_info = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            response_info = requests.get(url_correo, headers=headers_info)

            if response_info.status_code != 200:
                print(f"Error obteniendo correo original: {response_info.text}")
                return self.tools.output(404, "No se pudo obtener información del correo.", {})
            
            correo_original = response_info.json()

            # Preparar la respuesta
            subject = correo_original.get('subject', 'Sin asunto')
            if not subject.lower().startswith('re:'):
                subject = f"RE: {subject}"

            from_email = correo_original.get('from', {}).get('emailAddress', {}).get('address', '')
            
            # Construir payload para Microsoft Graph Reply
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
                
                # Ya están ordenados por receivedDateTime desc
                hilo_data = {'value': mensajes_conversacion}
            else:
                print(f"Error obteniendo mensajes: {response_hilo.text}")
                return self.tools.output(500, f"No se pudo obtener el hilo de conversación: {response_hilo.status_code}", {})
            
            if response_hilo.status_code == 200:
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
            
            # Obtener el correo original para saber a quién responder
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
            
            # URL para responder al correo
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
            
            # URL para responder al correo
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
            # Preparar el mensaje de respuesta automática
            mensaje_respuesta = f"""
            <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h3 style="color: #0066cc;">Confirmación de Recepción - Ticket #{ticket_id}</h3>
                
                <p>Estimado/a {from_name},</p>
                
                <p>Hemos recibido su solicitud <strong>(ID: {ticket_id})</strong> y nuestro equipo de soporte la está revisando.</p>
                
                <p><strong>Referencia:</strong> {subject_original}</p>
                
                <p>Su solicitud será analizada y asignada al nivel de atención correspondiente.</p>
                
                <p>Para cualquier consulta adicional sobre este ticket, por favor responda a este correo mencionando el ID del ticket.</p>
                
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
            
            # Preparar el subject del nuevo correo
            subject_respuesta = f"Ticket #{ticket_id} - Confirmación de Recepción"
            
            # Datos del correo nuevo
            mail_data = {
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
                },
                "saveToSentItems": True
            }
            
            # URL para enviar correo nuevo
            send_url = f"{MICROSOFT_URL_GRAPH}{EMAIL_USER}/sendMail"
            
            # Enviar el correo
            headers_send = {
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            }
            
            response_send = requests.post(send_url, json=mail_data, headers=headers_send)
            
            if response_send.status_code == 202:
                print(f"✅ Correo nuevo automático enviado para ticket {ticket_id} a {from_email}")
                return self.tools.output(200, "Correo de confirmación enviado exitosamente.", {
                    'ticket_id': ticket_id,
                    'from_email': from_email,
                    'subject': subject_respuesta,
                    'status': 'enviado'
                })
            else:
                print(f"❌ Error enviando correo nuevo - Status: {response_send.status_code}, Response: {response_send.text}")
                return self.tools.output(500, f"Error enviando correo de confirmación: {response_send.status_code}")
                
        except Exception as e:
            print(f"Error enviando correo nuevo automático: {e}")
            return self.tools.output(500, f"Error interno del servidor: {str(e)}")
