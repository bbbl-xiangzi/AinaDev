import io
import tempfile
import unittest
from starlette.requests import ClientDisconnect
from pathlib import Path
from unittest.mock import patch
from app.config import settings


class StorageTests(unittest.TestCase):
    def test_public_route_cannot_select_private_prefix(self):
        from app.services import file_storage as store
        with patch.object(store, "_object_response") as response:
            store.public_response("rag/private.txt")
            self.assertEqual(response.call_args.args[0], "uploads/rag/private.txt")

    def test_failed_download_cleans_partial_file(self):
        from app.services import file_storage as store
        paths = []
        class S3:
            def download_file(self, bucket, key, path):
                paths.append(Path(path))
                Path(path).write_bytes(b"partial")
                raise OSError("network failure")
        with patch.object(settings, "s3_bucket", "files"), patch.object(store, "client", return_value=S3()):
            with self.assertRaises(OSError), store.document_path("s3://files/rag/private.txt"):
                pass
        self.assertFalse(paths[0].exists())


class ResponseTests(unittest.IsolatedAsyncioTestCase):
    async def test_disconnect_closes_object_body(self):
        from app.services.file_storage import ObjectResponse
        body = io.BytesIO(b"secret")
        response = ObjectResponse(iter([b"part"]), body=body)

        async def send(message):
            raise OSError("disconnected")

        async def receive():
            return {"type": "http.disconnect"}

        with self.assertRaises(ClientDisconnect):
            await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)
        self.assertTrue(body.closed)

    def test_local_rag_uses_configured_root_and_keeps_bytes(self):
        from app.services import file_storage as store
        with tempfile.TemporaryDirectory() as root, patch.object(settings,"storage_backend","local"),patch.object(settings,"rag_docs_dir",root):
            ref=store.save("rag","test.txt",io.BytesIO(b"hello"))
            with store.document_path(ref) as path:
                self.assertEqual(Path(path).read_bytes(),b"hello")
                self.assertTrue(Path(path).is_relative_to(root))

    def test_s3_rag_is_private_and_temp_copy_is_cleaned(self):
        from app.services import file_storage as store
        class S3:
            def upload_fileobj(self,f,bucket,key,**kwargs):
                self.data=f.read();self.bucket=bucket;self.key=key
            def download_file(self,bucket,key,path):
                assert key=="rag/test.txt"
                Path(path).write_bytes(self.data)
        client=S3()
        with patch.object(settings,"storage_backend","s3"),patch.object(settings,"s3_bucket","files"),patch.object(store,"client",return_value=client):
            ref=store.save("rag","test.txt",io.BytesIO(b"private"))
            self.assertEqual(ref,"s3://files/rag/test.txt")
            with store.document_path(ref) as path:
                self.assertEqual(Path(path).read_bytes(),b"private")
            self.assertFalse(Path(path).exists())

    def test_path_traversal_and_foreign_bucket_rejected(self):
        from app.services import file_storage as store
        for key in ("../rag/private.txt","/etc/passwd","a/../../x","a\\..\\x"):
            with self.subTest(key=key),self.assertRaises(ValueError):
                store.checked_key(key)
        with patch.object(settings,"s3_bucket","files"),self.assertRaises(ValueError):
            with store.document_path("s3://other/rag/private.txt"):
                pass
