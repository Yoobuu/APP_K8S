import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .config import load_config, parse_args
from .collectors import COLLECTORS, CollectorContext
from .diagnostics import Diagnostics
from .schemas import SCHEMAS, SHEET_ORDER
from .vmware_client import connect, disconnect
from .writer.csv_writer import write_csv
from .writer.excel_writer import write_excel


def setup_logging(debug: bool) -> logging.Logger:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")
    return logging.getLogger("rvtools_exporter")


def _validate_config(config, logger: logging.Logger) -> bool:
    missing = []
    if not config.server:
        missing.append("--server o VCENTER_URL")
    if not config.user:
        missing.append("--user o VCENTER_USER")
    if not config.password:
        missing.append("--password o VCENTER_PASSWORD")

    if missing:
        logger.error("Faltan parametros requeridos: %s", ", ".join(missing))
        return False

    return True


def _mask_user(user: str) -> str:
    if not user:
        return ""
    if "@" in user:
        name, domain = user.split("@", 1)
        if not name:
            return f"***@{domain}"
        visible = name[:2] if len(name) > 1 else name[:1]
        return f"{visible}***@{domain}"
    visible = user[:2] if len(user) > 1 else user[:1]
    return f"{visible}***"


def _extract_server_host(server: str) -> str:
    if not server:
        return ""
    if "://" not in server:
        server = f"https://{server}"
    parsed = urlparse(server)
    return parsed.hostname or server


def _write_diagnostics(out_path: Path, diagnostics: Diagnostics, logger: logging.Logger) -> None:
    diagnostics_path = out_path.parent / "diagnostics.json"
    try:
        with diagnostics_path.open("w", encoding="utf-8") as handle:
            json.dump(diagnostics.to_dict(), handle, indent=2, sort_keys=True)
    except Exception as exc:
        logger.debug("No se pudo escribir diagnostics.json: %s", exc)


def _print_summary(diagnostics: Diagnostics, logger: logging.Logger) -> None:
    for sheet_name in SHEET_ORDER:
        stats = diagnostics.get_sheet_stats(sheet_name)
        logger.info(
            "Resumen %s: attempted=%s success=%s empty=%s no_permission=%s invalid_property=%s not_found=%s other_error=%s",
            sheet_name,
            stats.attempted_count,
            stats.success_count,
            stats.empty_count,
            stats.no_permission_count,
            stats.invalid_property_count,
            stats.not_found_count,
            stats.other_error_count,
        )


def main() -> int:
    args = parse_args()
    logger = setup_logging(args.debug)

    try:
        config = load_config(args)
    except Exception as exc:
        logger.error(str(exc))
        return 2

    if not _validate_config(config, logger):
        return 2

    out_path = Path(config.out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    csv_dir = None
    if config.csv_dir:
        csv_dir = Path(config.csv_dir)
        csv_dir.mkdir(parents=True, exist_ok=True)

    if config.env_file_used:
        logger.info(
            "Cargadas credenciales desde: %s (user: %s)",
            config.env_file_used,
            _mask_user(config.user),
        )

    diagnostics = Diagnostics(SHEET_ORDER)
    diagnostics.set_runtime_config(
        {
            "env_file_used": config.env_file_used,
            "server_host": _extract_server_host(config.server),
            "insecure": config.insecure,
        }
    )
    service_instance = None
    exit_code = 1

    try:
        logger.info("Conectando a %s", config.server)
        service_instance = connect(
            server=config.server,
            user=config.user,
            password=config.password,
            insecure=config.insecure,
        )
        content = service_instance.RetrieveContent()
        connected_at = datetime.now(timezone.utc).isoformat()

        context = CollectorContext(
            service_instance=service_instance,
            content=content,
            config=config,
            logger=logger,
            connected_at=connected_at,
            diagnostics=diagnostics,
        )

        data_by_sheet = {}
        for sheet_name in SHEET_ORDER:
            collector = COLLECTORS.get(sheet_name)
            if collector is None:
                logger.warning("Collector faltante para %s", sheet_name)
                data = []
            else:
                try:
                    data = collector(context) or []
                except Exception as exc:
                    logger.error("Error en collector %s: %s", sheet_name, exc)
                    data = []

            data_by_sheet[sheet_name] = data
            stats = diagnostics.get_sheet_stats(sheet_name)
            if (
                not data
                and stats.attempted_count == 0
                and stats.success_count == 0
                and stats.total_error_count == 0
            ):
                diagnostics.add_empty(sheet_name)

        write_excel(out_path, SCHEMAS, data_by_sheet, SHEET_ORDER)
        if csv_dir:
            write_csv(csv_dir, SCHEMAS, data_by_sheet, SHEET_ORDER)

        logger.info("Export completado: %s", out_path)
        if csv_dir:
            logger.info("CSVs generados en: %s", csv_dir)

        total_vms = max(
            len(data_by_sheet.get("vInfo", [])),
            len(data_by_sheet.get("vCPU", [])),
            len(data_by_sheet.get("vMemory", [])),
            len(data_by_sheet.get("vTools", [])),
        )
        logger.info(
            "Resumen VMs: total_vms=%s vInfo=%s vCPU=%s vMemory=%s vDisk=%s vNetwork=%s vTools=%s",
            total_vms,
            len(data_by_sheet.get("vInfo", [])),
            len(data_by_sheet.get("vCPU", [])),
            len(data_by_sheet.get("vMemory", [])),
            len(data_by_sheet.get("vDisk", [])),
            len(data_by_sheet.get("vNetwork", [])),
            len(data_by_sheet.get("vTools", [])),
        )

        exit_code = 0
    except Exception as exc:
        logger.error("Fallo la exportacion: %s", exc)
    finally:
        _write_diagnostics(out_path, diagnostics, logger)
        _print_summary(diagnostics, logger)
        disconnect(service_instance)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
