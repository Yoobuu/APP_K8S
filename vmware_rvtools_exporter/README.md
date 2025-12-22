# VMware RVTools Exporter (CLI)

Herramienta CLI para conectarse a vCenter/ESXi vía API y exportar un Excel (.xlsx) con la estructura de RVTools. Opcionalmente genera CSVs por hoja.

## Requisitos

- Python 3.9+
- Acceso a vCenter o ESXi

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Uso

### vCenter (autodiscovery .env)

```bash
python -m src.main \
  --out ./out/export.xlsx \
  --csv-dir ./out/csv
```

### ESXi (sin verificar TLS, autodiscovery .env)

```bash
python -m src.main \
  --insecure \
  --out ./out/export.xlsx
```

### Con archivo .env explícito

```bash
python -m src.main \
  --env-file /ruta/al/.env \
  --out ./out/export.xlsx
```

## Variables de entorno

El exporter busca un `.env` automáticamente en este orden (relativo a `vmware_rvtools_exporter/`):

1) `../backend/.env`
2) `../.env`
3) `./.env`
4) `../app_api/.env`
5) `../app_server/.env`

También puedes usar `--env-file` para indicar un path explícito.

Variables soportadas (ver `.env.example`):

- `VCENTER_URL`
- `VCENTER_USER`
- `VCENTER_PASSWORD`
- `VCENTER_INSECURE`
- `OUT_PATH` (opcional)
- `CSV_DIR` (opcional)

## Salida

- El Excel siempre incluye las 27 hojas requeridas con sus headers.
- Si pasas `--csv-dir`, se crea un CSV por hoja con los mismos headers.

## Notas

- `--insecure` deshabilita la verificación TLS solo si lo solicitas explícitamente.
- Esta fase usa collectors vacíos salvo `vSource` y `vMetaData`.
