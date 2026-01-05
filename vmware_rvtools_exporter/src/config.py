import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import dotenv_values


URL_ALIASES = ["VCENTER_URL", "VCENTER_HOST", "VSPHERE_URL", "VMW_URL", "VCSA_URL"]
USER_ALIASES = [
    "VCENTER_USER",
    "VSPHERE_USER",
    "VMW_USER",
    "VCSA_USER",
    "USERNAME",
]
PASSWORD_ALIASES = [
    "VCENTER_PASSWORD",
    "VCENTER_PASS",
    "VSPHERE_PASSWORD",
    "VMW_PASSWORD",
    "VCSA_PASSWORD",
    "PASSWORD",
]
INSECURE_ALIASES = ["VCENTER_INSECURE", "VSPHERE_INSECURE", "VMW_INSECURE"]


@dataclass
class Config:
    server: str
    user: str
    password: str
    insecure: bool
    out_path: str
    csv_dir: Optional[str]
    debug: bool
    env_file_used: Optional[str]
    # vFileInfo options
    fileinfo_enabled: bool
    fileinfo_max_datastores: int
    fileinfo_max_files_per_datastore: int
    fileinfo_path: str
    fileinfo_timeout_sec: int
    fileinfo_include_pattern: Optional[str]
    fileinfo_exclude_pattern: Optional[str]
    # vHealth options
    health_events_enabled: bool
    health_events_max_per_host: int


def _env_bool(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="VMware RVTools Exporter")
    parser.add_argument("--server", help="vCenter/ESXi URL (https://host)")
    parser.add_argument("--user", help="Usuario")
    parser.add_argument("--password", help="Password")
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Deshabilita verificacion TLS (solo si es necesario)",
    )
    parser.add_argument("--out", dest="out_path", help="Ruta de salida .xlsx")
    parser.add_argument("--csv-dir", dest="csv_dir", help="Directorio para CSVs")
    parser.add_argument("--debug", action="store_true", help="Logs en modo debug")
    parser.add_argument(
        "--env-file",
        dest="env_file",
        help="Ruta a archivo .env (si no se especifica, se autodetecta)",
    )
    
    # vFileInfo flags
    parser.add_argument("--fileinfo-enabled", action="store_true", help="Habilita escaneo de datastore files (lento)")
    parser.add_argument("--fileinfo-max-datastores", type=int, default=3, help="Max datastores a escanear")
    parser.add_argument("--fileinfo-max-files-per-datastore", type=int, default=200, help="Max archivos por datastore")
    parser.add_argument("--fileinfo-path", default="/", help="Path raiz para buscar")
    parser.add_argument("--fileinfo-timeout-sec", type=int, default=30, help="Timeout segundos por datastore search")
    parser.add_argument("--fileinfo-include-pattern", help="Regex para incluir archivos")
    parser.add_argument("--fileinfo-exclude-pattern", help="Regex para excluir archivos")

    # vHealth flags
    parser.add_argument("--health-events-enabled", action="store_true", help="Habilita consulta de EventManager para vHealth")
    parser.add_argument("--health-events-max-per-host", type=int, default=30, help="Max eventos recientes por host")

    return parser.parse_args()


def _env_candidates(base_dir: Path) -> List[Path]:
    return [
        base_dir / ".." / "backend" / ".env",
        base_dir / ".." / ".env",
        base_dir / ".env",
        base_dir / ".." / "app_api" / ".env",
        base_dir / ".." / "app_server" / ".env",
    ]


def _resolve_env_file(
    env_file: Optional[str], base_dir: Path, needs_env: bool
) -> Tuple[Optional[Path], List[Path]]:
    attempted = []

    if env_file:
        candidate = Path(env_file)
        attempted.append(candidate)
        if not candidate.is_file():
            raise RuntimeError(f"No se encontro .env en: {candidate}")
        return candidate, attempted

    if not needs_env:
        return None, attempted

    for candidate in _env_candidates(base_dir):
        attempted.append(candidate)
        if candidate.is_file():
            return candidate, attempted

    return None, attempted


def _read_env_values(env_file: Optional[Path]) -> Dict[str, str]:
    if env_file is None:
        return {}
    values = dotenv_values(env_file)
    normalized = {}
    for key, value in values.items():
        if value is None:
            continue
        normalized[key] = str(value).strip()
    return normalized


def _resolve_alias_value(aliases: List[str], env_values: Dict[str, str]) -> Optional[str]:
    resolved = None
    for key in aliases:
        value = env_values.get(key)
        if value:
            resolved = value
            break

    for key in aliases:
        value = os.environ.get(key)
        if value:
            return value.strip()

    return resolved


def _resolve_plain_value(key: str, env_values: Dict[str, str]) -> Optional[str]:
    resolved = env_values.get(key)
    env_override = os.environ.get(key)
    if env_override:
        return env_override.strip()
    return resolved


def load_config(args: argparse.Namespace) -> Config:
    base_dir = Path(__file__).resolve().parent.parent

    server_cli = (args.server or "").strip()
    user_cli = (args.user or "").strip()
    password_cli = (args.password or "").strip()

    needs_env = not (server_cli and user_cli and password_cli)
    env_file, attempted = _resolve_env_file(args.env_file, base_dir, needs_env)

    if env_file is None and needs_env:
        attempted_list = ", ".join(str(path) for path in attempted)
        raise RuntimeError(
            "No se encontro ningun .env. Rutas intentadas: " + attempted_list
        )

    env_values = _read_env_values(env_file)

    server_env = _resolve_alias_value(URL_ALIASES, env_values)
    user_env = _resolve_alias_value(USER_ALIASES, env_values)
    password_env = _resolve_alias_value(PASSWORD_ALIASES, env_values)
    insecure_env = _resolve_alias_value(INSECURE_ALIASES, env_values)

    server = server_cli or (server_env or "")
    user = user_cli or (user_env or "")
    password = password_cli or (password_env or "")

    if args.insecure:
        insecure = True
    else:
        insecure = _env_bool(insecure_env)

    out_path = (
        args.out_path
        or _resolve_plain_value("OUT_PATH", env_values)
        or "./out/rvtools_export.xlsx"
    )
    csv_dir = args.csv_dir or _resolve_plain_value("CSV_DIR", env_values)
    debug = args.debug

    return Config(
        server=server,
        user=user,
        password=password,
        insecure=insecure,
        out_path=out_path,
        csv_dir=csv_dir,
        debug=debug,
        env_file_used=str(env_file) if env_file else None,
        fileinfo_enabled=args.fileinfo_enabled,
        fileinfo_max_datastores=args.fileinfo_max_datastores,
        fileinfo_max_files_per_datastore=args.fileinfo_max_files_per_datastore,
        fileinfo_path=args.fileinfo_path,
        fileinfo_timeout_sec=args.fileinfo_timeout_sec,
        fileinfo_include_pattern=args.fileinfo_include_pattern,
        fileinfo_exclude_pattern=args.fileinfo_exclude_pattern,
        health_events_enabled=args.health_events_enabled,
        health_events_max_per_host=args.health_events_max_per_host,
    )