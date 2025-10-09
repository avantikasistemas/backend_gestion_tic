# 📧 Sistema de Gestión de Correos Microsoft Graph

## 🚀 Implementación Completada (Fases 1-3)

### 📊 **Nuevas Tablas Creadas**

#### `correos_microsoft`
- **id**: PK, BigInteger
- **message_id**: ID único de Microsoft (único)
- **subject**: Asunto del correo
- **from_email**: Email del remitente
- **from_name**: Nombre del remitente
- **received_date**: Fecha de recepción
- **body_preview**: Vista previa del contenido
- **body_content**: Contenido completo
- **estado**: 'nuevo', 'procesado', 'convertido_ticket'
- **hash_contenido**: Hash para detectar cambios
- **attachments_count**: Número de adjuntos
- **has_attachments**: Indica si tiene adjuntos
- **created_at**, **updated_at**: Timestamps

#### `sync_log`
- **id**: PK, BigInteger
- **tipo_sync**: 'incremental', 'completo'
- **fecha_inicio**, **fecha_fin**: Timestamps del proceso
- **correos_nuevos**, **correos_actualizados**: Contadores
- **estado**: 'exitoso', 'error', 'en_proceso'
- **mensaje_error**: Detalles del error si ocurre

### 🔧 **Nuevos Endpoints Disponibles**

1. **POST /obtener_correos**
   - Sincronización inteligente + retorna correos desde BD
   - Parámetro: `forzar_sync` (boolean)

2. **GET /obtener_correos_bd**
   - Solo obtiene desde BD (muy rápido)
   - Parámetros: `limite`, `offset`, `estado`

3. **POST /sincronizar_correos**
   - Fuerza sincronización completa

4. **POST /marcar_correo_procesado**
   - Cambia estado de correos
   - Parámetros: `messageId`, `estado`

### 🧠 **Lógica Inteligente Implementada**

#### **Sincronización Inteligente:**
1. **Primera vez**: Sync completo de todos los correos
2. **Subsecuentes**: Solo correos nuevos/modificados
3. **Detección de cambios**: Por hash de contenido
4. **Filtrado automático**: Excluye spam y correos automáticos

#### **Performance Optimizada:**
- ✅ Índices en campos clave
- ✅ Búsqueda por Set() para message_ids
- ✅ Paginación nativa
- ✅ Cache de attachments
- ✅ Logs de sincronización

### 📋 **Cómo Usar**

#### **1. Ejecutar Migración:**
```bash
cd backend
python migration_correos.py
```

#### **2. Endpoints Frontend:**

**Carga inicial rápida (desde BD):**
```javascript
const response = await axios.get('/obtener_correos_bd?limite=50&offset=0')
```

**Sincronización inteligente:**
```javascript
const response = await axios.post('/obtener_correos', { forzar_sync: false })
```

**Sincronización completa:**
```javascript
const response = await axios.post('/sincronizar_correos')
```

#### **3. Estados de Correos:**
- `'nuevo'`: Recién sincronizado
- `'procesado'`: Revisado por usuario
- `'convertido_ticket'`: Convertido a ticket

### 🎯 **Beneficios Obtenidos**

1. **Performance**: Carga inicial súper rápida desde BD
2. **Eficiencia**: Solo sincroniza correos nuevos/modificados
3. **Confiabilidad**: Historial completo, funciona offline
4. **Flexibilidad**: Estados personalizados, metadatos propios
5. **Escalabilidad**: Paginación eficiente, índices optimizados
6. **Monitoring**: Logs detallados de sincronización

### 🔄 **Flujo Recomendado Frontend**

1. **Carga inicial**: `GET /obtener_correos_bd` (rápido)
2. **Mostrar indicador**: "Última sync: hace X minutos"
3. **Sync en background**: `POST /obtener_correos` 
4. **Actualizar UI**: Con correos nuevos si los hay
5. **Marcar procesados**: `POST /marcar_correo_procesado`

### ⚡ **Próximos Pasos (Fase 4 - Opcional)**

- [ ] Mejorar UI con indicadores de estado
- [ ] Agregar filtros avanzados
- [ ] Implementar notificaciones de correos nuevos
- [ ] Añadir categorización automática
- [ ] Dashboard de estadísticas de sync

### 🔧 **Configuración Frontend**

El formato de respuesta mantiene compatibilidad con el código existente:

```javascript
// La respuesta incluye ahora:
{
  "status": 200,
  "message": "Sincronización incremental completada.",
  "data": {
    "emails": [...], // Mismo formato anterior
    "sync_stats": {
      "nuevos": 5,
      "actualizados": 2,
      "sin_cambios": 45
    },
    "tipo_sync": "incremental"
  }
}
```

¡Todo listo para usar! 🎉