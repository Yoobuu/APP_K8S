import ssl
from urllib.parse import urlparse

from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim


def _parse_server(server: str):
    if "://" not in server:
        server = f"https://{server}"

    parsed = urlparse(server)
    host = parsed.hostname
    port = parsed.port

    if not host:
        raise ValueError(f"Servidor invalido: {server}")

    if port is None:
        port = 443 if parsed.scheme == "https" else 80

    return host, port


def connect(server: str, user: str, password: str, insecure: bool):
    host, port = _parse_server(server)

    ssl_context = None
    if insecure:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

    try:
        service_instance = SmartConnect(
            host=host,
            user=user,
            pwd=password,
            port=port,
            sslContext=ssl_context,
        )
    except Exception as exc:
        raise ConnectionError(f"No se pudo conectar a {server}: {exc}") from exc

    if not isinstance(service_instance, vim.ServiceInstance):
        raise ConnectionError("No se obtuvo una instancia de servicio valida")

    return service_instance


def disconnect(service_instance):
    if service_instance is not None:
        Disconnect(service_instance)
