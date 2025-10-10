from Utils.tools import Tools, CustomException
from sqlalchemy import text, func
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
    
    def generar_hash_contenido(self, subject, body_preview, from_email):
        """Genera un hash del contenido del correo para detectar cambios"""
        contenido = f"{subject}{body_preview}{from_email}"
        return hashlib.sha256(contenido.encode()).hexdigest()
    
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
    
    def obtener_message_ids_existentes(self):
        """Obtiene todos los message_ids existentes en BD"""
        try:
            result = self.db.query(CorreosMicrosoftModel.message_id).all()
            return {row[0] for row in result}  # Set para búsqueda rápida
            
        except Exception as e:
            print(f"Error obteniendo message_ids existentes: {e}")
            return set()
    
    def marcar_correo_procesado(self, message_id, nuevo_estado='procesado'):
        """Marca un correo como procesado o cambia su estado"""
        return self.actualizar_correo(message_id, {'estado': nuevo_estado})
    
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
    
    def convertir_correo_ticket(self, message_id):
        """Marca un correo como convertido a ticket (ticket = 1)"""
        try:
            resultado = self.actualizar_correo(message_id, {
                'ticket': 1,
                'fecha_actualizacion': datetime.now()
            })
            
            if resultado:
                print(f"Correo {message_id} marcado como convertido a ticket")
                return resultado
            else:
                print(f"No se encontró el correo {message_id} para convertir")
                return None
                
        except Exception as e:
            print(f"Error convirtiendo correo {message_id} a ticket: {e}")
            return None
    
    def obtener_tickets_correos(self, vista=None, limite=100, offset=0):
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
