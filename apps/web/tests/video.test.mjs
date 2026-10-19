import { test } from 'node:test';
import assert from 'node:assert/strict';
import { isUploadedVideo } from '../lib/video.ts';
test('recognizes generated local videos but rejects external or unsafe paths', () => {
  const path='/uploads/202610/10/'+ 'a'.repeat(32);
  assert.equal(isUploadedVideo(path+'.mp4'), true);
  assert.equal(isUploadedVideo(path+'.webm'), true);
  for (const url of ['https://evil.example/video.mp4','javascript:alert(1)','//evil/video.mp4', '/uploads/../private.mp4', path+'.png', undefined]) {
    assert.equal(isUploadedVideo(url), false);
  }
});
