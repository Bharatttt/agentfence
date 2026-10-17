'use strict';
const $ = id => document.getElementById(id);
let role = '', page = 'chat', running = false, reviewChoice = null, sessionVersion = 0;
const reasons = {
 policy_permitted: 'The action is permitted for this account and assigned case.',
 resource_not_in_scope: 'This resource is outside your assigned case. Access was blocked.',
 scope_mismatch: 'The tenant or case does not match your permissions.',
 schema_invalid: 'The tool arguments do not match the allowed format.',
 sensitive_operation: 'This action changes or exports data and needs a reviewer’s approval.',
 suspicious_tool_output: 'Suspicious instructions were detected in the retrieved content. The output was withheld.',
 tool_not_permitted: 'This account is not permitted to use this tool.'
};
const labels = {executed:'Executed', denied:'Blocked', pending:'Needs approval', rejected:'Rejected', expired:'Expired'};
const tools = {get_asset_metadata:'Read asset metadata',disable_access_key:'Disable access key',export_asset_report:'Export asset report',read_document:'Read document',search_incident_runbooks:'Search runbooks'};
function el(tag, text, cls){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;}
function notice(text){$('notice').textContent=text;}
async function api(path, body){
 const response=await fetch(path,{method:body===undefined?'GET':'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-AgentFence':'portal'},...(body===undefined?{}:{body:JSON.stringify(body)})});
 let data;try{data=await response.json();}catch{throw new Error('Unexpected server response. Check Activity before retrying.');}
 if(!response.ok){if(response.status===401&&path!=='/api/login')signedOut();throw new Error(typeof data.detail==='string'?data.detail:'Request could not be completed.');}return data;
}
function signedOut(){sessionVersion++;role='';$('workspace').hidden=true;$('login-view').hidden=false;$('password').value='';$('conversation').replaceChildren();$('history').replaceChildren();$('audit').replaceChildren();$('approvals').replaceChildren();$('confirm').close();}
function showPage(next){page=next;for(const name of ['chat','review','activity']){$(name+'-page').hidden=name!==next;$('nav-'+name).classList.toggle('active',name===next);}$('page-title').textContent={chat:'Agent chat',review:'Approvals',activity:'Activity'}[next];}
async function signedIn(account){sessionVersion++;role=account;$('login-view').hidden=true;$('workspace').hidden=false;$('identity').textContent=role.charAt(0).toUpperCase()+role.slice(1);$('nav-chat').hidden=role==='reviewer';$('nav-review').hidden=role!=='reviewer';$('sensitive-example').hidden=role!=='responder';$('audit-section').hidden=role!=='reviewer';showPage(role==='reviewer'?'review':'chat');notice('');await refresh();}
function message(label,text,cls){const node=el('article',undefined,'message '+cls);node.append(el('div',label,'label'),el('p',text));$('conversation').append(node);return node;}
function eventCard(event){const card=el('div',undefined,'outcome '+event.status);card.append(el('strong',labels[event.status]||event.status),el('p',reasons[event.reason]||event.reason||'See Activity for details.'),el('small','Request '+event.request_id));return card;}
function renderResult(result,node){node.replaceChildren(el('div','AGENTFENCE RESULT','label'));
 if(result.answer)node.append(el('p',result.answer));
 for(const event of result.events||[])node.append(eventCard(event));
 if(result.status==='pending')node.append(el('p','The agent has paused. A reviewer must sign in to approve or reject the exact action. Approval does not automatically resume this chat.'));
 else if(result.status==='completed'&&!(result.events||[]).length)node.append(el('p','The model answered without a tool call. No gateway action was executed.'));
 else if(!['completed','pending','denied'].includes(result.status))node.append(el('p','The agent stopped: '+result.status+'. Check Activity before submitting another task.'));
}
function requestCard(row,review){const box=el('article',undefined,'card');const status=row.expired?'expired':row.status;const top=el('div',undefined,'card-top');top.append(el('h3',tools[row.tool]||row.tool),el('span',labels[status]||status,'badge '+status));box.append(top,el('p',row.owner+' · '+new Date(row.created*1000).toLocaleString()),el('p',reasons[row.reason]||row.reason));
 if(review){box.append(el('pre',JSON.stringify(row.arguments,null,2)),el('p','Expires '+new Date(row.expires*1000).toLocaleTimeString()));const actions=el('div',undefined,'card-actions');for(const [title,approve] of [['Approve action',true],['Reject',false]]){const b=el('button',title,approve?'primary':'secondary');b.onclick=()=>openReview(row,approve);actions.append(b);}box.append(actions);}
 const details=el('details');details.append(el('summary','Request details'),el('pre',JSON.stringify({request_id:row.id,task:row.task_id,arguments:row.arguments,binding:row.digest},null,2)));box.append(details);return box;
}
async function refresh(){if(!role)return;const version=sessionVersion;const rows=await api('/api/requests');if(version!==sessionVersion)return;const pending=rows.filter(r=>r.status==='pending'&&!r.expired);$('pending-count').textContent=pending.length;$('approvals').replaceChildren(...pending.map(r=>requestCard(r,true)));if(!pending.length)$('approvals').append(el('div','No actions waiting for approval.','empty'));$('history').replaceChildren(...rows.map(r=>requestCard(r,false)));if(!rows.length)$('history').append(el('div','No tool requests yet. Start a task in Agent chat.','empty'));
 if(role==='reviewer'){const events=await api('/api/audit');if(version!==sessionVersion)return;$('audit').replaceChildren();for(const event of events){const details=el('details',undefined,'audit-event');details.append(el('summary','#'+event.seq+' · '+event.event+' · '+event.actor+' · '+new Date(event.at*1000).toLocaleString()),el('pre',JSON.stringify(event,null,2)));$('audit').append(details);}}
}
function openReview(row,approve){reviewChoice={row,approve};$('confirm-title').textContent=approve?'Approve this exact action?':'Reject this action?';$('confirm-copy').textContent=(tools[row.tool]||row.tool)+' · requested by '+row.owner;$('confirm-args').textContent=JSON.stringify(row.arguments,null,2);$('confirm-action').textContent=approve?'Approve & execute':'Reject action';$('confirm-action').className=approve?'primary':'danger';$('confirm').showModal();}
$('cancel').onclick=()=>$('confirm').close();
$('confirm-action').onclick=async()=>{const choice=reviewChoice;if(!choice)return;$('confirm-action').disabled=true;try{const result=await api('/api/review/'+encodeURIComponent(choice.row.id),{approve:choice.approve,request_digest:choice.row.digest});$('confirm').close();notice(result.status==='executed'?'Approved action executed. Its outcome is recorded in Activity.':'Action rejected. This request was not executed.');await refresh();}catch(error){$('confirm').close();notice(error.message);await refresh().catch(()=>{});}finally{$('confirm-action').disabled=false;reviewChoice=null;}};
$('login-form').onsubmit=async event=>{event.preventDefault();$('login-button').disabled=true;$('login-error').textContent='';try{const data=await api('/api/login',{username:$('username').value,password:$('password').value});$('password').value='';await signedIn(data.role);}catch(error){$('login-error').textContent=error.message;}finally{$('login-button').disabled=false;}};
$('logout').onclick=async()=>{if(running){notice('A task is still running. Wait for its result before signing out.');return;}try{await api('/api/logout',{});signedOut();}catch(error){notice(error.message);}};
$('chat-form').onsubmit=async event=>{event.preventDefault();const prompt=$('prompt').value.trim();if(!prompt||running)return;running=true;$('send').disabled=true;$('send').textContent='Running…';notice('');const version=sessionVersion;message('YOU',prompt,'user');$('prompt').value='';const node=message('AGENTFENCE','Working with Gemini and checking tool permissions…','assistant');try{const result=await api('/api/chat',{prompt});if(version===sessionVersion){renderResult(result,node);await refresh();}}catch(error){if(version===sessionVersion){node.replaceChildren(el('div','TASK INTERRUPTED','label'),el('p',error.message));await refresh().catch(()=>{});}}finally{running=false;$('send').disabled=false;$('send').textContent='Run task →';}};
for(const button of document.querySelectorAll('[data-prompt]'))button.onclick=()=>{$('prompt').value=button.dataset.prompt;$('prompt').focus();};
for(const name of ['chat','review','activity'])$('nav-'+name).onclick=()=>{showPage(name);refresh().catch(e=>notice(e.message));};
for(const id of ['refresh-review','refresh-activity'])$(id).onclick=()=>refresh().catch(e=>notice(e.message));
api('/api/session').then(data=>signedIn(data.role)).catch(()=>{});
setInterval(()=>{if(role&&!running)refresh().catch(e=>notice(e.message));},15000);
