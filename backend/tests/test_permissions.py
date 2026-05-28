from uuid import uuid4

from app.core.permissions import can_access_event
from app.models.admin_account import AdminRole


class _Admin:
    def __init__(self, id, role):
        self.id = id
        self.role = role


class _Event:
    def __init__(self, id, owner_id, controllers=None):
        self.id = id
        self.owner_id = owner_id
        self.controllers = controllers or []


class _Controller:
    def __init__(self, admin_id):
        self.admin_id = admin_id


def test_super_can_access_any_event():
    admin = _Admin(uuid4(), AdminRole.SUPER)
    event = _Event(uuid4(), owner_id=uuid4())
    assert can_access_event(admin, event) is True


def test_event_manager_can_access_own_event():
    admin = _Admin(uuid4(), AdminRole.EVENT_MANAGER)
    event = _Event(uuid4(), owner_id=admin.id)
    assert can_access_event(admin, event) is True


def test_event_manager_cannot_access_foreign_event():
    admin = _Admin(uuid4(), AdminRole.EVENT_MANAGER)
    event = _Event(uuid4(), owner_id=uuid4())
    assert can_access_event(admin, event) is False


def test_controller_can_access_assigned_event():
    admin = _Admin(uuid4(), AdminRole.CONTROLLER)
    event = _Event(uuid4(), owner_id=uuid4(), controllers=[_Controller(admin.id)])
    assert can_access_event(admin, event) is True


def test_controller_cannot_access_unassigned_event():
    admin = _Admin(uuid4(), AdminRole.CONTROLLER)
    event = _Event(uuid4(), owner_id=uuid4(), controllers=[])
    assert can_access_event(admin, event) is False


def test_viewer_cannot_access_any_event():
    admin = _Admin(uuid4(), AdminRole.VIEWER)
    event = _Event(uuid4(), owner_id=uuid4())
    assert can_access_event(admin, event) is False
