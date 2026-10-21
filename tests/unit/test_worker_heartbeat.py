import unittest
from unittest.mock import MagicMock, patch

from petcare.services.worker_heartbeat import WorkerHeartbeat


class WorkerHeartbeatTests(unittest.TestCase):
    def test_pulse_is_rate_limited_but_errors_and_recovery_are_immediate(self):
        connection = object()
        transaction = MagicMock()
        transaction.return_value.__enter__.return_value = connection
        transaction.return_value.__exit__.return_value = False
        with patch("petcare.services.worker_heartbeat.transaction", transaction), patch(
            "petcare.services.worker_heartbeat.worker_heartbeat_repo.touch"
        ) as touch, patch(
            "petcare.services.worker_heartbeat.time.monotonic",
            side_effect=[100.0, 105.0, 106.0, 107.0],
        ):
            heartbeat = WorkerHeartbeat("email", "a" * 32)
            self.assertTrue(heartbeat.pulse(force=True))
            self.assertFalse(heartbeat.pulse())
            self.assertTrue(heartbeat.pulse(error_code="worker_error"))
            self.assertTrue(heartbeat.pulse())

        self.assertEqual(touch.call_count, 3)
        self.assertEqual(touch.call_args_list[0].args, (connection, "email", "a" * 32, None))
        self.assertEqual(touch.call_args_list[1].args, (connection, "email", "a" * 32, "worker_error"))
        self.assertEqual(touch.call_args_list[2].args, (connection, "email", "a" * 32, None))

    def test_worker_names_and_error_codes_are_bounded(self):
        with self.assertRaises(ValueError):
            WorkerHeartbeat("unknown")
        with patch("petcare.services.worker_heartbeat.transaction") as transaction:
            with self.assertRaises(ValueError):
                WorkerHeartbeat("email").pulse(error_code="smtp-password leaked")
        transaction.assert_not_called()


if __name__ == "__main__":
    unittest.main()
