# Reconciliación automática de notificaciones

El job horario de reconciliación mantiene los estados de las notificaciones coherentes con las anomalías detectadas
por el scraper de métricas. Cuando una métrica vuelve a la normalidad la notificación asociada pasa a `CLEARED` de forma
automática y queda auditada, sin eliminar registros históricos.

## Claves canónicas

Cada alerta se identifica por la combinación:

```
(provider, vm_name, metric, env?)  # env solo si existe
```

El reconciliador normaliza `provider` y `metric` a minúsculas (enum), el `vm_name` a minúsculas para la clave interna y
el `env` en mayúsculas. Esto garantiza que los mismos eventos se reconozcan aunque varíe el casing en el scrape.

## Flujo del job

1. Se ejecuta `collect_all_samples()` y se evalúan las anomalías con el mismo umbral (85%) que la fase de creación.
2. Se llama a `reconcile_notifications(current_anomalies, now_utc)` que:
   - Marca como `CLEARED` las notificaciones `OPEN`/`ACK` que ya no aparecen.
   - Refresca valores/umbral/discos para las que se mantienen.
   - Crea nuevas notificaciones `OPEN` para anomalías recién detectadas.
   - No toca notificaciones ya `CLEARED` ni `archived`.
3. Todas las transiciones generan auditoría con actor `system`:
   - `NOTIFICATION_CREATED` para nuevas alertas.
   - `NOTIFICATION_UPDATED` cuando se refrescan datos.
   - `NOTIFICATION_CLEARED` cuando desaparece la anomalía.
4. El job registra un resumen adicional (`notifications.reconcile`) con los contadores resultantes.

La operación es idempotente: repetir la reconciliación con el mismo input no crea duplicados ni cambia estados.

## Feature flags

| Variable | Descripción | Valor por defecto |
| --- | --- | --- |
| `NOTIFS_AUTOCLEAR_ENABLED` | Activa/desactiva el job de reconciliación. | `true` (deshabilitado automáticamente cuando `TESTING=1`). |
| `NOTIFS_RETENTION_DAYS` | Ventana en días antes de marcar notificaciones `CLEARED` como `archived`. | `180` |

## Retención (archivado soft)

El script `app/scripts/archive_notifications.py` marca como `archived=true` las notificaciones `CLEARED` con
`created_at` anterior al corte calculado (`now - NOTIFS_RETENTION_DAYS`). No elimina registros; sólo permite filtrarlos
en futuras consultas o tareas batch.

## Reportes

El reconciliador devuelve un `ReconciliationReport` con:

```
created, cleared, updated, preserved
created_ids, cleared_ids, ...
```

Este payload se usa tanto en logs como en la entrada de auditoría `notifications.reconcile`.
