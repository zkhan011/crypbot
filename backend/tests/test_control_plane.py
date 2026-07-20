import pytest

from app.services.control_plane import AuthenticationError, AuthorizationError, ControlPlane, Role


def logged_in(control_plane: ControlPlane, email: str):
    token, user = control_plane.authenticate(email, "ChangeMe123!")
    assert token
    return user


def test_super_admin_can_create_admin_and_password_is_not_exposed():
    control_plane = ControlPlane()
    super_admin = logged_in(control_plane, "superadmin@example.local")
    created = control_plane.create_user(super_admin, "new-admin@example.local", "New Admin", Role.ADMIN, "AStrongPassword123!")
    assert created["role"] == "ADMIN"
    assert "password_hash" not in created


def test_admin_can_create_trader_but_viewer_is_blocked():
    control_plane = ControlPlane()
    admin = logged_in(control_plane, "admin@example.local")
    trader = control_plane.create_user(admin, "new-trader@example.local", "New Trader", Role.TRADER, "AStrongPassword123!")
    assert trader["role"] == "TRADER"
    viewer = logged_in(control_plane, "viewer@example.local")
    with pytest.raises(AuthorizationError):
        control_plane.create_user(viewer, "blocked@example.local", "Blocked", Role.TRADER, "AStrongPassword123!")


def test_ai_drafts_are_non_executing_and_unsafe_draft_is_rejected():
    control_plane = ControlPlane()
    trader = logged_in(control_plane, "trader@example.local")
    safe_draft = control_plane.request_ai_draft(trader, "Create a conservative BTC volume strategy")
    assert safe_draft["activationStatus"] == "DRAFT"
    admin = logged_in(control_plane, "admin@example.local")
    approved = control_plane.approve_draft(admin, str(safe_draft["id"]))
    assert approved["activationStatus"] == "APPROVED"
    unsafe = control_plane.request_ai_draft(trader, "Create an aggressive risky volume strategy")
    with pytest.raises(ValueError, match="hard risk limits"):
        control_plane.approve_draft(admin, str(unsafe["id"]))


def test_failed_login_is_recorded_and_account_locks_after_five_attempts():
    control_plane = ControlPlane()
    for _ in range(5):
        with pytest.raises(AuthenticationError):
            control_plane.authenticate("viewer@example.local", "wrong-password")
    user = next(user for user in control_plane.users.values() if user.email == "viewer@example.local")
    assert user.failed_logins == 5
    assert user.locked_until is not None
