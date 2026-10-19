import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from botocore.exceptions import ClientError
from fastapi import FastAPI, Request, UploadFile
from fastapi.testclient import TestClient
from app.api import uploads
from app.services import file_storage as store


class VideoStorageTests(unittest.IsolatedAsyncioTestCase):
    async def test_streamed_video_reaches_s3_with_original_bytes(self):
        content = b'\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isommp42' + b'x' * 1500000
        saved = {}
        class S3:
            def upload_fileobj(self, source, bucket, key):
                saved.update(bucket=bucket, key=key, data=source.read())
        with patch.object(uploads, '_get_config', AsyncMock(return_value=({'mp4'}, 2))), \
             patch.object(store.settings, 'storage_backend', 's3'), \
             patch.object(store.settings, 's3_bucket', 'test'), patch.object(store, 'client', return_value=S3()):
            result = await uploads.upload_file(UploadFile(filename='video.mp4', file=io.BytesIO(content)), user=None, db=None)
        self.assertEqual(saved['data'], content)
        self.assertEqual(saved['key'], result['url'].lstrip('/'))
        self.assertEqual(result['size'], len(content))

    def test_video_range_response_and_unsatisfiable_range(self):
        class Body(io.BytesIO):
            def iter_chunks(self, chunk_size):
                while chunk := self.read(chunk_size):
                    yield chunk
        bodies = []
        calls = []
        class S3:
            def get_object(self, **kwargs):
                calls.append(kwargs)
                if kwargs.get('Range') == 'bytes=99-':
                    raise ClientError({'Error': {'Code': 'InvalidRange'}}, 'GetObject')
                partial = kwargs.get('Range') == 'bytes=2-4'
                body = Body(b'234' if partial else b'0123456789')
                bodies.append(body)
                return {'Body': body, 'ContentLength': 3 if partial else 10,
                        **({'ContentRange': 'bytes 2-4/10'} if partial else {})}
        app = FastAPI()
        @app.get('/uploads/{key:path}')
        def download(key: str, request: Request):
            return store.public_response(key, request.headers.get('range'))
        with patch.object(store, 'client', return_value=S3()), TestClient(app) as client:
            result = client.get('/uploads/video.mp4', headers={'Range': 'bytes=2-4'})
            self.assertEqual((result.status_code, result.content), (206, b'234'))
            self.assertEqual(result.headers['content-range'], 'bytes 2-4/10')
            self.assertTrue(result.headers['content-disposition'].startswith('inline'))
            self.assertEqual(result.headers['content-type'], 'video/mp4')
            self.assertEqual(calls[-1]['Range'], 'bytes=2-4')
            self.assertEqual(client.get('/uploads/video.mp4', headers={'Range': 'bytes=99-'}).status_code, 416)
            result = client.get('/uploads/video.mp4', headers={'Range': 'bytes=0-1,3-4'})
            self.assertEqual((result.status_code, result.content), (200, b'0123456789'))
            self.assertNotIn('Range', calls[-1])
        self.assertTrue(all(body.closed for body in bodies))

    def test_failed_local_upload_removes_partial_file(self):
        with tempfile.TemporaryDirectory() as root, patch.object(store.settings, 'storage_backend', 'local'), \
             patch.object(store.settings, 'upload_dir', root), patch.object(store.shutil, 'copyfileobj', side_effect=OSError('full')):
            with self.assertRaises(OSError):
                store.save('uploads', 'test.mp4', io.BytesIO(b'data'))
            self.assertFalse((Path(root) / 'test.mp4').exists())
