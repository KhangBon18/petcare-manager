import unittest
from unittest.mock import MagicMock

from petcare.repositories import tenant_export_repo


class TenantExportRepositoryTests(unittest.TestCase):
    def test_access_check_requires_current_job_owner_store_and_artifact(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchone.return_value = {"allowed": 1}
        job = {
            "id": 12,
            "tenant_id": 8,
            "requested_by": 3,
            "artifact_key": "tenants/8/exports/test.pcarexport",
        }

        self.assertTrue(tenant_export_repo.requester_has_active_admin_access(connection, job))

        sql, params = cursor.execute.call_args.args
        self.assertIn("j.status = 'processing'", sql)
        self.assertIn("tu.role IN ('owner', 'admin')", sql)
        self.assertEqual(params, (12, 8, 3, job["artifact_key"]))

    def test_access_check_denies_revoked_or_missing_requester(self):
        connection = MagicMock()
        connection.cursor.return_value.fetchone.return_value = None
        job = {"id": 12, "tenant_id": 8, "requested_by": 3, "artifact_key": "wrong-key"}

        self.assertFalse(tenant_export_repo.requester_has_active_admin_access(connection, job))


if __name__ == "__main__":
    unittest.main()
