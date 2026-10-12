"use client";
import { useEffect, useRef, useState } from "react";
import { http } from "@/lib/api";

type Banner = {id:string; image_url:string; post_id:number; pinned:boolean; enabled:boolean; post_title?:string; post_available?:boolean};
type Post = {id:number; title:string};
const inputClass="w-full rounded-md border border-[#d0d7de] px-3 py-2 text-sm focus:border-[#0969da] focus:outline-none";
const buttonClass="rounded-md border border-[#d0d7de] px-3 py-1.5 text-sm hover:bg-[#f6f8fa] disabled:opacity-50";

export function BannersPanel() {
  const [items,setItems]=useState<Banner[]>([]);
  const [loading,setLoading]=useState(true);
  const [loaded,setLoaded]=useState(false);
  const [loadAttempt,setLoadAttempt]=useState(0);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  const [draft,setDraft]=useState<Banner|null>(null);
  const [query,setQuery]=useState("");
  const [posts,setPosts]=useState<Post[]>([]);
  const [searching,setSearching]=useState(false);
  const [uploading,setUploading]=useState(false);
  const fileRef=useRef<HTMLInputElement>(null);
  const uploadSequence=useRef(0);
  useEffect(() => {
    let active=true;
    setLoading(true);setLoaded(false);setError("");
    http.get<{items:Banner[]}>("/admin/banners").then(r=>{if(active){setItems(r.items);setLoaded(true);}}).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setLoading(false);});
    return ()=>{active=false;};
  },[loadAttempt]);
  useEffect(() => {
    if (!draft) return;
    let active=true;
    setSearching(true);
    const timer=setTimeout(()=>http.get<{items:Post[]}>(`/admin/banners/posts?q=${encodeURIComponent(query)}`).then(r=>{if(active)setPosts(r.items);}).catch(e=>{if(active){setPosts([]);setError(e.message);}}).finally(()=>{if(active)setSearching(false);}),250);
    return ()=>{active=false;clearTimeout(timer);};
  },[query,draft?.id]);
  async function persist(next:Banner[]) {
    if(!loaded || loading) return false;
    setBusy(true);setError("");setMessage("");
    try {
      const r=await http.put<{items:Banner[]}>("/admin/banners",{items:next.map(({id,image_url,post_id,pinned,enabled})=>({id,image_url,post_id,pinned,enabled}))});
      setItems(r.items);setMessage("已保存");return true;
    } catch(e:any){setError(e.message || "保存失败");return false;} finally{setBusy(false);}
  }
  function edit(item?:Banner) {
    if(!loaded || loading) return;
    uploadSequence.current++;setUploading(false);setError("");setMessage("");setQuery("");setPosts([]);
    const id=Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,"0")).join("");
    setDraft(item ? {...item} : {id,image_url:"",post_id:0,pinned:false,enabled:true});
  }
  async function upload(file?:File) {
    if (!file) return;
    if (!/\.(png|jpe?g|gif|webp)$/i.test(file.name)){setError("请选择 PNG、JPG、GIF 或 WebP 图片");return;}
    const sequence=++uploadSequence.current;
    setUploading(true);setError("");
    try { const fd=new FormData();fd.append("file",file);const r=await http.upload<{url:string}>("/uploads",fd);if(sequence===uploadSequence.current)setDraft(d=>d?{...d,image_url:r.url}:d); }
    catch(e:any){if(sequence===uploadSequence.current)setError(e.message || "上传失败");}
    finally{if(sequence===uploadSequence.current)setUploading(false);}
  }
  async function save() {
    if(!draft?.image_url || !draft.post_id){setError("请上传图片并选择关联帖子");return;}
    const exists=items.some(i=>i.id===draft.id);
    if(await persist(exists?items.map(i=>i.id===draft.id?draft:i):[...items,draft]))setDraft(null);
  }
  return <div className="space-y-4">
    <div className="flex items-center justify-between"><h2 className="text-[16px] font-semibold">轮播图设置</h2><button type="button" disabled={!loaded||loading||busy||!!draft||items.length>=20} onClick={()=>edit()} className="rounded-md bg-[#0969da] px-3 py-2 text-sm text-white hover:bg-[#0860ca] disabled:opacity-50">新增轮播图</button></div>
    {error&&<p role="alert" className="text-sm text-[#cf222e]">{error}</p>}
    {!loading&&!loaded&&<button type="button" className={buttonClass} onClick={()=>setLoadAttempt(i=>i+1)}>重新加载</button>}
    {message&&<p role="status" className="text-sm text-[#1a7f37]">{message}</p>}
    {draft&&<div className="space-y-4 rounded-lg border border-[#d0d7de] bg-white p-4">
      <div className="text-sm font-semibold">{items.some(i=>i.id===draft.id)?"编辑轮播图":"新增轮播图"}</div>
      <div><label className="mb-2 block text-sm">轮播图片</label>
        {draft.image_url&&<img src={draft.image_url} alt="轮播图预览" className="mb-2 aspect-[3/1] w-full max-w-[600px] rounded-md border border-[#d0d7de] object-cover"/>}
        <button type="button" className={buttonClass} disabled={uploading||busy} onClick={()=>fileRef.current?.click()}>{uploading?"上传中…":draft.image_url?"更换图片":"上传图片"}</button>
        <span className="ml-3 text-xs text-[#656d76]">建议比例 3:1</span>
        <input ref={fileRef} aria-label="上传轮播图片" type="file" accept=".png,.jpg,.jpeg,.gif,.webp" className="hidden" onChange={e=>{upload(e.target.files?.[0]);e.target.value="";}}/>
      </div>
      <div><label htmlFor="banner-post-search" className="mb-2 block text-sm">关联帖子</label>
        <input id="banner-post-search" placeholder="搜索帖子标题或 ID" value={query} onChange={e=>setQuery(e.target.value)} className={inputClass}/>
        <select aria-label="选择关联帖子" value={draft.post_id||""} onChange={e=>{const p=posts.find(p=>p.id===Number(e.target.value));if(p)setDraft({...draft,post_id:p.id,post_title:p.title,post_available:true});}} className={`${inputClass} mt-2`} disabled={searching}>
          <option value="" disabled>{searching?"搜索中…":"请选择帖子"}</option>
          {!!draft.post_id&&!posts.some(p=>p.id===draft.post_id)&&<option value={draft.post_id}>#{draft.post_id} {draft.post_title}</option>}
          {posts.map(p=><option key={p.id} value={p.id}>#{p.id} {p.title}</option>)}
        </select>
        {!searching&&!posts.length&&<p className="mt-1 text-xs text-[#656d76]">暂无匹配的已发布帖子</p>}
      </div>
      <div className="flex flex-wrap gap-6 text-sm"><label>是否置顶 <select aria-label="是否置顶" className="ml-2 rounded border border-[#d0d7de] px-2 py-1" value={draft.pinned?"yes":"no"} onChange={e=>setDraft({...draft,pinned:e.target.value==="yes"})}><option value="no">否</option><option value="yes">是</option></select></label>
      <label>状态 <select aria-label="轮播状态" className="ml-2 rounded border border-[#d0d7de] px-2 py-1" value={draft.enabled?"on":"off"} onChange={e=>setDraft({...draft,enabled:e.target.value==="on"})}><option value="on">开启</option><option value="off">下架</option></select></label></div>
      <div className="flex gap-2"><button type="button" onClick={save} disabled={busy||uploading} className="rounded-md bg-[#0969da] px-4 py-2 text-sm text-white disabled:opacity-50">{busy?"保存中…":"保存"}</button><button type="button" disabled={busy} className={buttonClass} onClick={()=>{uploadSequence.current++;setDraft(null);setUploading(false);}}>取消</button></div>
    </div>}
    <div className="overflow-x-auto rounded-lg border border-[#d0d7de] bg-white">
      {loading?<p className="p-6 text-center text-sm text-[#656d76]">加载中…</p>:!items.length?<p className="p-10 text-center text-sm text-[#656d76]">暂无轮播图</p>:<table className="w-full text-left text-sm"><thead className="border-b border-[#d0d7de] bg-[#f6f8fa] text-[#656d76]"><tr>{["图片","关联帖子","置顶","状态","操作"].map(h=><th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr></thead><tbody>{[...items].sort((a,b)=>Number(b.pinned)-Number(a.pinned)).map(item=><tr key={item.id} className="border-b border-[#d0d7de] last:border-0">
        <td className="px-3 py-3"><img src={item.image_url} alt={item.post_title||"轮播图片"} className="aspect-[3/1] w-36 min-w-24 rounded border border-[#d0d7de] object-cover"/></td>
        <td className="max-w-[240px] px-3 py-3">{item.post_available?<a href={`/post/${item.post_id}`} className="text-[#0969da] hover:underline">{item.post_title}</a>:<span className="text-[#656d76]">{item.post_title}（不可展示）</span>}</td>
        <td className="px-3 py-3">{item.pinned?"是":"否"}</td><td className="whitespace-nowrap px-3 py-3"><span className={item.enabled?"text-[#1a7f37]":"text-[#656d76]"}>{item.enabled?"开启":"下架"}</span></td>
        <td className="px-3 py-3"><div className="flex gap-3"><button disabled={busy||!!draft} onClick={()=>edit(item)} className="text-[#0969da] disabled:opacity-50">编辑</button><button disabled={busy||!!draft} onClick={()=>persist(items.map(i=>i.id===item.id?{...i,enabled:!i.enabled}:i))} className="text-[#0969da] disabled:opacity-50">{item.enabled?"下架":"开启"}</button><button disabled={busy||!!draft} onClick={()=>{if(window.confirm("删除这张轮播图配置？关联帖子和原图片会保留。"))persist(items.filter(i=>i.id!==item.id));}} className="text-[#cf222e] disabled:opacity-50">删除</button></div></td>
      </tr>)}</tbody></table>}
    </div>
  </div>;
}
