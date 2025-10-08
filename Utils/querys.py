from Utils.tools import Tools, CustomException
from sqlalchemy import text
from datetime import datetime, date
from Models.IntranetGraphTokenModel import IntranetGraphTokenModel as TokenModel

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
