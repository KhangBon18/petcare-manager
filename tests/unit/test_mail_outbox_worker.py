import unittest
from unittest.mock import MagicMock, call, patch

from flask import Flask

from petcare.services.mail_outbox_worker import run_maintenance, run_worker


class MailOutboxWorkerTests(unittest.TestCase):
    def test_maintenance_prunes_expired_mail_quotas_and_signup_rows(self):
        connection = object()
        transaction = MagicMock()
        transaction.return_value.__enter__.return_value = connection
        transaction.return_value.__exit__.return_value = False
        with patch(
            "petcare.services.mail_outbox_worker.transaction", transaction
        ), patch(
            "petcare.services.mail_outbox_worker.mail_outbox_repo.prune_delivered"
        ) as prune_mail, patch(
            "petcare.services.mail_outbox_worker.request_throttle_repo.prune_old"
        ) as prune_throttles, patch(
            "petcare.services.mail_outbox_worker.worker_heartbeat_repo.prune_stale"
        ) as prune_heartbeats, patch(
            "petcare.services.mail_outbox_worker.cleanup_expired_public_signups"
        ) as cleanup_signups:
            run_maintenance()

        prune_mail.assert_called_once_with(connection)
        prune_throttles.assert_called_once_with(connection)
        prune_heartbeats.assert_called_once_with(connection)
        cleanup_signups.assert_called_once_with(connection)

    def test_transient_database_failure_does_not_terminate_worker_loop(self):
        app = Flask(__name__)
        with app.app_context():
            with (
                patch(
                    "petcare.services.mail_outbox_worker.dispatch_batch",
                    side_effect=[OSError("database temporarily unavailable"), KeyboardInterrupt],
                ) as dispatch,
                patch("petcare.services.mail_outbox_worker.WorkerHeartbeat") as heartbeat_type,
                patch("petcare.services.mail_outbox_worker.time.sleep") as sleep,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    run_worker(poll_seconds=5)

        self.assertEqual(dispatch.call_count, 2)
        self.assertEqual(dispatch.call_args.kwargs, {"heartbeat": heartbeat_type.return_value})
        self.assertGreaterEqual(heartbeat_type.return_value.pulse.call_count, 2)
        sleep.assert_has_calls([call(5)])


if __name__ == "__main__":
    unittest.main()
