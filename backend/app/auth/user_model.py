from datetime import datetime, timezone
from sqlmodel import Field, SQLModel


# —————— Definición del modelo de usuario ——————
class User(SQLModel, table=True):
    """
    Representa la tabla 'User' en la base de datos.

    Campos:
    - id             : Clave primaria autogenerada para cada usuario.
    - username       : Nombre de usuario único, indexado para búsquedas.
    - hashed_password: Contraseña almacenada de forma segura (hasheada).
    """
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    must_change_password: bool = Field(default=False, nullable=False)
    password_last_set_at: datetime | None = Field(default=None, nullable=True)

    def mark_password_changed(self) -> None:
        """Update password change bookkeeping."""
        self.must_change_password = False
        self.password_last_set_at = datetime.now(timezone.utc)

    def mark_password_reset(self) -> None:
        """Flag password for replacement after admin reset."""
        self.must_change_password = True
        self.password_last_set_at = datetime.now(timezone.utc)
