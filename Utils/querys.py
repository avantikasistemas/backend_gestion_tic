from Utils.tools import Tools, CustomException
from sqlalchemy import text, func, case
from datetime import datetime, date
from Models.IntranetGraphTokenModel import IntranetGraphTokenModel as TokenModel
from Models.IntranetCorreosMicrosoftModel import IntranetCorreosMicrosoftModel as CorreosMicrosoftModel
from Models.IntranetSyncLogModel import IntranetSyncLogModel as SyncLogModel
from Models.IntranetEstadosTickets import IntranetEstadosTickets
from Models.IntranetUsuariosGestionTicModel import IntranetUsuariosGestionTicModel
from Models.IntranetTipoPrioridadModel import IntranetTipoPrioridadModel
from Models.IntranetTipoSoporteModel import IntranetTipoSoporteModel
from Models.IntranetTipoTicketModel import IntranetTipoTicketModel
from Models.IntranetPerfilesMacroprocesoModel import IntranetPerfilesMacroprocesoModel

import hashlib

class Querys:

    def __init__(self, db):
        self.db = db
        self.tools = Tools()
        self.query_params = dict()

    # Query para obtener la información del activo por código
    def get_token(self):
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                response = dict()
                
                sql = self.db.query(
                    TokenModel
                ).filter(
                    TokenModel.estado == 1
                ).order_by(
                    TokenModel.id.desc()
                ).first()

                if sql:
                    response = sql.to_dict()

                return response

            except Exception as e:
                retry_count += 1
                print(f"Error en conexión a BD (intento {retry_count}/{max_retries}): {e}")
                
                if retry_count < max_retries:
                    # Cerrar conexión actual e intentar reconectar
                    try:
                        self.db.close()
                    except:
                        pass
                    
                    # Esperar un poco antes del siguiente intento
                    import time
                    time.sleep(1)
                    
                    # Reinicializar la conexión
                    from Config.db import get_database
                    self.db = next(get_database())
                else:
                    # Si se agotaron los reintentos, lanzar excepción
                    raise CustomException(f"Error de conexión a BD después de {max_retries} intentos: {e}")
        
        return dict()

    # Query para desactivar token expirado
    def desactivar_token(self, token_id: int):
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                token_record = self.db.query(
                    TokenModel).filter(TokenModel.id == token_id).first()
                if token_record:
                    token_record.estado = 0
                    self.db.commit()
                    return True
                return False
                
            except Exception as e:
                retry_count += 1
                print(f"Error desactivando token (intento {retry_count}/{max_retries}): {e}")
                
                try:
                    self.db.rollback()
                except:
                    pass
                
                if retry_count < max_retries:
                    # Cerrar conexión actual e intentar reconectar
                    try:
                        self.db.close()
                    except:
                        pass
                    
                    # Esperar un poco antes del siguiente intento
                    import time
                    time.sleep(1)
                    
                    # Reinicializar la conexión
                    from Config.db import get_database
                    self.db = next(get_database())
                else:
                    raise CustomException(f"Error desactivando token después de {max_retries} intentos: {e}")
        
        return False

    # Query para insertar datos en cualquier tabla
    def insertar_datos(self, model: any, data: dict):
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                new_record = model(data)
                self.db.add(new_record)
                self.db.commit()
                self.db.refresh(new_record)
                return new_record
                
            except Exception as e:
                retry_count += 1
                print(f"Error insertando datos (intento {retry_count}/{max_retries}): {e}")
                
                try:
                    self.db.rollback()
                except:
                    pass
                
                if retry_count < max_retries:
                    # Cerrar conexión actual e intentar reconectar
                    try:
                        self.db.close()
                    except:
                        pass
                    
                    # Esperar un poco antes del siguiente intento
                    import time
                    time.sleep(1)
                    
                    # Reinicializar la conexión
                    from Config.db import get_database
                    self.db = next(get_database())
                else:
                    raise CustomException(f"Error insertando datos después de {max_retries} intentos: {e}")
        
        return None

    # ============= MÉTODOS PARA CORREOS MICROSOFT =============

    # Query para generar hash del contenido del correo
    def generar_hash_contenido(self, subject, body_preview, from_email):
        """Genera un hash del contenido del correo para detectar cambios"""
        contenido = f"{subject}{body_preview}{from_email}"
        return hashlib.sha256(contenido.encode()).hexdigest()
    
    # Query para obtener un correo por su message_id de Microsoft
    def obtener_correo_por_message_id(self, message_id):
        """Obtiene un correo por su message_id de Microsoft"""
        try:
            correo = self.db.query(CorreosMicrosoftModel).filter(
                CorreosMicrosoftModel.message_id == message_id
            ).first()
            
            return correo.to_dict() if correo else None
            
        except Exception as e:
            print(f"Error obteniendo correo por message_id: {e}")
            return None

    # Query para obtener correos desde la base de datos con filtros y paginación
    def obtener_correos_bd(self, limite=100, offset=0, estado=None):
        """Obtiene correos desde la base de datos con filtros y paginación"""
        try:
            # Filtrar correos activos y no descartados (estado != 0)
            query = self.db.query(CorreosMicrosoftModel).filter(
                CorreosMicrosoftModel.ticket == 0,
                CorreosMicrosoftModel.activo == 1,
                CorreosMicrosoftModel.estado != 0  # Excluir correos descartados
            )
            
            # Filtro por estado específico si se especifica
            if estado:
                query = query.filter(CorreosMicrosoftModel.estado == estado)
            
            # Ordenar por fecha recibida (más recientes primero)
            query = query.order_by(CorreosMicrosoftModel.received_date.desc())
            
            # Paginación
            correos = query.offset(offset).limit(limite).all()
            
            # Convertir a formato frontend
            return [correo.to_frontend_format() for correo in correos]
            
        except Exception as e:
            print(f"Error obteniendo correos de BD: {e}")
            return []

    # Query para insertar un nuevo correo
    def insertar_correo(self, correo_data):
        """Inserta un nuevo correo en la base de datos"""
        try:
            # Generar hash del contenido
            hash_contenido = self.generar_hash_contenido(
                correo_data.get('subject', ''),
                correo_data.get('body_preview', ''),
                correo_data.get('from_email', '')
            )
            correo_data['hash_contenido'] = hash_contenido
            
            nuevo_correo = CorreosMicrosoftModel(correo_data)
            self.db.add(nuevo_correo)
            self.db.commit()
            self.db.refresh(nuevo_correo)
            
            return nuevo_correo.to_dict()
            
        except Exception as e:
            self.db.rollback()
            print(f"Error insertando correo: {e}")
            return None
    
    # Query para actualizar un correo existente
    def actualizar_correo(self, message_id, datos_actualizacion):
        """Actualiza un correo existente"""
        try:
            correo = self.db.query(CorreosMicrosoftModel).filter(
                CorreosMicrosoftModel.message_id == message_id
            ).first()
            
            if correo:
                # Actualizar campos
                for campo, valor in datos_actualizacion.items():
                    if hasattr(correo, campo):
                        setattr(correo, campo, valor)
                
                correo.updated_at = datetime.now()
                self.db.commit()
                return correo.to_dict()
            
            return None
            
        except Exception as e:
            self.db.rollback()
            print(f"Error actualizando correo: {e}")
            return None
    
    # Query para obtener todos los message_ids existentes en BD
    def obtener_message_ids_existentes(self):
        """Obtiene todos los message_ids existentes en BD"""
        try:
            result = self.db.query(CorreosMicrosoftModel.message_id).all()
            return {row[0] for row in result}  # Set para búsqueda rápida
            
        except Exception as e:
            print(f"Error obteniendo message_ids existentes: {e}")
            return set()
    
    # Query para marcar un correo como procesado o cambiar su estado
    def marcar_correo_procesado(self, message_id, nuevo_estado='procesado'):
        """Marca un correo como procesado o cambia su estado"""
        return self.actualizar_correo(message_id, {'estado': nuevo_estado})
    
    # Query para obtener un ticket por su ticket_id (id de la tabla)
    def obtener_ticket_por_id(self, ticket_id):
        """
        Obtiene un ticket por su ticket_id (id de la tabla)
        """
        try:
            ticket = self.db.query(CorreosMicrosoftModel).filter(
                CorreosMicrosoftModel.id == ticket_id
            ).first()
            
            if ticket:
                return ticket.to_dict()
            
            return None
            
        except Exception as e:
            print(f"Error obteniendo ticket por ID {ticket_id}: {e}")
            return None

    # Query para obtener un correo por su message_id
    def obtener_correo_por_message_id(self, message_id):
        """
        Obtiene un correo por su message_id
        """
        try:
            correo = self.db.query(CorreosMicrosoftModel).filter(
                CorreosMicrosoftModel.message_id == message_id
            ).first()
            
            if correo:
                return correo.to_dict()
            
            return None
            
        except Exception as e:
            print(f"Error obteniendo correo por message_id {message_id}: {e}")
            return None

    # Query para registrar una respuesta enviada a un correo
    def registrar_respuesta_correo(self, message_id, respuesta, ticket_id=None):
        """
        Registra una respuesta enviada a un correo en la base de datos
        """
        try:
            # Por ahora solo actualizar el timestamp para indicar que se respondió
            datos_actualizacion = {
                'updated_at': datetime.now()
            }
            
            return self.actualizar_correo(message_id, datos_actualizacion)
            
        except Exception as e:
            print(f"Error registrando respuesta de correo: {e}")
            return None
    
    # Query para descartar un correo (marcarlo como inactivo)
    def descartar_correo(self, message_id):
        """Marca un correo como descartado (estado = 0) para que no aparezca en la bandeja"""
        try:
            resultado = self.actualizar_correo(message_id, {
                'activo': 0,
                'fecha_actualizacion': datetime.now()
            })
            
            if resultado:
                print(f"Correo {message_id} marcado como descartado")
                return resultado
            else:
                print(f"No se encontró el correo {message_id} para descartar")
                return None
                
        except Exception as e:
            print(f"Error descartando correo {message_id}: {e}")
            return None
    
    # Query para convertir un correo en ticket
    def convertir_correo_ticket(self, message_id):
        """Marca un correo como convertido a ticket (ticket = 1) y genera ticket_id"""
        try:
            resultado = self.actualizar_correo(message_id, {
                'ticket': 1,
                'fecha_actualizacion': datetime.now()
            })
            
            if resultado:
                # Generar ticket_id en formato TCK-XXXX basado en el ID del correo
                ticket_id_display = f"TCK-{resultado['id']:04d}"
                ticket_id_numero = str(resultado['id'])  # Solo el número puro
                
                print(f"Correo {message_id} convertido a ticket {ticket_id_display}")
                
                # Agregar ambos formatos al resultado
                resultado['ticket_id'] = ticket_id_numero  # Para uso interno
                resultado['ticket_id_display'] = ticket_id_display  # Para mostrar al usuario
                
                return resultado
            else:
                print(f"No se encontró el correo {message_id} para convertir")
                return None
                
        except Exception as e:
            print(f"Error convirtiendo correo {message_id} a ticket: {e}")
            return None
    
    # Query para obtener correos convertidos en tickets con filtrado optimizado por vista
    def obtener_tickets_correos(self, vista=None, limite=100, offset=0, tecnico_id=None):
        """
        Obtiene correos convertidos en tickets desde la base de datos
        Filtrado optimizado por vista para máximo rendimiento
        Incluye JOIN con IntranetEstadosTickets para obtener el nombre del estado
        """
        try:
            # Query base con JOINs: correos activos convertidos a tickets + información completa
            query = self.db.query(
                CorreosMicrosoftModel,
                IntranetEstadosTickets.nombre.label('estado_nombre'),
                IntranetUsuariosGestionTicModel.nombre.label('tecnico_nombre'),
                IntranetTipoPrioridadModel.nombre.label('prioridad_nombre'),
                IntranetTipoSoporteModel.nombre.label('tipo_soporte_nombre'),
                IntranetTipoTicketModel.nombre.label('tipo_ticket_nombre'),
                IntranetPerfilesMacroprocesoModel.nombre.label('macroproceso_nombre')
            ).outerjoin(
                IntranetEstadosTickets, 
                CorreosMicrosoftModel.estado == IntranetEstadosTickets.id
            ).outerjoin(
                IntranetUsuariosGestionTicModel,
                CorreosMicrosoftModel.asignado == IntranetUsuariosGestionTicModel.id
            ).outerjoin(
                IntranetTipoPrioridadModel,
                CorreosMicrosoftModel.prioridad == IntranetTipoPrioridadModel.id
            ).outerjoin(
                IntranetTipoSoporteModel,
                CorreosMicrosoftModel.tipo_soporte == IntranetTipoSoporteModel.id
            ).outerjoin(
                IntranetTipoTicketModel,
                CorreosMicrosoftModel.tipo_ticket == IntranetTipoTicketModel.id
            ).outerjoin(
                IntranetPerfilesMacroprocesoModel,
                CorreosMicrosoftModel.macroproceso == IntranetPerfilesMacroprocesoModel.id
            ).filter(
                CorreosMicrosoftModel.activo == 1,
                CorreosMicrosoftModel.ticket == 1
            )
            
            # Aplicar filtros específicos por vista
            if vista == 'todos':
                # Ya tenemos el filtro base
                pass
            elif vista == 'sin':
                # Sin asignar: donde asignado es NULL o vacío
                query = query.filter(
                    CorreosMicrosoftModel.asignado.is_(None)
                )
            elif vista == 'abiertos':
                # Estado = 1 (Abierto)
                query = query.filter(CorreosMicrosoftModel.estado == 1)
            elif vista == 'proceso':
                # Estado = 2 (En Proceso)
                query = query.filter(CorreosMicrosoftModel.estado == 2)
            elif vista == 'comp':
                # Estado = 4 (Completado)
                query = query.filter(CorreosMicrosoftModel.estado == 3)
            elif vista and vista.startswith('tecnico_'):
                # Filtro por técnico específico: tecnico_1, tecnico_2, etc.
                tecnico_id_from_vista = vista.replace('tecnico_', '')
                try:
                    tecnico_id_int = int(tecnico_id_from_vista)
                    query = query.filter(CorreosMicrosoftModel.asignado == tecnico_id_int)
                except ValueError:
                    # Si no es un número válido, no aplicar filtro
                    pass
            
            # Filtro adicional por tecnico_id específico (parámetro directo)
            if tecnico_id:
                query = query.filter(CorreosMicrosoftModel.asignado == tecnico_id)
            
            # Ordenar por fecha recibida (más recientes primero)
            query = query.order_by(CorreosMicrosoftModel.received_date.desc())
            
            # Obtener total para paginación (sin JOIN para mejor performance en count)
            count_query = self.db.query(CorreosMicrosoftModel).filter(
                CorreosMicrosoftModel.activo == 1,
                CorreosMicrosoftModel.ticket == 1
            )
            
            # Aplicar los mismos filtros para el conteo
            if vista == 'sin':
                count_query = count_query.filter(CorreosMicrosoftModel.asignado.is_(None))
            elif vista == 'abiertos':
                count_query = count_query.filter(CorreosMicrosoftModel.estado == 1)
            elif vista == 'proceso':
                count_query = count_query.filter(CorreosMicrosoftModel.estado == 2)
            elif vista == 'comp':
                count_query = count_query.filter(CorreosMicrosoftModel.estado == 3)
            elif vista and vista.startswith('tecnico_'):
                # Aplicar el mismo filtro de técnico para el conteo
                tecnico_id_from_vista = vista.replace('tecnico_', '')
                try:
                    tecnico_id_int = int(tecnico_id_from_vista)
                    count_query = count_query.filter(CorreosMicrosoftModel.asignado == tecnico_id_int)
                except ValueError:
                    pass
                    
            # Filtro adicional por tecnico_id para el conteo
            if tecnico_id:
                count_query = count_query.filter(CorreosMicrosoftModel.asignado == tecnico_id)
            
            total = count_query.count()
            
            # Aplicar paginación y obtener resultados
            resultados = query.offset(offset).limit(limite).all()
            
            # Convertir a formato frontend con información adicional de todos los JOINs
            tickets = []
            for correo, estado_nombre, tecnico_nombre, prioridad_nombre, tipo_soporte_nombre, tipo_ticket_nombre, macroproceso_nombre in resultados:
                ticket_data = correo.to_frontend_format()
                # Agregar información del estado
                ticket_data['estado_nombre'] = estado_nombre or '-'
                ticket_data['estadoTicket'] = estado_nombre or '-'  # Para compatibilidad
                # Agregar información del técnico asignado
                ticket_data['tecnico_nombre'] = tecnico_nombre or '-'
                ticket_data['asignadoNombre'] = tecnico_nombre or '-'  # Para compatibilidad
                # Agregar información de prioridad
                ticket_data['prioridad_nombre'] = prioridad_nombre or '-'
                # Agregar información de tipo de soporte
                ticket_data['tipo_soporte_nombre'] = tipo_soporte_nombre or '-'
                # Agregar información de tipo de ticket
                ticket_data['tipo_ticket_nombre'] = tipo_ticket_nombre or '-'
                # Agregar información de macroproceso
                ticket_data['macroproceso_nombre'] = macroproceso_nombre or '-'
                tickets.append(ticket_data)
            
            return {
                'tickets': tickets,
                'total': total,
                'limite': limite,
                'offset': offset,
                'vista': vista
            }
            
        except Exception as e:
            print(f"Error obteniendo tickets de correos: {e}")
            return {
                'tickets': [],
                'total': 0,
                'limite': limite,
                'offset': offset,
                'vista': vista
            }
    
    # Query para obtener todos los estados de tickets
    def obtener_estados_tickets(self):
        """
        Obtiene todos los estados de tickets disponibles desde IntranetEstadosTickets
        """
        try:
            estados = self.db.query(IntranetEstadosTickets).filter(
                IntranetEstadosTickets.estado == 1
            ).all()
            
            return [{'id': estado.id, 'nombre': estado.nombre} for estado in estados]
            
        except Exception as e:
            print(f"Error obteniendo estados de tickets: {e}")
            return []
    
    # Query para obtener todos los técnicos de gestión TIC
    def obtener_tecnicos_gestion_tic(self):
        """
        Obtiene todos los técnicos disponibles desde IntranetUsuariosGestionTicModel
        """
        try:
            tecnicos = self.db.query(IntranetUsuariosGestionTicModel).filter(
                IntranetUsuariosGestionTicModel.estado == 1
            ).all()
            
            return [{'id': tecnico.id, 'nombre': tecnico.nombre} for tecnico in tecnicos]
            
        except Exception as e:
            print(f"Error obteniendo técnicos de gestión TIC: {e}")
            return []
    
    # Querys para logs de sincronización
    def obtener_ultimo_sync_exitoso(self):
        """Obtiene información del último sync exitoso"""
        try:
            ultimo_sync = self.db.query(SyncLogModel).filter(
                SyncLogModel.estado == 'exitoso'
            ).order_by(SyncLogModel.fecha_fin.desc()).first()
            
            return ultimo_sync.to_dict() if ultimo_sync else None
            
        except Exception as e:
            print(f"Error obteniendo último sync: {e}")
            return None
    
    # Query para crear un nuevo log de sincronización
    def crear_log_sync(self, tipo_sync='incremental'):
        """Crea un nuevo registro de sincronización"""
        try:
            log_data = {
                'tipo_sync': tipo_sync,
                'fecha_inicio': datetime.now(),
                'estado': 1
            }
            
            nuevo_log = SyncLogModel(log_data)
            self.db.add(nuevo_log)
            self.db.commit()
            self.db.refresh(nuevo_log)
            
            return nuevo_log.id
            
        except Exception as e:
            self.db.rollback()
            print(f"Error creando log de sync: {e}")
            return None
    
    # Query para finalizar un log de sincronización
    def finalizar_log_sync(self, log_id, correos_nuevos=0, correos_actualizados=0, 
                          correos_eliminados=0, estado=1, mensaje_error=None):
        """Finaliza un log de sincronización"""
        try:
            log_sync = self.db.query(SyncLogModel).filter(
                SyncLogModel.id == log_id
            ).first()
            
            if log_sync:
                log_sync.fecha_fin = datetime.now()
                log_sync.correos_nuevos = correos_nuevos
                log_sync.correos_actualizados = correos_actualizados
                log_sync.correos_eliminados = correos_eliminados
                log_sync.estado = estado
                log_sync.mensaje_error = mensaje_error
                
                self.db.commit()
                return log_sync.to_dict()
            
            return None
            
        except Exception as e:
            self.db.rollback()
            print(f"Error finalizando log de sync: {e}")
            return None

    # Querys para obtener listas de prioridades, tipos de soporte, tipos de ticket y macroprocesos
    def obtener_prioridades(self):
        """
        Obtiene todas las prioridades disponibles desde IntranetPrioridades
        """
        try:
            prioridades = self.db.query(IntranetTipoPrioridadModel).filter(
                IntranetTipoPrioridadModel.estado == 1
            ).all()
            
            return [{'id': prioridad.id, 'nombre': prioridad.nombre} for prioridad in prioridades]
            
        except Exception as e:
            print(f"Error obteniendo prioridades: {e}")
            return []

    # Query para obtener tipos de soporte
    def obtener_tipo_soporte(self):
        """
        Obtiene todos los tipos de soporte disponibles desde IntranetTipoSoporte
        """
        try:
            tipos_soporte = self.db.query(IntranetTipoSoporteModel).filter(
                IntranetTipoSoporteModel.estado == 1
            ).all()
            
            return [{'id': tipo.id, 'nombre': tipo.nombre} for tipo in tipos_soporte]
            
        except Exception as e:
            print(f"Error obteniendo tipos de soporte: {e}")
            return []

    # Query para obtener tipos de ticket
    def obtener_tipo_ticket(self):
        """
        Obtiene todos los tipos de ticket disponibles desde IntranetTipoTicket
        """
        try:
            tipos_ticket = self.db.query(IntranetTipoTicketModel).filter(
                IntranetTipoTicketModel.estado == 1
            ).all()
            
            return [{'id': tipo.id, 'nombre': tipo.nombre} for tipo in tipos_ticket]
        except Exception as e:
            print(f"Error obteniendo tipos de ticket: {e}")
            return []

    # Query para obtener macroprocesos
    def obtener_macroprocesos(self):
        """
        Obtiene todos los macroprocesos disponibles (valores estáticos por ahora)
        """
        try:
            # Valores estáticos por ahora
            macroprocesos = self.db.query(IntranetPerfilesMacroprocesoModel).filter(
                IntranetPerfilesMacroprocesoModel.estado == 1
            ).all()
            return [{'id': macro.id, 'nombre': macro.nombre} for macro in macroprocesos]

        except Exception as e:
            print(f"Error obteniendo macroprocesos: {e}")
            return self.tools.output(500, "Error obteniendo macroprocesos.", {})

    # Query para filtrar tickets con optimización usando IDs exactos
    def filtrar_tickets_optimizado(self, filtros: dict):
        """
        Filtra tickets usando los campos reales de la tabla intranet_correos_microsoft
        Optimizado para usar los IDs exactos que envía el frontend
        
        Campos de la tabla:
        - ticket (0/1) - Solo tickets convertidos
        - asignado (ID del técnico)
        - prioridad (ID de prioridad)
        - tipo_soporte (ID de tipo soporte)
        - tipo_ticket (ID de tipo ticket) 
        - macroproceso (ID de macroproceso)
        - estado (ID numérico del estado)
        """
        try:
            # Query base con JOINs para obtener nombres
            base_query = """
            SELECT DISTINCT
                icm.id,
                icm.message_id,
                icm.subject,
                icm.from_name,
                icm.from_email,
                icm.body_content,
                icm.received_date,
                icm.created_at,
                icm.updated_at,
                icm.ticket,
                icm.estado,
                icm.asignado,
                icm.prioridad,
                icm.tipo_soporte,
                icm.tipo_ticket,
                icm.macroproceso,
                icm.fecha_vencimiento,
                icm.sla,
                
                -- JOINs para obtener nombres
                itp.nombre as prioridad_nombre,
                its.nombre as tipo_soporte_nombre,
                itt.nombre as tipo_ticket_nombre,
                ipm.nombre as macroproceso_nombre,
                iugt.nombre as asignado_nombre,
                
                -- Mapeo de estados
                CASE 
                    WHEN icm.estado = 1 THEN 'Abierto'
                    WHEN icm.estado = 2 THEN 'En Proceso' 
                    WHEN icm.estado = 3 THEN 'Completado'
                    WHEN icm.estado = 4 THEN 'Cerrado'
                    ELSE 'Abierto'
                END as estado_nombre

            FROM intranet_correos_microsoft icm
            
            -- LEFT JOINs para obtener nombres
            LEFT JOIN intranet_tipo_prioridad itp ON icm.prioridad = itp.id AND itp.estado = 1
            LEFT JOIN intranet_tipo_soporte its ON icm.tipo_soporte = its.id AND its.estado = 1  
            LEFT JOIN intranet_tipo_ticket itt ON icm.tipo_ticket = itt.id AND itt.estado = 1
            LEFT JOIN intranet_perfiles_macroproceso ipm ON icm.macroproceso = ipm.id AND ipm.estado = 1
            LEFT JOIN intranet_usuarios_gestion_tic iugt ON icm.asignado = iugt.id AND iugt.estado = 1
            
            WHERE icm.activo = 1 
            AND icm.ticket = 1
            """
            
            params = {}
            
            # 1. Filtro de vista base
            vista = filtros.get('vista', 'todos')
            if vista == 'sin':
                base_query += " AND icm.asignado IS NULL"
            elif vista == 'abiertos':
                base_query += " AND icm.estado = 1"
            elif vista == 'proceso':
                base_query += " AND icm.estado = 2"
            elif vista == 'comp':
                base_query += " AND icm.estado = 3"
            elif vista.startswith('tecnico_'):
                tecnico_id = int(vista.replace('tecnico_', ''))
                base_query += " AND icm.asignado = :tecnico_id"
                params['tecnico_id'] = tecnico_id
            
            # 2. Filtros específicos usando campos reales
            if filtros.get('q'):
                search_term = f"%{filtros['q']}%"
                base_query += """ AND (
                    CAST(icm.id AS NVARCHAR) LIKE :search_term OR
                    icm.subject LIKE :search_term OR  
                    icm.from_name LIKE :search_term OR
                    icm.from_email LIKE :search_term
                )"""
                params['search_term'] = search_term
                
            if filtros.get('estado'):
                base_query += " AND icm.estado = :estado_filtro"
                params['estado_filtro'] = filtros['estado']
                
            if filtros.get('asignado'):
                base_query += " AND icm.asignado = :asignado_filtro"
                params['asignado_filtro'] = filtros['asignado']
                
            if filtros.get('tipo_soporte'):
                base_query += " AND icm.tipo_soporte = :tipo_soporte_filtro"
                params['tipo_soporte_filtro'] = filtros['tipo_soporte']
                
            if filtros.get('macroproceso'):
                base_query += " AND icm.macroproceso = :macroproceso_filtro"
                params['macroproceso_filtro'] = filtros['macroproceso']
                
            if filtros.get('tipo_ticket'):
                base_query += " AND icm.tipo_ticket = :tipo_ticket_filtro"
                params['tipo_ticket_filtro'] = filtros['tipo_ticket']
            
            # 3. Contar total (antes de paginación)
            # Extraer solo la parte WHERE y filtros de la query base
            where_clause = ""
            if 'WHERE' in base_query:
                where_clause = "WHERE" + base_query.split('WHERE', 1)[1]
            
            count_query = f"""
            SELECT COUNT(DISTINCT icm.id) as total
            FROM intranet_correos_microsoft icm
            LEFT JOIN intranet_usuarios_gestion_tic iugt ON icm.asignado = iugt.id AND iugt.estado = 1
            {where_clause}
            """
            
            total_result = self.db.execute(text(count_query), params).fetchone()
            total = total_result[0] if total_result else 0
            
            # 4. Agregar ordenación y paginación (SQL Server syntax)
            limite = filtros.get('limite', 100)
            offset = filtros.get('offset', 0)
            
            base_query += f"""
            ORDER BY icm.created_at DESC
            OFFSET {offset} ROWS
            FETCH NEXT {limite} ROWS ONLY
            """
            
            # 5. Ejecutar query principal
            result = self.db.execute(text(base_query), params)
            tickets = []
            
            for row in result:
                ticket_dict = {
                    'id': row[0],
                    'message_id': row[1], 
                    'subject': row[2],
                    'from_name': row[3],
                    'from_email': row[4],
                    'body': row[5],
                    'received_at': row[6].strftime('%Y-%m-%d %H:%M:%S') if row[6] else None,
                    'created_at': row[7].strftime('%Y-%m-%d') if row[7] else None,
                    'updated_at': row[8].strftime('%Y-%m-%d %H:%M:%S') if row[8] else None,
                    'ticket_id': row[0],  # Usar ID como ticket_id
                    'ticket': row[9],
                    'estado': row[10],
                    'asignado': row[11],
                    'prioridad': row[12],
                    'tipo_soporte': row[13],
                    'tipo_ticket': row[14],
                    'macroproceso': row[15],
                    'fecha_vencimiento': row[16].strftime('%Y-%m-%d') if row[16] else None,
                    'sla': row[17],
                    'prioridad_nombre': row[18],
                    'tipo_soporte_nombre': row[19],
                    'tipo_ticket_nombre': row[20],
                    'macroproceso_nombre': row[21],
                    'asignadoNombre': row[22],
                    'estadoTicket': row[23]  # Nombre del estado mapeado
                }
                tickets.append(ticket_dict)
            
            # 6. Preparar respuesta
            return {
                'tickets': tickets,
                'total': total,
                'limite': filtros.get('limite', 100),
                'offset': filtros.get('offset', 0),
                'filtros_aplicados': {k: v for k, v in filtros.items() 
                                   if k not in ['limite', 'offset'] and v is not None}
            }
            
        except Exception as e:
            print(f"Error en filtrar_tickets_optimizado: {e}")
            raise e

    # ===== FUNCIONES PARA MANEJO DE RESPUESTAS EN HILOS =====
    
    # Query para obtener un ticket por su conversation_id
    def obtener_ticket_por_conversation_id(self, conversation_id):
        """
        Busca un ticket existente basado en el conversation_id
        Returns: dict con datos del ticket o None si no existe
        """
        try:
            if not conversation_id:
                return None
                
            # Por ahora buscaremos por similitud de asunto, ya que no tenemos conversation_id en BD
            # En el futuro se puede agregar la columna conversation_id
            print(f"🔍 Buscando ticket por conversation_id: {conversation_id}")
            
            # Buscaremos cualquier ticket existente (temporalmente deshabilitado)
            # TODO: Agregar columna conversation_id a la tabla
            return None
            
            result = self.db.execute(sql, {"conversation_id": conversation_id}).fetchone()
            
            if result:
                return {
                    'id': result[0],
                    'message_id': result[1],
                    'subject': result[2],
                    'from_email': result[3],
                    'from_name': result[4],
                    'conversation_id': result[5],
                    'created_at': result[6]
                }
                
            return None
            
        except Exception as e:
            print(f"Error en obtener_ticket_por_conversation_id: {e}")
            return None

    # Query para registrar una respuesta entrante en el historial del ticket
    def registrar_respuesta_entrante_ticket(self, respuesta_data):
        """
        Registra una respuesta entrante en el historial del ticket
        """
        try:
            # Por ahora, vamos a insertarlo como un correo normal pero marcado como respuesta
            # En el futuro se puede crear una tabla específica para respuestas
            
            # Crear entrada usando el constructor correcto del modelo
            correo_data = {
                'message_id': respuesta_data.get('message_id'),
                'subject': f"[RESPUESTA] {respuesta_data.get('subject', '')}",
                'from_email': respuesta_data.get('from_email'),
                'from_name': respuesta_data.get('from_name'),
                'received_date': respuesta_data.get('received_date'),
                'body_preview': respuesta_data.get('subject', '')[:100],
                'body_content': respuesta_data.get('body_content'),
                'estado': 2  # Estado 2 = Respuesta procesada (no aparece en buzón)
            }
            
            correo_respuesta = CorreosMicrosoftModel(correo_data)
            
            self.db.add(correo_respuesta)
            self.db.commit()
            
            print(f"✅ Respuesta registrada para ticket {respuesta_data.get('ticket_id')}")
            return True
            
        except Exception as e:
            print(f"Error registrando respuesta entrante: {e}")
            self.db.rollback()
            return False

    # Query para actualizar la fecha de última actividad de un ticket
    def actualizar_ultima_actividad_ticket(self, ticket_id):
        """
        Actualiza la fecha de última actividad de un ticket
        """
        try:
            sql = text("""
                UPDATE intranet_correos_microsoft 
                SET updated_at = NOW()
                WHERE id = :ticket_id
            """)
            
            self.db.execute(sql, {"ticket_id": ticket_id})
            self.db.commit()
            
            return True
            
        except Exception as e:
            print(f"Error actualizando última actividad: {e}")
            self.db.rollback()
            return False

    # Query para buscar tickets con subject similar
    def buscar_ticket_por_subject_similar(self, subject_limpio, from_email):
        """
        Busca tickets con subject similar al proporcionado
        Útil para detectar hilos cuando conversation_id no coincide
        """
        try:
            sql = text("""
                SELECT TOP 1 id, subject, from_email, conversation_id, created_at
                FROM intranet_correos_microsoft 
                WHERE subject LIKE :subject_pattern
                AND from_email = :from_email
                AND estado = 1
                AND created_at >= DATEADD(day, -7, GETDATE())
                ORDER BY created_at DESC
            """)
            
            # Buscar con patrón LIKE para subjects similares
            subject_pattern = f"%{subject_limpio}%"
            
            result = self.db.execute(sql, {
                "subject_pattern": subject_pattern,
                "from_email": from_email
            }).fetchone()
            
            if result:
                return {
                    'id': result[0],
                    'subject': result[1],
                    'from_email': result[2],
                    'conversation_id': result[3],
                    'created_at': result[4]
                }
                
            return None
            
        except Exception as e:
            print(f"Error buscando ticket por subject similar: {e}")
            return None

    # Query para buscar el ticket más reciente de un remitente específico
    def buscar_ticket_reciente_por_email(self, from_email, days=7):
        """
        Busca el ticket más reciente de un remitente específico
        """
        try:
            sql = text("""
                SELECT TOP 1 id, subject, from_email, conversation_id, created_at
                FROM intranet_correos_microsoft 
                WHERE from_email = :from_email
                AND estado = 1
                AND created_at >= DATEADD(day, :days_back, GETDATE())
                ORDER BY created_at DESC
            """)
            
            result = self.db.execute(sql, {
                "from_email": from_email,
                "days_back": -days
            }).fetchone()
            
            if result:
                return {
                    'id': result[0],
                    'subject': result[1],
                    'from_email': result[2],
                    'conversation_id': result[3],
                    'created_at': result[4]
                }
                
            return None
            
        except Exception as e:
            print(f"Error buscando ticket reciente por email: {e}")
            return None

    # Query para obtener métricas del dashboard
    def obtener_metricas_dashboard(self, fecha_inicio=None, fecha_fin=None):
        """
        Obtiene métricas del dashboard para tickets con las condiciones especificadas:
        - Total de tickets: activo=1 AND ticket=1
        - Gestión: tipo_ticket=1
        - Estratégicos: tipo_ticket=2
        - Prioridad alta: prioridad=3
        - Estados: Abiertos (estado=1), En proceso (estado=2), Completados (estado=3)
        - Top 3 tipos de soporte más frecuentes
        - Top 3 macroprocesos más frecuentes
        - Top 3 prioridades más frecuentes
        - Top 3 asignados más frecuentes
        - Distribución por tipo de ticket (Gestión y Estratégico)
        """
        try:
            # Opción 1: SQLAlchemy ORM (más legible, orientado a objetos)
            
            # Query base con filtros
            query = self.db.query(
                func.count().label('total_tickets'),
                func.sum(case((CorreosMicrosoftModel.tipo_ticket == 1, 1), else_=0)).label('gestion'),
                func.sum(case((CorreosMicrosoftModel.tipo_ticket == 2, 1), else_=0)).label('estrategicos'),
                func.sum(case((CorreosMicrosoftModel.prioridad == 3, 1), else_=0)).label('prioridad_alta'),
                func.sum(case((CorreosMicrosoftModel.estado == 1, 1), else_=0)).label('abiertos'),
                func.sum(case((CorreosMicrosoftModel.estado == 2, 1), else_=0)).label('en_proceso'),
                func.sum(case((CorreosMicrosoftModel.estado == 3, 1), else_=0)).label('completados')
            ).filter(
                CorreosMicrosoftModel.activo == 1,
                CorreosMicrosoftModel.ticket == 1
            )
            
            # Agregar filtros de fecha si se proporcionan
            if fecha_inicio:
                query = query.filter(func.date(CorreosMicrosoftModel.received_date_time) >= fecha_inicio)
            
            if fecha_fin:
                query = query.filter(func.date(CorreosMicrosoftModel.received_date_time) <= fecha_fin)
            
            # Ejecutar query
            result = query.one()
            
            # Query para obtener los 3 tipos de soporte más frecuentes
            query_tipos_soporte = self.db.query(
                CorreosMicrosoftModel.tipo_soporte,
                IntranetTipoSoporteModel.nombre.label('nombre_tipo_soporte'),
                func.count(CorreosMicrosoftModel.tipo_soporte).label('cantidad')
            ).join(
                IntranetTipoSoporteModel,
                CorreosMicrosoftModel.tipo_soporte == IntranetTipoSoporteModel.id
            ).filter(
                CorreosMicrosoftModel.activo == 1,
                CorreosMicrosoftModel.ticket == 1,
                CorreosMicrosoftModel.tipo_soporte.isnot(None),
                CorreosMicrosoftModel.tipo_soporte != 0
            )
            
            # Agregar filtros de fecha para tipos de soporte
            if fecha_inicio:
                query_tipos_soporte = query_tipos_soporte.filter(
                    func.date(CorreosMicrosoftModel.received_date_time) >= fecha_inicio
                )
            
            if fecha_fin:
                query_tipos_soporte = query_tipos_soporte.filter(
                    func.date(CorreosMicrosoftModel.received_date_time) <= fecha_fin
                )
            
            # Agrupar, ordenar y limitar a los 3 primeros
            tipos_soporte_result = query_tipos_soporte.group_by(
                CorreosMicrosoftModel.tipo_soporte,
                IntranetTipoSoporteModel.nombre
            ).order_by(
                func.count(CorreosMicrosoftModel.tipo_soporte).desc()
            ).limit(3).all()
            
            # Formatear tipos de soporte
            tipos_soporte = []
            for tipo in tipos_soporte_result:
                tipos_soporte.append({
                    'id': tipo[0],
                    'nombre': tipo[1],
                    'cantidad': int(tipo[2])
                })
            
            # Query para obtener los 3 macroprocesos más frecuentes
            query_macroprocesos = self.db.query(
                CorreosMicrosoftModel.macroproceso,
                IntranetPerfilesMacroprocesoModel.nombre.label('nombre_macroproceso'),
                func.count(CorreosMicrosoftModel.macroproceso).label('cantidad')
            ).join(
                IntranetPerfilesMacroprocesoModel,
                CorreosMicrosoftModel.macroproceso == IntranetPerfilesMacroprocesoModel.id
            ).filter(
                CorreosMicrosoftModel.activo == 1,
                CorreosMicrosoftModel.ticket == 1,
                CorreosMicrosoftModel.macroproceso.isnot(None),
                CorreosMicrosoftModel.macroproceso != 0
            )
            
            # Agregar filtros de fecha para macroprocesos
            if fecha_inicio:
                query_macroprocesos = query_macroprocesos.filter(
                    func.date(CorreosMicrosoftModel.received_date_time) >= fecha_inicio
                )
            
            if fecha_fin:
                query_macroprocesos = query_macroprocesos.filter(
                    func.date(CorreosMicrosoftModel.received_date_time) <= fecha_fin
                )
            
            # Agrupar, ordenar y limitar a los 3 primeros
            macroprocesos_result = query_macroprocesos.group_by(
                CorreosMicrosoftModel.macroproceso,
                IntranetPerfilesMacroprocesoModel.nombre
            ).order_by(
                func.count(CorreosMicrosoftModel.macroproceso).desc()
            ).limit(3).all()
            
            # Formatear macroprocesos
            macroprocesos = []
            for macro in macroprocesos_result:
                macroprocesos.append({
                    'id': macro[0],
                    'nombre': macro[1],
                    'cantidad': int(macro[2])
                })
            
            # Query para obtener las 3 prioridades más frecuentes
            query_prioridades = self.db.query(
                CorreosMicrosoftModel.prioridad,
                IntranetTipoPrioridadModel.nombre.label('nombre_prioridad'),
                func.count(CorreosMicrosoftModel.prioridad).label('cantidad')
            ).join(
                IntranetTipoPrioridadModel,
                CorreosMicrosoftModel.prioridad == IntranetTipoPrioridadModel.id
            ).filter(
                CorreosMicrosoftModel.activo == 1,
                CorreosMicrosoftModel.ticket == 1,
                CorreosMicrosoftModel.prioridad.isnot(None),
                CorreosMicrosoftModel.prioridad != 0
            )
            
            # Agregar filtros de fecha para prioridades
            if fecha_inicio:
                query_prioridades = query_prioridades.filter(
                    func.date(CorreosMicrosoftModel.received_date_time) >= fecha_inicio
                )
            
            if fecha_fin:
                query_prioridades = query_prioridades.filter(
                    func.date(CorreosMicrosoftModel.received_date_time) <= fecha_fin
                )
            
            # Agrupar, ordenar y limitar a los 3 primeros
            prioridades_result = query_prioridades.group_by(
                CorreosMicrosoftModel.prioridad,
                IntranetTipoPrioridadModel.nombre
            ).order_by(
                func.count(CorreosMicrosoftModel.prioridad).desc()
            ).limit(3).all()
            
            # Formatear prioridades
            prioridades = []
            for prio in prioridades_result:
                prioridades.append({
                    'id': prio[0],
                    'nombre': prio[1],
                    'cantidad': int(prio[2])
                })
            
            # Query para obtener los 3 asignados más frecuentes
            query_asignados = self.db.query(
                CorreosMicrosoftModel.asignado,
                IntranetUsuariosGestionTicModel.nombre.label('nombre_asignado'),
                func.count(CorreosMicrosoftModel.asignado).label('cantidad')
            ).join(
                IntranetUsuariosGestionTicModel,
                CorreosMicrosoftModel.asignado == IntranetUsuariosGestionTicModel.id
            ).filter(
                CorreosMicrosoftModel.activo == 1,
                CorreosMicrosoftModel.ticket == 1,
                CorreosMicrosoftModel.asignado.isnot(None),
                CorreosMicrosoftModel.asignado != 0
            )
            
            # Agregar filtros de fecha para asignados
            if fecha_inicio:
                query_asignados = query_asignados.filter(
                    func.date(CorreosMicrosoftModel.received_date_time) >= fecha_inicio
                )
            
            if fecha_fin:
                query_asignados = query_asignados.filter(
                    func.date(CorreosMicrosoftModel.received_date_time) <= fecha_fin
                )
            
            # Agrupar, ordenar y limitar a los 3 primeros
            asignados_result = query_asignados.group_by(
                CorreosMicrosoftModel.asignado,
                IntranetUsuariosGestionTicModel.nombre
            ).order_by(
                func.count(CorreosMicrosoftModel.asignado).desc()
            ).limit(3).all()
            
            # Formatear asignados
            asignados = []
            for asig in asignados_result:
                asignados.append({
                    'id': asig[0],
                    'nombre': asig[1],
                    'cantidad': int(asig[2])
                })
            
            if result:
                metricas = {
                    'totals': {
                        'total': int(result[0] or 0),
                        'gestion': int(result[1] or 0),
                        'estrategicos': int(result[2] or 0),
                        'prioridad_alta': int(result[3] or 0)
                    },
                    'estados': {
                        'abiertos': int(result[4] or 0),
                        'en_proceso': int(result[5] or 0),
                        'completados': int(result[6] or 0)
                    },
                    'tipos_soporte': tipos_soporte,
                    'macroprocesos': macroprocesos,
                    'prioridades': prioridades,
                    'asignados': asignados
                }
                
                return metricas
            
            # Si no hay resultados, devolver métricas vacías
            return {
                'totals': {
                    'total': 0,
                    'gestion': 0,
                    'estrategicos': 0,
                    'prioridad_alta': 0
                },
                'estados': {
                    'abiertos': 0,
                    'en_proceso': 0,
                    'completados': 0
                },
                'tipos_soporte': [],
                'macroprocesos': [],
                'prioridades': [],
                'asignados': []
            }
            
        except Exception as e:
            print(f"Error obteniendo métricas del dashboard: {e}")
            raise CustomException(f"Error obteniendo métricas: {str(e)}")
