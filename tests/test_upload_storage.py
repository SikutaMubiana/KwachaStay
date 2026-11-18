import tempfile
import unittest
from pathlib import Path

from upload_storage import LocalUploadStorage


class UploadedFile:
    def __init__(self, content):
        self.content = content

    def save(self, path):
        Path(path).write_bytes(self.content)


class LocalUploadStorageTests(unittest.TestCase):
    def test_saves_and_deletes_upload_inside_storage_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            storage = LocalUploadStorage(folder)
            path = storage.save(UploadedFile(b'image bytes'), 'photo.jpg')

            self.assertEqual(Path(path).read_bytes(), b'image bytes')
            storage.delete(path)
            self.assertFalse(Path(path).exists())

    def test_rejects_path_outside_storage_directory(self):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as outside:
            storage = LocalUploadStorage(folder)
            with self.assertRaises(ValueError):
                storage.delete(str(Path(outside) / 'not-an-upload.jpg'))


if __name__ == '__main__':
    unittest.main()
