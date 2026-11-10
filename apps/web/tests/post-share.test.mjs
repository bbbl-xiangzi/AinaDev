import test from 'node:test';
import assert from 'node:assert/strict';
import { postShareUrl, postShareText } from '../lib/post-share.ts';
test('share URL keeps browser origin and port, drops credentials, query and hash', () => {
  assert.equal(postShareUrl('http://user:pass@community.example:8090/post/2?token=secret#reply', 32), 'http://community.example:8090/post/32');
  assert.equal(postShareUrl('https://community.example', 32), 'https://community.example/post/32');
  for (const id of ['../admin', '1?token=x', 0, -1]) assert.throws(() => postShareUrl('https://example.com', id));
  assert.throws(() => postShareUrl('javascript:alert(1)', 1));
});
test('share content contains only title, configured site name and link', () => {
  assert.equal(postShareText('帖子标题', '企业社区', 'https://example.com/post/32'), '推荐阅读：帖子标题\n来自：企业社区\nhttps://example.com/post/32');
  assert.equal(postShareText('标题', '', 'http://example.com/post/1'), '推荐阅读：标题\nhttp://example.com/post/1');
});
