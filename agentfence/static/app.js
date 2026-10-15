let token = ''; let role = '';
const $ = id => document.getElementById(id);
const scoped = {tenant_id:'tenant-a',case_id:'case-1'};
function preset(){
 const type=$('preset').value; const task=role==='responder'?'response-1':'investigation-1';
 const p={task_id:task,tool:'get_asset_metadata',arguments:{...scoped,asset_id:'asset-1'}};
 if(type==='smuggle')p.arguments.bypass_policy=true;
 if(type==='cross')Object.assign(p.arguments,{tenant_id:'tenant-b',case_id:'case-2',asset_id:'asset-2'});
 if(type==='poison'){p.tool='read_document';p.arguments={...scoped,document_id:'poisoned-1'};}
 if(type==='disable'){p.tool='disable_access_key';p.arguments={...scoped,key_id:'key-1',reason:'suspected_compromise'};}
 if(type==='export'){p.tool='export_asset_report';p.arguments={...scoped,asset_id:'asset-1',destination:'https://unapproved.example'};}
 $('proposal').value=JSON.stringify(p,null,2);
}
async function api(path,body){
 const r=await fetch(path,{method:body===undefined?'GET':'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},...(body===undefined?{}:{body:JSON.stringify(body)})});
 const value=await r.json(); if(!r.ok)throw new Error(value.detail||'Request failed');return value;
}
function element(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
async function refresh(){
 const rows=await api('/api/requests');$('count').textContent=rows.length;
 for(const s of ['denied','pending','executed'])$(s).textContent=rows.filter(x=>x.status===s&&!x.expired).length;
 $('requests').replaceChildren();if(!rows.length)$('requests').append(element('p','No requests yet.','muted'));
 for(const row of rows){
  const box=element('article',undefined,'request');const title=element('div',undefined,'request-title');
  title.append(element('strong',row.tool),element('span',row.expired?'expired':row.status,'status'));box.append(title);
  box.append(element('p',`${row.owner} · ${row.task_id} · ${row.reason} · ${new Date(row.created*1000).toLocaleString()}`));
  box.append(element('code',JSON.stringify(row.arguments)));box.append(element('p','Request: '+row.id));
  if(row.status==='pending'&&!row.expired&&role==='reviewer'){
   box.append(element('p','Binding: '+row.digest));const actions=element('div',undefined,'actions');
   for(const [label,approve] of [['Approve exact action',true],['Reject',false]]){const b=element('button',label,approve?'':'danger');b.onclick=()=>run(async()=>{await api('/api/approvals/'+encodeURIComponent(row.id),{approve,request_digest:row.digest});await refresh();$('message').textContent=approve?'Approved and executed.':'Request rejected.';});actions.append(b);}box.append(actions);
  }$('requests').append(box);
 }
 $('events').replaceChildren();if(role==='reviewer'){
  const events=await api('/api/audit');for(const event of events){const d=element('details',undefined,'event');d.append(element('summary',`#${event.seq} ${event.event} · ${event.actor} · ${new Date(event.at*1000).toLocaleTimeString()}`),element('pre',JSON.stringify(event,null,2)));$('events').append(d);}
 }else $('events').textContent='Reviewer access required.';
}
async function run(action){$('message').textContent='Working…';try{await action();if($('message').textContent==='Working…')$('message').textContent='Up to date.';}catch(e){$('message').textContent=e.message;}}
$('connect').onclick=()=>run(async()=>{token=$('token').value;const me=await api('/api/me');role=me.role;$('identity').textContent=me.name+' · connected';$('token').value='';preset();await refresh();});
$('logout').onclick=()=>{token='';role='';$('token').value='';$('identity').textContent='Not connected';$('requests').replaceChildren();$('events').replaceChildren();$('result').textContent='Session cleared.';for(const x of ['count','denied','pending','executed'])$(x).textContent='—';};
$('submit').onclick=()=>run(async()=>{const p=JSON.parse($('proposal').value);const r=await api('/api/calls',p);$('result').textContent=JSON.stringify(r,null,2);await refresh();});
$('refresh').onclick=()=>run(refresh);$('preset').onchange=preset;preset();
