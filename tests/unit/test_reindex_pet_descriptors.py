import io
import unittest
from contextlib import nullcontext
from unittest.mock import MagicMock, patch

from PIL import Image

from petcare.vision import reindex_pet_descriptors as reindexer


def image_bytes():
    output = io.BytesIO()
    Image.new("RGB", (48, 48), (180, 70, 30)).save(output, format="PNG")
    return output.getvalue()


class ReindexPetDescriptorTests(unittest.TestCase):
    def test_default_dry_run_does_not_write_and_reports_missing_media(self):
        rows = [
            {"id": 4, "tenant_id": 1, "photo_filename": "a" * 32 + ".jpg"},
            {"id": 5, "tenant_id": 2, "photo_filename": "b" * 32 + ".jpg"},
        ]
        storage = MagicMock()
        storage.read.side_effect = [image_bytes(), FileNotFoundError()]
        read_connections = [nullcontext(object()), nullcontext(object())]

        with (
            patch.object(reindexer, "read_connection", side_effect=read_connections),
            patch.object(reindexer, "fetch_all", side_effect=[rows, []]),
            patch.object(reindexer, "transaction") as write_transaction,
        ):
            result = reindexer.reindex_pet_descriptors(storage=storage)

        self.assertEqual(result, {"scanned": 2, "prepared": 1, "updated": 0, "skipped": 1})
        write_transaction.assert_not_called()

    def test_apply_updates_only_photo_row_matching_tenant_and_filename(self):
        rows = [{"id": 7, "tenant_id": 3, "photo_filename": "c" * 32 + ".jpg"}]
        connection = MagicMock()
        read_connections = [nullcontext(object()), nullcontext(object())]

        with (
            patch.object(reindexer, "read_connection", side_effect=read_connections),
            patch.object(reindexer, "fetch_all", side_effect=[rows, []]),
            patch.object(reindexer, "transaction", return_value=nullcontext(connection)) as write_transaction,
            patch.object(reindexer, "get_media_storage") as get_storage,
            patch.object(reindexer.pet_repo, "replace_photo_search_indexes") as replace_index,
        ):
            get_storage.return_value.read.return_value = image_bytes()
            connection.cursor.return_value.rowcount = 1
            connection.cursor.return_value.fetchall.return_value = [
                (7, 3, '{"visual_hash":"0123456789abcdef"}')
            ]
            result = reindexer.reindex_pet_descriptors(apply=True)

        self.assertEqual(result, {"scanned": 1, "prepared": 1, "updated": 1, "skipped": 0})
        write_transaction.assert_called_once_with()
        connection.cursor.return_value.executemany.assert_called_once()
        sql, params = connection.cursor.return_value.executemany.call_args.args
        self.assertIn("tenant_id = %s AND photo_filename = %s", sql)
        self.assertEqual(params[0][1:], (7, 3, "c" * 32 + ".jpg"))
        replace_index.assert_called_once()
        self.assertEqual(
            tuple(replace_index.call_args.args[1]),
            ((3, 7, '{"visual_hash":"0123456789abcdef"}'),),
        )
        connection.cursor.return_value.close.assert_called_once_with()

    def test_rejects_unbounded_batch_size(self):
        with self.assertRaisesRegex(ValueError, "1 and 500"):
            reindexer.reindex_pet_descriptors(batch_size=501, storage=MagicMock())


if __name__ == "__main__":
    unittest.main()
