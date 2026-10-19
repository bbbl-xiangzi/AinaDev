const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({headless:true,channel:process.env.TEST_BROWSER||'msedge'});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:1000}});
    await page.addInitScript(()=>{if(window.top!==window)return;localStorage.setItem('community_user',JSON.stringify({id:1,name:'Tester',role:'super_admin'}));localStorage.setItem('community_token','test');});
    let config={pages:[]};
    await page.route('**/api/**',r=>{
      const path=new URL(r.request().url()).pathname;
      if(path==='/api/admin/sdk-pages'){
        if(r.request().method()==='PUT')config=r.request().postDataJSON();
        return r.fulfill({json:config});
      }
      if(path==='/api/sdk-pages')return r.fulfill({json:config.pages.filter(p=>p.enabled).map(({slug,title})=>({slug,title}))});
      if(path==='/api/sdk-pages/helper')return config.pages[0]?.enabled?r.fulfill({json:config.pages[0]}):r.fulfill({status:404,json:{detail:'页面不存在或已停用'}});
      return r.fulfill({json:path==='/api/categories'?[]:{}});
    });
    const base=process.env.TEST_BASE_URL||'http://localhost:3051';
    await page.goto(base+'/admin?tab=sdk');
    await page.getByRole('button',{name:'添加页面',exact:true}).click();
    for(const [label,value] of [['页面名称','问答助手'],['页面标识（小写字母开头）','helper'],['平台地址','https://agent.example'],['SDK 脚本地址','https://sdk.example/embed.js'],['浏览器端 AppKey','public-id']])await page.getByLabel(label,{exact:true}).fill(value);
    await page.getByLabel('启用页面',{exact:true}).check();
    await page.getByRole('button',{name:'保存配置',exact:true}).click();
    await page.getByText('已保存，刷新社区导航后生效',{exact:true}).waitFor();
    assert.equal(config.pages.length,1);
    await page.goto(base+'/sdk/helper');
    await page.getByRole('heading',{name:'问答助手',exact:true}).waitFor();
    const frame=page.frameLocator('iframe[title="问答助手"]');
    const doc=await page.locator('iframe').getAttribute('srcdoc');
    assert.ok(doc.includes('https://sdk.example/embed.js'));assert.ok(doc.includes('public-id'));
    assert.equal(await frame.locator('body').evaluate(()=>{try{parent.localStorage.getItem('community_token');return false}catch{return true}}),true);
    await frame.locator('script[src]').evaluate(s=>s.dispatchEvent(new Event('error')));
    assert.match(await frame.locator('[role="status"]').innerText(),/无法加载/);
    assert.equal(await page.getByRole('link',{name:'打开平台 ↗'}).getAttribute('href'),'https://agent.example');
    await page.goto(base+'/admin?tab=sdk');await page.getByLabel('启用页面',{exact:true}).uncheck();await page.getByRole('button',{name:'保存配置',exact:true}).click();await page.getByText('已保存，刷新社区导航后生效',{exact:true}).waitFor();
    await page.goto(base+'/sdk/helper');await page.getByText('页面不存在或已停用',{exact:true}).waitFor();assert.equal(await page.locator('iframe').count(),0);
    console.log('PASS: administrator add/save/disable, configured title/SDK/appKey, sandbox isolation, SDK load-error UI, disabled page denied');
  } finally {await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1;});

