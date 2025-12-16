from __future__ import annotations

from sqlmodel import select

from app.auth.user_model import User, UserRole
from app.dependencies import get_current_user
from app.permissions.models import Permission, PermissionCode, RolePermission, UserPermission
from app.permissions.service import ROLE_DEFAULT_PERMISSIONS, ensure_default_permissions, user_effective_permissions


def test_seed_permissions_idempotent(session):
    ensure_default_permissions(session)
    first_perm_count = len(session.exec(select(Permission)).all())
    first_role_pairs = len(session.exec(select(RolePermission)).all())

    ensure_default_permissions(session)

    second_perm_count = len(session.exec(select(Permission)).all())
    second_role_pairs = len(session.exec(select(RolePermission)).all())

    assert first_perm_count == len(PermissionCode)
    assert second_perm_count == len(PermissionCode)
    expected_pairs = sum(len(perms) for perms in ROLE_DEFAULT_PERMISSIONS.values())
    assert first_role_pairs == expected_pairs
    assert second_role_pairs == expected_pairs


def test_user_effective_permissions_with_overrides(session):
    ensure_default_permissions(session)
    user = User(username="alice", hashed_password="x", role=UserRole.USER)
    session.add(user)
    session.commit()
    session.refresh(user)

    base = user_effective_permissions(user, session)
    assert PermissionCode.VMS_VIEW.value in base
    assert PermissionCode.HYPERV_VIEW.value in base
    assert PermissionCode.NOTIFICATIONS_VIEW.value not in base

    session.add_all(
        [
            UserPermission(
                user_id=user.id,
                permission_code=PermissionCode.VMS_VIEW.value,
                granted=False,
            ),
            UserPermission(
                user_id=user.id,
                permission_code=PermissionCode.NOTIFICATIONS_VIEW.value,
                granted=True,
            ),
        ]
    )
    session.commit()

    updated = user_effective_permissions(user, session)
    assert PermissionCode.VMS_VIEW.value not in updated
    assert PermissionCode.NOTIFICATIONS_VIEW.value in updated


def test_permission_enforcement_on_route(client, session):
    ensure_default_permissions(session)
    user = User(id=10, username="bob", hashed_password="x", role=UserRole.USER)
    session.add(user)
    session.commit()

    def override_current_user():
        return user

    client.app.dependency_overrides[get_current_user] = override_current_user
    try:
        response = client.get("/api/notifications")
        assert response.status_code == 403

        session.add(
            UserPermission(
                user_id=user.id,
                permission_code=PermissionCode.NOTIFICATIONS_VIEW.value,
                granted=True,
            )
        )
        session.commit()

        response_allowed = client.get("/api/notifications")
        assert response_allowed.status_code == 200
    finally:
        client.app.dependency_overrides.pop(get_current_user, None)
