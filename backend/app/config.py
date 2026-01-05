from app.settings import settings

# —————— Parámetros de conexión a vCenter ——————
# VCENTER_HOST : URL o dirección del servidor vCenter (incluye protocolo y puerto)
# VCENTER_USER : Nombre de usuario con permisos para la API de vCenter
# VCENTER_PASS : Contraseña asociada al usuario de vCenter
VCENTER_HOST = settings.vcenter_host
VCENTER_USER = settings.vcenter_user
VCENTER_PASS = settings.vcenter_pass

# —————— Configuración de JWT ——————
# SECRET_KEY                 : Clave secreta utilizada para firmar y verificar tokens JWT
# ALGORITHM                  : Algoritmo de cifrado empleado para los JWT
# ACCESS_TOKEN_EXPIRE_MINUTES: Duración (en minutos) antes de que el token caduque
SECRET_KEY = settings.secret_key
ALGORITHM = settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
