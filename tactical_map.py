"""Interactive shared battlemap; uses existing app_state and public anon REST."""
import json
import html
from shared_backend import config_value

def map_html(map_config, token_catalog):
    api = str(config_value("SUPABASE_URL") or "").rstrip("/")
    anon = str(config_value("SUPABASE_ANON_KEY") or "")
    # No service-role key is ever embedded in client-side HTML.
    settings = {"api": api, "anon": anon, "config": map_config or {},
                "catalog": token_catalog or {}}
    source = r"""<!doctype html><html lang="pt-BR"><head><meta charset="UTF-8">
<style>
*{box-sizing:border-box}html,body{margin:0;background:#11141b;color:#e9eaf0;font:13px system-ui}
#toolbar{display:flex;gap:7px;align-items:center;flex-wrap:wrap;padding:7px;background:#191c26;border:1px solid #303443;border-radius:9px 9px 0 0}
select,button{background:#282b38;color:#eee;border:1px solid #4b5060;border-radius:6px;padding:6px;cursor:pointer}
button.active{border-color:#c5485b;background:#4a1e29}#status{margin-left:auto;color:#adb4c6;font-size:11px}
#viewport{position:relative;height:480px;overflow:hidden;background:#0e1119;border:1px solid #353b4b;border-radius:0 0 9px 9px;touch-action:none;cursor:grab}
#viewport.drag{cursor:grabbing}canvas{position:absolute;left:0;top:0;transform-origin:0 0;touch-action:none}
#tip{position:absolute;z-index:4;pointer-events:none;display:none;background:#171b25e8;color:#ffe5a1;border:1px solid #b49a5e;border-radius:7px;padding:4px 8px;font-weight:700;white-space:nowrap}
#help{padding:5px 2px;color:#9299aa;font-size:11px}
</style></head><body>
<div id="toolbar">
<select id="token"></select>
<button id="lock" class="active" title="Bloquear edição do mapa; os tokens continuam móveis">🔒 Mapa travado</button>
<button id="measure" title="Medir distância">📏 Medir</button>
<button id="reset">⤢ Ajustar</button>
<button id="clear" title="Remover todos os tokens">Limpar tokens</button>
<span id="status">Sincronizando…</span>
</div>
<div id="viewport"><canvas id="canvas" width="1200" height="800"></canvas><div id="tip"></div></div>
<div id="help">Scroll: zoom · Clique vazio: colocar token · Shift+arrastar: mover visão (ou imagem destravada) · Arrastar token: mover · Ctrl+arrastar: medir · Clique direito no token: excluir · Cada quadrado: 1,5 m</div>
<script>
const OPT=__OPTIONS__, API=OPT.api, KEY=OPT.anon;
let catalog=OPT.catalog||{};
const vp=document.getElementById('viewport'),c=document.getElementById('canvas'),ctx=c.getContext('2d');
const tip=document.getElementById('tip'),tokenSelect=document.getElementById('token'),status=document.getElementById('status');
const W=1200,H=800,CELL=50,COLS=24,ROWS=16,remote=Boolean(API&&KEY);
const headers={'apikey':KEY,'Authorization':'Bearer '+KEY,'Content-Type':'application/json'};
let config=OPT.config||{},tokens=[],scale=1,offsetX=0,offsetY=0,locked=true,measure=false,action=null;
let lastWrite=0,dirty=false,reading=false;
const images={};let background=null,bgUrl='',refreshingCatalog=false;
async function refreshCatalog(){
 if(!remote||refreshingCatalog)return;
 refreshingCatalog=true;
 try{
  const charReq=fetch(API+'/rest/v1/characters?select=player_id,data&limit=10',
                      {headers:{apikey:KEY,Authorization:'Bearer '+KEY}});
  const bossReq=fetch(API+'/rest/v1/app_state?key=eq.boss_config&select=data',
                      {headers:{apikey:KEY,Authorization:'Bearer '+KEY}});
  const responses=await Promise.all([charReq,bossReq]);
  if(responses[0].ok){
    const rows=await responses[0].json();
    for(const row of rows){
      const pid=row.player_id;
      if(catalog[pid]&&row.data){
        const next=String(row.data.token_url||'');
        if(next && next!==catalog[pid].url)catalog[pid].url=next;
      }
    }
  }
  if(responses[1].ok){
    const rows=await responses[1].json();
    const mob=((rows[0]||{}).data||{}).mob_tokens||{};
    for(let i=1;i<=5;i++){
      const id='mob_'+i;
      if(catalog[id]&&mob[id])catalog[id].url=String(mob[id]);
    }
  }
  draw();
 }catch(e){/* Preserve cached token image on transient network failure. */}
 finally{refreshingCatalog=false;}
}
function getImg(url){if(!url)return null;if(!images[url]){const im=new Image();im.crossOrigin='anonymous';im.src=url;im.onload=draw;images[url]=im;}return images[url];}
function setBackground(){const url=config.image_url||'';if(url!==bgUrl){bgUrl=url;background=getImg(url);}}
function loadCatalog(){tokenSelect.innerHTML='';for(const [id,entry] of Object.entries(catalog)){
 const opt=document.createElement('option');opt.value=id;opt.textContent=entry.label||id;tokenSelect.appendChild(opt);
}}
function fit(){scale=Math.min(vp.clientWidth/W,vp.clientHeight/H);offsetX=(vp.clientWidth-W*scale)/2;offsetY=(vp.clientHeight-H*scale)/2;draw();}
function position(e){const r=vp.getBoundingClientRect();return {x:e.clientX-r.left,y:e.clientY-r.top};}
function world(p){return {x:(p.x-offsetX)/scale,y:(p.y-offsetY)/scale};}
function cell(p){const w=world(p);return {x:Math.max(0,Math.min(COLS-1,Math.floor(w.x/CELL))),y:Math.max(0,Math.min(ROWS-1,Math.floor(w.y/CELL)))};}
function tokenAt(p){const w=world(p);return [...tokens].reverse().find(t=>Math.hypot((t.x+.5)*CELL-w.x,(t.y+.5)*CELL-w.y)<CELL*.48);}
function renderMap(){setBackground();ctx.fillStyle='#111827';ctx.fillRect(0,0,W,H);
 if(background&&background.complete&&background.naturalWidth){
  const mode=config.fit||'cover',iw=background.naturalWidth,ih=background.naturalHeight;
  const zoom=Math.max(.25,Math.min(4,Number(config.image_zoom)||1));
  const panX=Math.max(-1,Math.min(1,Number(config.pan_x)||0))*W*.5;
  const panY=Math.max(-1,Math.min(1,Number(config.pan_y)||0))*H*.5;
  const factor=mode==='contain'?Math.min(W/iw,H/ih):Math.max(W/iw,H/ih);
  const bw=mode==='stretch'?W*zoom:iw*factor*zoom;
  const bh=mode==='stretch'?H*zoom:ih*factor*zoom;
  ctx.drawImage(background,(W-bw)/2+panX,(H-bh)/2+panY,bw,bh);
 }
 ctx.strokeStyle='rgba(228,236,248,.42)';ctx.lineWidth=1.05;
 for(let i=0;i<=COLS;i++){ctx.beginPath();ctx.moveTo(i*CELL+.5,0);ctx.lineTo(i*CELL+.5,H);ctx.stroke();}
 for(let i=0;i<=ROWS;i++){ctx.beginPath();ctx.moveTo(0,i*CELL+.5);ctx.lineTo(W,i*CELL+.5);ctx.stroke();}
 for(const t of tokens){
  const x=(t.x+.5)*CELL,y=(t.y+.5)*CELL,entry=catalog[t.id]||{},url=entry.url;
  const img=getImg(url);
  if(img&&img.complete&&img.naturalWidth){
   const factor=Math.min(CELL*.86/img.naturalWidth,CELL*.86/img.naturalHeight);
   ctx.drawImage(img,x-img.naturalWidth*factor/2,y-img.naturalHeight*factor/2,
                 img.naturalWidth*factor,img.naturalHeight*factor);
  }else{
   // Do not replace the user's own token with generic shield/devil artwork.
   // Keep a subtle slot outline while the uploaded image loads.
   ctx.strokeStyle='rgba(243,227,193,.72)';ctx.lineWidth=2;
   ctx.beginPath();ctx.arc(x,y,CELL*.40,0,Math.PI*2);ctx.stroke();
   if(!url){
     ctx.fillStyle='rgba(18,20,29,.76)';
     ctx.font='bold 11px system-ui';ctx.textAlign='center';ctx.textBaseline='middle';
     ctx.fillText('SEM PNG',x,y);
   }
  }
 }
 if(action&&action.mode==='measure'){
  const a=action.start,b=action.end||a;
  ctx.strokeStyle='#f7d16e';ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();
  const dx=(b.x-a.x)/CELL,dy=(b.y-a.y)/CELL,meters=Math.hypot(dx,dy)*1.5;
  const label=meters.toFixed(2).replace('.',',')+' m';
  ctx.font='bold 19px system-ui';ctx.textAlign='center';ctx.textBaseline='middle';
  const mx=(a.x+b.x)/2,my=(a.y+b.y)/2-17,tw=ctx.measureText(label).width+16;
  ctx.fillStyle='#111827df';ctx.fillRect(mx-tw/2,my-13,tw,27);
  ctx.fillStyle='#ffe19c';ctx.fillText(label,mx,my);
 }
}
function draw(){c.style.transform='translate('+offsetX+'px,'+offsetY+'px) scale('+scale+')';renderMap();}
async function save(){dirty=true;lastWrite=Date.now();draw();
 if(!remote){status.textContent='Mapa local';return;}
 try{const r=await fetch(API+'/rest/v1/app_state?on_conflict=key',{method:'POST',
  headers:{...headers,Prefer:'resolution=merge-duplicates'},
  body:JSON.stringify({key:'battle_grid',data:{tokens},updated_at:new Date().toISOString()})});
  if(!r.ok)throw Error('HTTP '+r.status);dirty=false;status.textContent='● Sincronizado';
 }catch(e){status.textContent='⚠ Falha ao gravar';}
}
async function saveMapConfig(){
 if(!remote){status.textContent='Enquadramento local';return;}
 try{
  const response=await fetch(API+'/rest/v1/app_state?on_conflict=key',{
   method:'POST',headers:{...headers,Prefer:'resolution=merge-duplicates'},
   body:JSON.stringify({key:'battle_map_config',data:config,
                        updated_at:new Date().toISOString()})});
  if(!response.ok)throw Error(response.status);
  status.textContent='● Enquadramento salvo';
 }catch(e){status.textContent='⚠ Não foi possível salvar enquadramento';}
}
async function poll(){
 if(!remote||reading||action||dirty&&Date.now()-lastWrite<2500)return;
 reading=true;
 try{
  const r=await fetch(API+'/rest/v1/app_state?key=eq.battle_grid&select=data',{headers});
  if(!r.ok)throw Error(r.status);
  const rows=await r.json();const arr=rows[0]?.data?.tokens;
  if(Array.isArray(arr)){tokens=arr.filter(t=>Number.isInteger(t.x)&&Number.isInteger(t.y)&&t.x>=0&&t.x<COLS&&t.y>=0&&t.y<ROWS).slice(0,150);draw();}
  dirty=false;status.textContent='● Sincronizado';
 }catch(e){status.textContent='⚠ Sem conexão';}finally{reading=false;}
}
vp.addEventListener('wheel',e=>{e.preventDefault();const p=position(e),w=world(p),factor=e.deltaY<0?1.13:1/1.13;
 scale=Math.max(.2,Math.min(5,scale*factor));offsetX=p.x-w.x*scale;offsetY=p.y-w.y*scale;draw();},{passive:false});
vp.addEventListener('pointerdown',e=>{
 const p=position(e),w=world(p),target=tokenAt(p);
 if(e.ctrlKey||measure){action={mode:'measure',start:w,end:w};}
 else if(target){action={mode:'token',id:target.id};}
 else if(!locked&&e.shiftKey){action={mode:'map',p,panX:Number(config.pan_x)||0,panY:Number(config.pan_y)||0};}
 else if(e.shiftKey||e.button===1){action={mode:'pan',p,ox:offsetX,oy:offsetY};}
 else{action={mode:'place',p};}
 vp.setPointerCapture(e.pointerId);vp.classList.add('drag');draw();
});
vp.addEventListener('pointermove',e=>{
 if(!action)return;const p=position(e),w=world(p);
 if(action.mode==='measure')action.end=w;
 if(action.mode==='pan'){offsetX=action.ox+p.x-action.p.x;offsetY=action.oy+p.y-action.p.y;}
 if(action.mode==='token'){const t=tokens.find(t=>t.id===action.id);if(t){const at=cell(p);t.x=at.x;t.y=at.y;}}
 if(action.mode==='map'){config.pan_x=Math.max(-1,Math.min(1,action.panX+(p.x-action.p.x)/(W*scale)*2));config.pan_y=Math.max(-1,Math.min(1,action.panY+(p.y-action.p.y)/(H*scale)*2));}
 draw();
});
vp.addEventListener('pointerup',e=>{
 if(!action)return;const mode=action.mode,p=position(e);
 if(mode==='place'){const id=tokenSelect.value,at=cell(p);
   if(!catalog[id]||!catalog[id].url){
     status.textContent='⚠ Envie primeiro a imagem do token na ficha ou no app do boss';
     action=null;vp.classList.remove('drag');draw();return;
   }
   const existing=tokens.find(t=>t.id===id);
   if(existing){existing.x=at.x;existing.y=at.y;}else tokens.push({id,x:at.x,y:at.y});}
 action=null;vp.classList.remove('drag');draw();
 if(mode==='token'||mode==='place')save();
 if(mode==='map')saveMapConfig();
});
vp.addEventListener('contextmenu',e=>{e.preventDefault();const t=tokenAt(position(e));if(t){tokens=tokens.filter(x=>x!==t);save();}});
document.getElementById('lock').onclick=()=>{
 locked=!locked;const el=document.getElementById('lock');el.classList.toggle('active',locked);
 el.textContent=locked?'🔒 Mapa travado':'🔓 Editar mapa';
};
document.getElementById('measure').onclick=()=>{
 measure=!measure;document.getElementById('measure').classList.toggle('active',measure);
};
document.getElementById('reset').onclick=fit;
document.getElementById('clear').onclick=()=>{if(confirm('Remover todos os tokens?')){tokens=[];save();}};
loadCatalog();fit();poll();refreshCatalog();if(remote){setInterval(poll,1300);setInterval(refreshCatalog,2500);}
</script></body></html>"""
    return source.replace("__OPTIONS__", json.dumps(settings, ensure_ascii=False).replace("</", "<\\/"))
