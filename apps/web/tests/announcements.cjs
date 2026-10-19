const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const BASE=process.env.TEST_BASE_URL||'http://localhost:3051';
(async()=>{
 const b=await chromium.launch({headless:true,channel:'msedge'});
 const results=[]; const errors=[];
 try {
 const page=await b.newPage({viewport:{width:1440,height:1000}});
 page.on('pageerror',e=>errors.push(e.message));
 await page.clock.install();
 const cat={id:17,slug:'announcements',name:'公告',icon:'📣',post_permission:'public'};
 let cats=[cat], failure='', posts=[{id:101,title:'原公告',pinned:false,created_at:'2026-10-15T10:00:00Z',status:'published'}], calls=[];
 const full=p=>({...p,category_id:17,category_name:'公告',author_id:1,author_name:'测试管理员',author_type:'human',body_md:'公告正文',tags:[],attachments:[],view_count:0,reply_count:0,like_count:0});
 await page.route('**/api/**',async r=>{
  const u=new URL(r.request().url());
  if(u.pathname==='/api/categories')return r.fulfill({status:failure==='categories'?500:200,json:failure==='categories'?{detail:'test failure'}:cats});
  if(u.pathname==='/api/posts'){
   if(u.searchParams.has('category_id')){
    calls.push(u.search);
    if(failure==='posts')return r.fulfill({status:500,json:{detail:'test failure'}});
    assert.equal(u.searchParams.get('category_id'),String(cats.find(c=>c.slug==='announcements')?.id??cats[0]?.id));
    assert.equal(u.searchParams.get('sort'),'latest'); assert.equal(u.searchParams.get('page_size'),'1');
    const items=posts.filter(p=>p.status==='published'&&!p.deleted_at).sort((a,b)=>Number(b.pinned)-Number(a.pinned)||Date.parse(b.created_at)-Date.parse(a.created_at)).slice(0,1).map(full);
    return r.fulfill({json:{items,total:items.length}});
   }
   return r.fulfill({json:{items:[],total:0}});
  }
  if(u.pathname.endsWith('/replies'))return r.fulfill({json:[]});
  if(/^\/api\/posts\/\d+$/.test(u.pathname))return r.fulfill({json:full(posts.find(p=>p.id===Number(u.pathname.split('/').pop()))??{id:101,title:'原公告',status:'published',created_at:'2026-10-15T10:00:00Z'})});
  if(u.pathname==='/api/banners')return r.fulfill({json:{items:[]}});
  return r.fulfill({json:{}});
 });
 const card=page.locator('aside').filter({hasText:'公告'});
 const expectText=async text=>{await page.waitForFunction(text=>Array.from(document.querySelectorAll('aside')).some(a=>a.textContent.includes(text)),text);};
 const pass=s=>{results.push(s);console.log('PASS',s)};
 await page.goto(BASE+'/');await expectText('原公告');assert.equal(await card.locator('a').getAttribute('href'),'/post/101');pass('首页公告及相对路径链接');
 await card.locator('a').click();await page.waitForURL('**/post/101');await expectText('原公告');assert.equal(await page.locator('h1').innerText(),'原公告');pass('点击跳转详情且详情页显示同一公告');
 posts[0].title='已修改公告';await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expectText('已修改公告');pass('切回窗口刷新修改后的标题');
 posts.push({id:102,title:'最新公告',pinned:false,created_at:'2026-10-16T10:00:00Z',status:'published'});
 await page.clock.fastForward(60000);await expectText('最新公告');pass('一分钟自动刷新');
 posts[0].pinned=true;await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expectText('已修改公告');pass('置顶旧帖优先于新帖（模拟已排序API）');
 posts[0].status='hidden';await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expectText('最新公告');pass('隐藏后切换下一公告（模拟API过滤）');
 posts[1].deleted_at='2026-10-16';await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expectText('暂无公告');assert.equal(await card.locator('a').count(),0);pass('没有已发布公告时无旧链接');
 failure='posts';await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expectText('公告暂时无法加载');pass('帖子接口失败有提示');
 failure='categories';await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expectText('公告暂时无法加载');pass('栏目接口失败有提示');
 failure='';posts=[{id:103,title:'恢复后公告',pinned:false,status:'published',created_at:'2026-10-16T11:00:00Z'}];await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expectText('恢复后公告');pass('请求恢复后自动恢复');
 cats=[{...cat,name:'公司通知'}];await page.reload();await expectText('恢复后公告');pass('栏目改名后保留slug关联');
 cats=[{...cat,slug:'custom-notice',name:'通知公告'}];await page.reload();await expectText('恢复后公告');pass('旧栏目名称兼容');
 cats=[];await page.reload();await expectText('暂无公告');pass('公告栏目不存在');
 cats=[cat];posts[0].title='<img src=x onerror=alert(1)>'+ '超长公告'.repeat(45);await page.reload();await expectText('<img src=x');assert.equal(await card.locator('img').count(),0);assert.ok(await card.evaluate(a=>a.scrollWidth<=a.clientWidth));pass('标题安全转义及长标题换行');
 posts[0].title='公告增量包验证';await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expectText('公告增量包验证');
 await page.goto(BASE+'/login');await page.clock.fastForward(120000);const before=calls.length;await page.clock.fastForward(60000);assert.equal(calls.length,before);pass('离开公告页面后停止轮询');
 assert.deepEqual(errors,[]);pass('无浏览器运行时异常');
 }finally{await b.close();}
})().catch(e=>{console.error(e);process.exit(1)});
