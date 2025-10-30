"""Manual smoke script for GET /api/vms/{vm_id}/perf."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Consulta el endpoint /api/vms/{vm_id}/perf y muestra el payload."
    )
    parser.add_argument("vm_id", help="Identificador de la VM en vCenter (moid).")
    parser.add_argument(
        "--base-url",
        default=os.getenv("SMOKE_BASE_URL", "http://localhost:8000"),
        help="URL base de la API (por defecto: %(default)s o SMOKE_BASE_URL).",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("SMOKE_TOKEN"),
        help="Token Bearer para Authorization (o variable SMOKE_TOKEN).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.getenv("SMOKE_TIMEOUT", "10")),
        help="Timeout en segundos para la solicitud (por defecto: %(default)s).",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=int(os.getenv("SMOKE_WINDOW", "60")),
        help="Ventana en segundos para recopilar métricas (20-1800).",
    )
    parser.add_argument(
        "--idle-to-zero",
        action="store_true",
        help="Rellena con 0 los contadores de disco sin actividad (idle_to_zero).",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Imprime la respuesta raw (sin formatear JSON).",
    )
    parser.add_argument(
        "--by-disk",
        action="store_true",
        help="Incluye metricas por disco (instancias).",
    )
    return parser.parse_args()


def pretty_print(data: Any) -> None:
    if isinstance(data, (dict, list)):
        print(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(data)


def main() -> int:
    args = parse_args()
    url = args.base_url.rstrip("/") + f"/api/vms/{args.vm_id}/perf"

    headers = {"Accept": "application/json"}
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"

    params = {"window": args.window}
    if args.idle_to_zero:
        params["idle_to_zero"] = "true"
    if args.by_disk:
        params["by_disk"] = "true"

    try:
        response = requests.get(url, headers=headers, params=params, timeout=args.timeout)
    except requests.RequestException as exc:  # pragma: no cover - smoke script
        print(f"Error al conectar con {url}: {exc}", file=sys.stderr)
        return 2

    if not args.raw:
        print(f"GET {url} -> {response.status_code}")

    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        data = response.json()
        if args.raw:
            print(json.dumps(data, ensure_ascii=False))
        else:
            pretty_print(data)
    else:
        print(response.text)

    return 0 if response.ok else 1


if __name__ == "__main__":  # pragma: no cover - entrada script
    raise SystemExit(main())
