// Run against a local web server with Playwright available in NODE_PATH.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({headless:true, channel:process.env.TEST_BROWSER || 'msedge'});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    const errors=[];page.on('pageerror', e=>{errors.push(e.message);console.error(e.stack)});
    const source='# 标题\n\n正文 **加粗**\n\n[附件](/uploads/test.pdf)\n\n![图片](/uploads/test.png)\n\n```js\nconst x = 1;\n```';
    await page.addInitScript(source=>{
      localStorage.setItem('community_user',JSON.stringify({id:1,name:'Tester',role:'super_admin'}));
      localStorage.setItem('community_token','test');
      localStorage.setItem('post_draft',JSON.stringify({body:source}));
    }, source);
    let submitted;
    await page.route('**/api/**', r=>{
      const path=new URL(r.request().url()).pathname;
      if(path==='/api/posts' && r.request().method()==='POST') {submitted=r.request().postDataJSON();return r.fulfill({status:400,json:{detail:'Test intercepted'}});}
      return r.fulfill({json:path==='/api/categories'?[{id:1,name:'技术',post_permission:'public'}]:path==='/api/sdk-pages'?[]:{}});
    });
    await page.goto((process.env.TEST_BASE_URL||'http://localhost:3051')+'/new');
    await page.locator('.CodeMirror').waitFor({timeout:60000});
    await page.getByPlaceholder('标题',{exact:true}).fill('切换测试');
    await page.getByRole('button',{name:'富文本',exact:true}).click();
    const editor=page.getByLabel('正文富文本编辑');await editor.waitFor();
    assert.equal(await editor.locator('h1').innerText(),'标题');
    await page.getByRole('button',{name:'Markdown',exact:true}).click();
    await page.locator('.CodeMirror').waitFor();
    await page.getByRole('button',{name:'发布',exact:true}).click();
    await page.getByText('Test intercepted',{exact:true}).waitFor();
    assert.equal(submitted.body_md,source,'switch without editing must preserve raw Markdown');
    await page.getByRole('button',{name:'富文本',exact:true}).click();await editor.waitFor();
    await editor.press('Control+End');await editor.press('Enter');await page.keyboard.insertText('追加正文');
    await page.getByRole('button',{name:'Markdown',exact:true}).click();await page.locator('.CodeMirror').waitFor();
    assert.match(await page.locator('.CodeMirror-code').innerText(),/追加正文/);
    await page.locator('.CodeMirror').click();await page.keyboard.press('Control+End');await page.keyboard.press('Enter');await page.keyboard.insertText('Markdown新增');
    await page.getByRole('button',{name:'富文本',exact:true}).click();await editor.waitFor();
    assert.match(await editor.innerText(),/Markdown新增/);
    assert.equal(await editor.locator('a[href="/uploads/test.pdf"]').count(),1);
    assert.equal(await editor.locator('img[src="/uploads/test.png"]').count(),1);
    await editor.fill('    普通缩进');await page.getByLabel('段落样式').selectOption('0');
    assert.equal(await page.getByLabel('帖子实时预览').locator('pre').count(),0);
    await editor.press('Control+End');await editor.press('Enter');await page.keyboard.insertText('# 普通符号');
    assert.equal(await editor.locator('h1').count(),0,'input rules must stay disabled');
    await page.getByLabel('段落样式').selectOption('2');
    assert.equal(await page.getByLabel('帖子实时预览').locator('h2').count(),1);
    await page.setViewportSize({width:390,height:844});
    await page.getByRole('tab',{name:'预览',exact:true}).click();
    assert.equal(await editor.isVisible(),false);
    assert.equal(await page.getByLabel('帖子实时预览').isVisible(),true);
    assert.deepEqual(errors,[]);
    console.log('PASS: raw-preserving switch, bidirectional edits, attachments/images, indentation, literal Markdown, headings, mobile preview, no page errors');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

