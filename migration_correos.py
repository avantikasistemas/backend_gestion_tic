"""
Script de migración para crear las tablas de correos Microsoft
Ejecutar este script para crear las nuevas tablas en la base de datos
"""

from Config.db import engine, BASE
from backend.Models.IntranetCorreosMicrosoftModel import IntranetCorreosMicrosoftModel
from backend.Models.IntranetSyncLogModel import IntranetSyncLogModel
import sys

def crear_tablas():
    """Crea las tablas de correos Microsoft y sync log"""
    try:
        print("Iniciando creación de tablas...")
        
        # Crear todas las tablas definidas en los modelos
        BASE.metadata.create_all(bind=engine)
        
        print("✅ Tablas creadas exitosamente:")
        print("   - correos_microsoft")
        print("   - sync_log")
        print("\nLas tablas están listas para usar.")
        
    except Exception as e:
        print(f"❌ Error creando tablas: {e}")
        sys.exit(1)

def verificar_tablas():
    """Verifica que las tablas existan"""
    try:
        from sqlalchemy import inspect
        
        inspector = inspect(engine)
        tablas_existentes = inspector.get_table_names()
        
        tablas_requeridas = ['correos_microsoft', 'sync_log']
        tablas_faltantes = [tabla for tabla in tablas_requeridas if tabla not in tablas_existentes]
        
        if tablas_faltantes:
            print(f"⚠️  Tablas faltantes: {tablas_faltantes}")
            return False
        else:
            print("✅ Todas las tablas requeridas existen")
            return True
            
    except Exception as e:
        print(f"❌ Error verificando tablas: {e}")
        return False

if __name__ == "__main__":
    print("=== MIGRACIÓN DE BASE DE DATOS - CORREOS MICROSOFT ===\n")
    
    # Verificar si las tablas ya existen
    if verificar_tablas():
        print("\n🎉 Las tablas ya existen. No es necesario ejecutar migración.")
    else:
        print("\n📦 Creando tablas faltantes...")
        crear_tablas()
        
        # Verificar nuevamente
        if verificar_tablas():
            print("\n🎉 Migración completada exitosamente!")
        else:
            print("\n❌ Algo salió mal durante la migración.")