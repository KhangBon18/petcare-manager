import unittest
from unittest.mock import patch

from petcare.services.ops_metrics_service import collect_prometheus_payload


class OpsMetricsServiceTests(unittest.TestCase):
    @patch("petcare.services.ops_metrics_service.collect")
    def test_payload_contains_aggregate_queue_and_worker_metrics(self, collect):
        collect.return_value = {
            "email_jobs": {"pending": 3},
            "export_jobs": {"ready": 2},
            "oldest_email_pending_seconds": 17,
            "oldest_export_pending_seconds": 0,
            "healthy_workers": {"email"},
        }
        connection = object()
        payload = collect_prometheus_payload(connection, 300)

        self.assertIn('petcare_queue_jobs{queue="email",status="pending"} 3', payload)
        self.assertIn('petcare_queue_jobs{queue="email",status="failed"} 0', payload)
        self.assertIn('petcare_queue_jobs{queue="tenant_export",status="ready"} 2', payload)
        self.assertIn('petcare_queue_oldest_pending_seconds{queue="email"} 17', payload)
        self.assertIn('petcare_worker_up{worker="email"} 1', payload)
        self.assertIn('petcare_worker_up{worker="tenant_export"} 0', payload)
        collect.assert_called_once_with(connection, 300)


if __name__ == "__main__":
    unittest.main()
