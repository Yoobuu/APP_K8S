# backend/scripts/add_audit_table_sqlite.py
import os, sys
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(CURRENT_DIR)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from sqlmodel import SQLModel
from app.db import engine
from app.audit.models import AuditLog  # side-effect: registra el modelo

def main():
    SQLModel.metadata.create_all(engine)
    print("Tabla AuditLog creada o ya existente.")

if __name__ == "__main__":
    main()
