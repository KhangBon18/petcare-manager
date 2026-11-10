import unittest
from unittest.mock import patch

from flask import Flask, g

from petcare.services import actors, common
from petcare.services.actors import ActorContext
from petcare.services.exceptions import ForbiddenError


class ActorAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.actor = {
            "id": 12,
            "tenant_id": 31,
            "role": "admin",
            "user_active": 1,
            "membership_active": 1,
        }
        self.connection = object()

    def test_legacy_context_requires_exactly_one_active_store(self):
        with (
            patch("petcare.services.actors.user_repo.list_active_tenant_ids", return_value=[31]),
            patch("petcare.services.actors.user_repo.get_actor_for_tenant", return_value=self.actor) as get_actor,
            patch("petcare.services.actors.set_tenant_context") as set_context,
        ):
            result = actors.require_actor(self.connection, 12)

        self.assertEqual(result, self.actor)
        get_actor.assert_called_once_with(self.connection, 12, 31)
        set_context.assert_called_once_with(self.connection, 31)

    def test_zero_or_multiple_active_stores_are_rejected(self):
        for memberships in ([], [31, 32]):
            with self.subTest(memberships=memberships):
                with (
                    patch("petcare.services.actors.user_repo.list_active_tenant_ids", return_value=memberships),
                    patch("petcare.services.actors.user_repo.get_actor_for_tenant") as get_actor,
                    patch("petcare.services.actors.set_tenant_context") as set_context,
                    self.assertRaises(ForbiddenError),
                ):
                    actors.require_actor(self.connection, 12)
                get_actor.assert_not_called()
                set_context.assert_not_called()

    def test_inactive_actor_is_rejected_before_tenant_context_is_set(self):
        inactive = {**self.actor, "membership_active": 0}
        with (
            patch("petcare.services.actors.user_repo.get_actor_for_tenant", return_value=inactive),
            patch("petcare.services.actors.set_tenant_context") as set_context,
            self.assertRaises(ForbiddenError),
        ):
            actors.require_actor(self.connection, 12, tenant_id=31)
        set_context.assert_not_called()

    def test_admin_requirement_uses_live_membership_role(self):
        staff = {**self.actor, "role": "staff"}
        with (
            patch("petcare.services.actors.user_repo.get_actor_for_tenant", return_value=staff),
            patch("petcare.services.actors.set_tenant_context") as set_context,
            self.assertRaises(ForbiddenError),
        ):
            actors.require_actor(self.connection, 12, tenant_id=31, admin=True)
        set_context.assert_not_called()

    def test_common_adapter_passes_explicit_request_context_to_actor_service(self):
        context = ActorContext(user_id=12, tenant_id=31)
        app = Flask(__name__)
        with app.test_request_context("/"):
            g.actor_context = context
            with patch("petcare.services.common.actors.require_actor", return_value=self.actor) as authorize:
                result = common.require_actor(self.connection, 12, admin=True)

        self.assertEqual(result, self.actor)
        authorize.assert_called_once_with(self.connection, 12, 31, admin=True)


if __name__ == "__main__":
    unittest.main()
