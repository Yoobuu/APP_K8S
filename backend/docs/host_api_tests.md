# Pruebas de endpoints de hosts ESXi

## Contexto
- Backend corriendo en `http://localhost:8000` con autenticación JWT (`admin/1234`).
- Todas las llamadas incluyen `Authorization: Bearer <token>`.

## PRUEBA 1 — GET /api/hosts (10 veces)
Comando:
```
for i in {1..10}; do curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/hosts/; done
```
Resultado: 10/10 respuestas `200`.

## PRUEBA 2 — Detalles en paralelo
Comando (ejecutado en paralelo):
```
curl -s -w "h1360 status=%{http_code} time=%{time_total}\n" -o /tmp/h1360_detail.json http://localhost:8000/api/hosts/host-1360
curl -s -w "h445  status=%{http_code} time=%{time_total}\n" -o /tmp/h445_detail.json  http://localhost:8000/api/hosts/host-445
```
Resultados:
- host-1360 → `status=200`, `time=3.48s`
- host-445  → `status=200`, `time=3.62s`

## PRUEBA 3 — Deep en paralelo
Comando (ejecutado en paralelo, timeout 240s):
```
curl -s -m 240 -w "h1360 status=%{http_code} time=%{time_total}\n" -o /tmp/h1360_deep.json http://localhost:8000/api/hosts/host-1360/deep
curl -s -m 240 -w "h8096 status=%{http_code} time=%{time_total}\n" -o /tmp/h8096_deep.json http://localhost:8000/api/hosts/host-8096/deep
```
Resultados:
- host-1360/deep → `status=200`, `time=2.72s`
- host-8096/deep → `status=200`, `time=3.99s`

## Observaciones
- `/api/hosts` redirige (307) sin el slash final; con `.../hosts/` responde 200 de forma estable.
- Las llamadas deep completan en pocos segundos con el filtro aplicado (sin colgues).
