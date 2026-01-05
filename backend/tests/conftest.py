from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.audit.models import AuditLog  # noqa: F401  # ensure table registration
from app.auth.user_model import User, UserRole  # noqa: F401
from app.db import get_session as app_get_session, set_engine
from app.dependencies import (
    AuditRequestContext,
    get_current_user,
    get_request_audit_context,
    require_superadmin,
)
from app.main import app
from app.notifications.models import Notification  # noqa: F401
from app.permissions.models import Permission, RolePermission, UserPermission  # noqa: F401
from app.system_settings.models import SystemSettings  # noqa: F401


@pytest.fixture(scope="function")
def test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    try:
        yield engine
    finally:
        SQLModel.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def client(test_engine):
    original_testing = os.environ.get("TESTING")
    os.environ["TESTING"] = "1"
    set_engine(test_engine)

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    def override_require_superadmin():
        return User(id=1, username="superadmin", role=UserRole.SUPERADMIN)

    def override_get_current_user():
        return User(id=1, username="superadmin", role=UserRole.SUPERADMIN)

    def override_audit_context():
        return AuditRequestContext(ip=None, user_agent=None, correlation_id="test-correlation")

    app.dependency_overrides[app_get_session] = override_get_session
    app.dependency_overrides[require_superadmin] = override_require_superadmin
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_request_audit_context] = override_audit_context

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    set_engine(None)
    if original_testing is None:
        os.environ.pop("TESTING", None)
    else:
        os.environ["TESTING"] = original_testing


@pytest.fixture(scope="function")
def session(test_engine):
    with Session(test_engine) as session:
        yield session
