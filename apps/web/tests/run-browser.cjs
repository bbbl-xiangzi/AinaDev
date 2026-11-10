const { spawnSync } = require('node:child_process');
const path = require('node:path');
const env = {
  ...process.env,
  TEST_BASE_URL: process.env.TEST_BASE_URL || 'http://127.0.0.1:3063',
  TEST_BROWSER: process.env.TEST_BROWSER || (process.platform === 'win32' ? 'msedge' : 'chromium'),
};
for (const file of ['community-workflows.cjs', 'editor-modes.cjs', 'announcements.cjs', 'sdk-pages-browser.cjs']) {
  const result = spawnSync(process.execPath, [path.join(__dirname, file)], { env, stdio: 'inherit' });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status || 1);
}
