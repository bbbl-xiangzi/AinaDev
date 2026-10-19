import unittest
import io
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
from fastapi import UploadFile, HTTPException
from app.api.uploads import _check_magic, _file_type, DEFAULT_ALLOWED_TYPES


class VideoUploadTests(unittest.TestCase):
    def test_video_types_enabled_and_classified(self):
        for ext in ('mp4', 'webm'):
            self.assertIn(ext, DEFAULT_ALLOWED_TYPES.split(','))
            self.assertEqual(_file_type(ext), 'video')

    def test_mp4_header(self):
        self.assertTrue(_check_magic(b'\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isommp42', 'mp4'))
        self.assertFalse(_check_magic(b'<html>not a video</html>', 'mp4'))
        self.assertFalse(_check_magic(b'\x00\x00\x00\x18ftypavif\x00\x00\x00\x00avifmif1', 'mp4'))

    def test_webm_header(self):
        self.assertTrue(_check_magic(b'\x1a\x45\xdf\xa3\x87\x42\x82\x84webm', 'webm'))
        self.assertFalse(_check_magic(b'not a video', 'webm'))
        self.assertFalse(_check_magic(b'\x1a\x45\xdf\xa3matroska', 'webm'))


class VideoUploadIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_preserves_bytes_and_metadata(self):
        from app.api import uploads
        content = b'\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isommp42' + b'x' * 1500000
        with tempfile.TemporaryDirectory() as tmp, patch.object(uploads, '_get_config', AsyncMock(return_value=({'mp4'}, 2))), patch.object(uploads.settings, 'upload_dir', tmp):
            result=await uploads.upload_file(UploadFile(filename='test.mp4',file=io.BytesIO(content)), user=object(), db=object())
            self.assertEqual((Path(tmp)/result['url'].removeprefix('/uploads/')).read_bytes(), content)
        self.assertEqual(result['type'], 'video')
        self.assertEqual(result['size'], len(content))

    async def test_oversize_and_disguised_video_not_saved(self):
        from app.api import uploads
        for content in (b'x'*1048577, b'<html>fake video</html>'):
            with patch.object(uploads, '_get_config', AsyncMock(return_value=({'mp4'}, 1))), patch.object(uploads, '_save_upload') as save:
                with self.assertRaises(HTTPException) as exc:
                    await uploads.upload_file(UploadFile(filename='test.mp4',file=io.BytesIO(content)), user=object(), db=object())
                self.assertEqual(exc.exception.status_code,400)
                save.assert_not_called()
