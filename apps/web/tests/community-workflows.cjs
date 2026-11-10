// Run against a local development/production server; APIs are isolated fixtures.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const BASE = process.env.TEST_BASE_URL || 'http://127.0.0.1:3063';
const user = { id: 7, name: 'Test member', role: 'super_admin', department: 'Engineering', org_id: 'Example' };
const category = { id: 1, slug: 'general', name: 'General', description: '', can_post: true, post_permission: 'public' };
const post = (id, title = `Post ${id}`) => ({ id, title, body_md: 'Original body', category_id: 1, category_name: 'General', author_id: 7, author_name: user.name, author_type: 'human', status: 'published', post_type: 'discussion', tags: [], attachments: [], created_at: '2026-11-03T04:38:12Z', view_count: 3, reply_count: 0, like_count: 0, locked: false });
const frame = page => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));

(async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.TEST_BROWSER || 'msedge' });
  const results = [];
  async function run(name, test) {
    if (process.env.TEST_CASE && !new RegExp(process.env.TEST_CASE).test(name)) return;
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const page = await context.newPage();
    page.setDefaultTimeout(15000);
    page.setDefaultNavigationTimeout(60000);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const state = { override: null, employeeFailure: false, patches: [], title: 'Original post', auditCalls: [] };
    await page.addInitScript(user => {
      localStorage.setItem('community_token', 'isolated-test-token');
      localStorage.setItem('community_user', JSON.stringify(user));
      localStorage.setItem('post_draft', JSON.stringify({ body: '# Heading\n\nOriginal body\n\n[Attachment](/uploads/test.pdf)' }));
    }, user);
    await page.route('**/api/**', async route => {
      const request = route.request(), url = new URL(request.url()), path = url.pathname;
      if (state.override && await state.override(route, url)) return;
      const reply = (json, status = 200) => route.fulfill({ status, json });
      if (path === '/api/auth/me') return reply(user);
      if (path === '/api/auth/sso/status') return reply({ enabled: false });
      if (path === '/api/admin/site-config-public' || path === '/api/admin/site-config') return reply({ site_name: 'Example community', login_title: 'Example community', login_subtitle: 'Welcome', auto_sso_login: false });
      if (path === '/api/sdk-pages') return reply([]);
      if (path === '/api/admin/categories' || path === '/api/admin/external-agents') return reply([]);
      if (path === '/api/categories') return reply([category, { ...category, id: 17, slug: 'announcements', name: '公告' }]);
      if (/^\/api\/categories\/\d+$/.test(path)) return reply(category);
      if (path === '/api/banners') return reply({ items: [] });
      if (path === '/api/me/employee-fields') return reply([{ field_key: 'staff_code', field_name: 'Staff code', target: 'custom', enabled: true, user_editable: true }]);
      if (path === '/api/me/employee') return state.employeeFailure ? reply({ detail: 'Employee lookup failed' }, 503) : reply({ extras: { staff_code: 'E001' } });
      if (path === '/api/me/profile') { state.patches.push(request.postDataJSON()); return reply(user); }
      if (path === '/api/me/tickets') return reply({ balance: 0, total_earned: 0, items: [] });
      if (path === '/api/me/posts' || path === '/api/me/notifications') return reply({ items: [], total: 0 });
      if (path === '/api/admin/audit-logs') {
        state.auditCalls.push(url.search);
        const pageNumber = Number(url.searchParams.get('page') || 1), size = Number(url.searchParams.get('page_size') || 20);
        const count = url.searchParams.get('action') ? 2 : size === 1 || pageNumber === 2 ? 1 : 20;
        return reply(Array.from({ length: count }, (_, i) => ({ id: (pageNumber - 1) * size + i + 1, actor_type: 'user', actor_id: 7, action: 'edit_post', created_at: '2026-11-03T04:38:12Z' })));
      }
      if (path === '/api/admin/agent-runs') return reply({ items: [], total: 0 });
      if (path === '/api/posts') return reply(url.searchParams.get('page_size') === '1' ? { items: [post(100, 'Announcement')], total: 1 } : { items: [], total: 0 });
      if (path.endsWith('/replies')) return reply([]);
      if (path === '/api/posts/11/edit') return reply({ ...post(11, state.title), revision: 'a'.repeat(64) });
      if (/^\/api\/posts\/\d+$/.test(path)) return reply(post(Number(path.split('/').pop()), state.title));
      return reply({});
    });
    try {
      await test(page, state);
      assert.deepEqual(errors, [], 'browser runtime errors');
      console.log('PASS', name);
      results.push({ name, passed: true });
    } catch (error) {
      console.error('FAIL', name, error.stack);
      if (name.startsWith('audit-')) console.error('AUDIT_DIAGNOSTICS', JSON.stringify({ calls: state.auditCalls, jump: await page.getByLabel('目标页码').inputValue().catch(() => null), navigation: await page.getByRole('navigation', { name: '操作审计日志分页' }).innerText().catch(() => null) }));
      results.push({ name, passed: false, error: error.message });
    } finally { await context.close(); }
  }

  try {
    await run('feed-race', async (page, state) => {
      let release, started;
      const ready = new Promise(resolve => { started = resolve; });
      const gate = new Promise(resolve => { release = resolve; });
      state.override = async (route, url) => {
        if (url.pathname !== '/api/posts' || url.searchParams.get('page_size') !== '20') return false;
        if (url.searchParams.get('sort') === 'latest') { started(); await gate; await route.fulfill({ json: { items: [post(1, 'Outdated latest')], total: 1 } }); }
        else await route.fulfill({ json: { items: [post(2, 'Current hot')], total: 1 } });
        return true;
      };
      await page.goto(BASE + '/'); await ready;
      await page.getByRole('button', { name: '热门', exact: true }).click();
      await page.getByRole('link', { name: 'Current hot', exact: true }).waitFor();
      const oldResponse = page.waitForResponse(response => response.url().includes('/api/posts?sort=latest') && response.url().includes('page_size=20'));
      release(); await oldResponse; await frame(page);
      assert.equal(await page.getByRole('link', { name: 'Outdated latest', exact: true }).count(), 0, 'late old feed must not overwrite a newer sort');
      assert.equal(await page.getByRole('link', { name: 'Current hot', exact: true }).isVisible(), true);
    });

    await run('feed-pagination', async (page, state) => {
      let secondPageCalls = 0;
      state.override = async (route, url) => {
        if (url.pathname !== '/api/posts' || url.searchParams.get('page_size') !== '20') return false;
        const second = url.searchParams.get('page') === '2';
        if (second) secondPageCalls++;
        await route.fulfill({ json: { items: second ? [post(21)] : Array.from({ length: 20 }, (_, i) => post(i + 1)), total: 21 } });
        return true;
      };
      await page.goto(BASE + '/'); await page.getByRole('link', { name: 'Post 1', exact: true }).waitFor();
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await page.getByRole('link', { name: 'Post 21', exact: true }).waitFor();
      await frame(page); assert.equal(secondPageCalls, 1);
      assert.equal(await page.getByRole('link', { name: /^Post \d+$/ }).count(), 21);
    });

    await run('profile-failure', async (page, state) => {
      await page.goto(BASE + '/me');
      await page.getByRole('button', { name: '编辑资料', exact: true }).click();
      const dialog = page.getByRole('dialog', { name: '编辑个人资料' });
      await dialog.locator('input').first().waitFor();
      await dialog.locator('input').last().waitFor();
      await dialog.getByRole('button', { name: '取消', exact: true }).click();
      state.employeeFailure = true;
      const failed = page.waitForResponse(response => response.url().endsWith('/api/me/employee') && response.status() === 503);
      await page.getByRole('button', { name: '编辑资料', exact: true }).click(); await failed; await frame(page);
      assert.equal(await dialog.getByRole('button', { name: '保存', exact: true }).isDisabled(), true, 'unread employee data must not be saved as empty values');
      assert.equal(state.patches.length, 0);
    });

    await run('profile-save', async (page, state) => {
      await page.goto(BASE + '/me'); await page.getByRole('button', { name: '编辑资料', exact: true }).click();
      const dialog = page.getByRole('dialog', { name: '编辑个人资料' });
      await dialog.getByLabel('昵称', { exact: true }).fill('Updated name');
      await dialog.getByLabel(/^Staff code/).fill('E002');
      const saved = page.waitForResponse(response => response.url().endsWith('/api/me/profile'));
      await dialog.getByRole('button', { name: '保存', exact: true }).click();
      await saved;
      assert.equal(state.patches.length, 1); assert.equal(state.patches[0].name, 'Updated name'); assert.equal(state.patches[0].extras.staff_code, 'E002');
    });

    await run('modal-keyboard-focus', async page => {
      await page.goto(BASE + '/me');
      const trigger = page.getByRole('button', { name: '编辑资料', exact: true });
      await trigger.click();
      const dialog = page.getByRole('dialog', { name: '编辑个人资料' });
      await dialog.waitFor(); await frame(page);
      assert.equal(await dialog.evaluate(element => element.contains(document.activeElement)), true, 'opening a modal must move keyboard focus inside it');
      await dialog.getByRole('button', { name: '关闭编辑个人资料', exact: true }).focus(); await page.keyboard.press('Shift+Tab');
      assert.equal(await dialog.evaluate(element => element.contains(document.activeElement)), true, 'Tab must remain inside the modal');
      await page.keyboard.press('Escape');
      assert.equal(await trigger.evaluate(element => document.activeElement === element), true, 'closing restores the trigger focus');
    });

    await run('nested-modal-preserves-parent', async page => {
      await page.goto(BASE + '/admin?tab=categories');
      await page.getByRole('button', { name: '+ 新建栏目', exact: true }).click();
      const parent = page.getByRole('dialog', { name: '新建栏目', exact: true });
      await parent.locator('input').first().fill('Unsaved category');
      await parent.getByText('点击选择', { exact: true }).click();
      await page.getByRole('dialog').last().waitFor();
      await page.keyboard.press('Escape'); await frame(page);
      assert.equal(await parent.count(), 1, 'one Escape must close only the emoji dialog');
      assert.equal(await parent.locator('input').first().inputValue(), 'Unsaved category');
      assert.equal(await parent.evaluate(element => element.contains(document.activeElement)), true);
      assert.equal(await page.evaluate(() => document.body.style.overflow), 'hidden');
      await page.keyboard.press('Escape');
      assert.equal(await parent.count(), 0);
      assert.notEqual(await page.evaluate(() => document.body.style.overflow), 'hidden');
    });

    await run('edit-blocks-pending-media-save', async (page, state) => {
      let release, started, submitted = 0;
      const uploadStarted = new Promise(resolve => { started = resolve; });
      const uploadGate = new Promise(resolve => { release = resolve; });
      state.override = async (route, url) => {
        if (url.pathname === '/api/uploads') {
          started(); await uploadGate;
          await route.fulfill({ json: { url: '/uploads/new-image.png', name: 'new-image.png', type: 'image', size: 68 } });
          return true;
        }
        if (url.pathname === '/api/posts/11' && route.request().method() === 'PUT') {
          submitted++; await route.fulfill({ status: 409, json: { detail: 'Keep editor open' } }); return true;
        }
        return false;
      };
      try {
        await page.goto(BASE + '/post/11/edit');
        await page.getByLabel('帖子标题').fill('Title with image');
        await page.getByRole('button', { name: '富文本', exact: true }).click();
        await page.getByLabel('正文富文本编辑', { exact: true }).waitFor();
        await page.getByLabel('上传图片', { exact: true }).setInputFiles({ name: 'new-image.png', mimeType: 'image/png', buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2nXcAAAAASUVORK5CYII=', 'base64') });
        await uploadStarted; await frame(page);
        assert.equal(await page.getByRole('button', { name: '保存修改', exact: true }).isDisabled(), true, 'saving while media is pending loses its inserted link');
        assert.equal(submitted, 0);
        release();
        await page.getByLabel('正文富文本编辑', { exact: true }).locator('img[src="/uploads/new-image.png"]').waitFor();
        assert.equal(await page.getByRole('button', { name: '保存修改', exact: true }).isEnabled(), true);
      } finally { release?.(); }
    });

    for (const target of ['new', 'reply']) await run(`${target}-blocks-pending-media-submit`, async (page, state) => {
      let release, started;
      const ready = new Promise(resolve => { started = resolve; });
      const gate = new Promise(resolve => { release = resolve; });
      state.override = async (route, url) => {
        if (url.pathname !== '/api/uploads') return false;
        started(); await gate;
        await route.fulfill({ json: { url: '/uploads/new-image.png', name: 'new-image.png', type: 'image', size: 68 } }); return true;
      };
      try {
        await page.goto(BASE + (target === 'new' ? '/new' : '/post/11'));
        if (target === 'new') await page.getByPlaceholder('标题', { exact: true }).fill('New post with image');
        await page.getByRole('button', { name: '富文本', exact: true }).click();
        const editor = page.getByLabel('正文富文本编辑', { exact: true }); await editor.waitFor();
        if (target === 'reply') await editor.fill('Reply with image');
        await page.getByLabel('上传图片', { exact: true }).setInputFiles({ name: 'new-image.png', mimeType: 'image/png', buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2nXcAAAAASUVORK5CYII=', 'base64') });
        await ready; await frame(page);
        const submit = page.getByRole('button', { name: target === 'new' ? '发布' : '回复', exact: true }).last();
        assert.equal(await submit.isDisabled(), true, 'pending media must be included before submission is enabled');
        release(); await editor.locator('img[src="/uploads/new-image.png"]').waitFor();
        assert.equal(await submit.isEnabled(), true);
      } finally { release?.(); }
    });

    await run('audit-load-lock', async (page, state) => {
      let release;
      const gate = new Promise(resolve => { release = resolve; });
      state.override = async (route, url) => {
        if (url.pathname !== '/api/admin/audit-logs') return false;
        await gate; await route.fulfill({ json: [] }); return true;
      };
      try {
        await page.goto(BASE + '/admin'); await page.getByRole('button', { name: /审计/ }).first().click();
        await page.getByLabel('目标页码').waitFor();
        assert.equal(await page.getByLabel('目标页码').isDisabled(), true, 'a pending result must not erase a newly typed jump target');
      } finally { release(); }
    });

    await run('audit-search-jump-time', async (page, state) => {
      await page.goto(BASE + '/admin'); await page.getByRole('button', { name: /审计/ }).first().click();
      await page.getByText('第 1 页', { exact: true }).waitFor();
      assert.ok(await page.getByText('2026年11月03日 12:38:12', { exact: true }).count());
      assert.equal(await page.getByRole('button', { name: '上一页', exact: true }).isDisabled(), true);
      await page.getByRole('button', { name: '下一页', exact: true }).click(); await page.getByText('第 2 页', { exact: true }).waitFor();
      await page.getByLabel('搜索操作名称').fill('edit_post'); await page.getByRole('button', { name: '搜索', exact: true }).click();
      await page.getByText('第 1 页', { exact: true }).waitFor();
      assert.equal(await page.getByRole('button', { name: '下一页', exact: true }).isDisabled(), true);
      await page.getByRole('button', { name: '清除', exact: true }).click(); await page.getByLabel('目标页码').fill('2');
      await page.getByRole('button', { name: '跳转', exact: true }).click(); await page.getByText('第 2 页', { exact: true }).waitFor();
      assert.ok(state.auditCalls.some(search => search.includes('action=edit_post')));
    });

    await run('post-edit-share-layout', async (page, state) => {
      let saved;
      state.override = async (route, url) => {
        if (url.pathname !== '/api/posts/11' || route.request().method() !== 'PUT') return false;
        saved = route.request().postDataJSON(); await route.fulfill({ status: 409, json: { detail: 'Concurrent edit; please reload' } }); return true;
      };
      await page.goto(BASE + '/post/11');
      assert.equal(await page.locator('aside').count(), 0, 'post detail uses the former announcement space');
      await page.getByRole('button', { name: '分享', exact: true }).click();
      assert.equal(await page.getByLabel('帖子链接', { exact: true }).inputValue(), BASE + '/post/11');
      await page.getByRole('button', { name: '关闭分享弹窗' }).click();
      await page.getByRole('link', { name: '编辑', exact: true }).click();
      await page.getByLabel('帖子标题').fill('Edited title');
      const response = page.waitForResponse(response => response.request().method() === 'PUT');
      await page.getByRole('button', { name: '保存修改', exact: true }).click(); await response;
      await page.getByRole('alert').filter({ hasText: 'Concurrent edit' }).waitFor();
      assert.equal(saved.revision, 'a'.repeat(64)); assert.equal(await page.getByLabel('帖子标题').inputValue(), 'Edited title');
    });

    await run('editor-fullscreen-views', async page => {
      await page.goto(BASE + '/new'); await page.getByRole('button', { name: '富文本', exact: true }).click();
      await page.getByLabel('正文富文本编辑', { exact: true }).waitFor();
      await page.getByRole('button', { name: '全屏', exact: true }).click();
      await page.getByRole('dialog', { name: '全屏编辑器' }).waitFor();
      assert.equal(await page.evaluate(() => document.body.style.overflow), 'hidden');
      await page.getByRole('button', { name: '分屏', exact: true }).click();
      assert.equal(await page.getByLabel('帖子实时预览', { exact: true }).isVisible(), true);
      await page.getByRole('button', { name: '仅预览', exact: true }).click();
      assert.equal(await page.getByLabel('正文富文本编辑', { exact: true }).isVisible(), false);
      await page.keyboard.press('Escape');
      assert.notEqual(await page.evaluate(() => document.body.style.overflow), 'hidden');
      await page.getByRole('button', { name: '仅编辑', exact: true }).click();
      await page.getByRole('button', { name: 'Markdown', exact: true }).click(); await page.locator('.CodeMirror').waitFor();
    });

    await run('manual-login-storage-denied', async page => {
      await page.addInitScript(() => { Storage.prototype.getItem = () => { throw new Error('Storage denied'); }; });
      await page.goto(BASE + '/login?local=1');
      await page.getByLabel('邮箱', { exact: true }).waitFor();
      assert.equal(await page.getByRole('button', { name: '登录', exact: true }).last().isVisible(), true);
    });
  } finally { await browser.close(); }
  console.log(JSON.stringify({ results }));
  if (results.some(result => !result.passed)) process.exitCode = 1;
})().catch(error => { console.error(error); process.exitCode = 1; });
