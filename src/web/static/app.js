const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
let assets = [], libraryGroups = ['未分组'], selected = null, tab = 'markdown', filter = 'all', timer = null, uploading = false, groupDialogMode = 'create';
let selectedIds = new Set(), lastSelectedId = null;
let collapsedGroups = new Set(JSON.parse(localStorage.getItem('collapsedGroups') || '[]'));
const labels = {extract_audio:'提取音频',speech:'语音转写',text_analysis:'章节分析',scene_detect:'场景检测',extract_frames:'关键帧',vision:'画面分析',multimodal:'音画融合',knowledge:'知识提炼',markdown:'Markdown'};

async function api(url, opt) {
  const r = await fetch(url, opt);
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || '请求失败');
  return data;
}
function toast(t) {
  const e = $('#toast'); e.textContent = t; e.classList.add('show');
  setTimeout(() => e.classList.remove('show'), 2200);
}
function esc(s='') { return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function stateText(s) { return ({done:'已完成',running:'处理中',queued:'排队中',failed:'失败',needs_ai:'需要 AI 分析',waiting_agent:'需要 AI 分析',pending:'待继续',new:'未处理'})[s] || s; }

async function load() {
  const d = await api('/api/assets'); assets = d.assets; libraryGroups = d.groups || ['未分组']; $('#count').textContent = `${assets.length} 项`;
  renderList();
  if (selected) { selected = assets.find(x => x.asset_id === selected.asset_id) || selected; renderDetail(); }
}
function renderList() {
  const rows = assets.filter(x => filter === 'all' || x.pipeline === filter);
  const groups = new Map(libraryGroups.map(g=>[g,[]]));
  rows.forEach(a => { const g=a.group||'未分组'; if(!groups.has(g)) groups.set(g,[]); groups.get(g).push(a); });
  $('#assetList').innerHTML = [...groups.entries()].map(([group,items]) => `<section class="library-group ${collapsedGroups.has(group)?'collapsed':''}" data-group="${esc(group)}"><div class="group-title"><button class="group-toggle" data-group="${esc(group)}"><span class="caret">▾</span><span>${esc(group)}</span><span class="group-count">${items.length}</span></button></div><div class="group-items">${items.length ? items.map(a => `<div class="asset ${selected?.asset_id===a.asset_id?'active':''} ${selectedIds.has(a.asset_id)?'selected':''}" draggable="true" data-id="${esc(a.asset_id)}"><button class="asset-check ${selectedIds.has(a.asset_id)?'checked':''}" draggable="false" type="button" role="checkbox" aria-checked="${selectedIds.has(a.asset_id)}" aria-label="选择 ${esc(a.asset_id)}"></button><div class="asset-icon">${a.pipeline==='video'?'▶':'♪'}</div><div class="asset-info"><strong>${esc(a.asset_id)}</strong><small>${a.pipeline==='video'?'视频':'音频'} · ${stateText(a.status)}</small></div><i class="dot ${a.status}"></i></div>`).join('') : '<div class="group-empty">拖放素材到这里</div>'}</div></section>`).join('');
  $$('.asset').forEach(e => e.onclick = event => {
    if(event.target.classList.contains('asset-check')) return;
    if(event.metaKey||event.ctrlKey||event.shiftKey||selectedIds.size){ toggleAssetSelection(e.dataset.id,event.shiftKey,rows.map(a=>a.asset_id)); }
    else select(e.dataset.id);
  });
  bindSelection(rows.map(a=>a.asset_id)); bindGroupToggles(); bindLibraryDragDrop(); updateSelectionBar();
}
function bindSelection(visibleIds) {
  $$('.asset-check').forEach(box => box.onclick = event => {
    event.preventDefault(); event.stopPropagation(); toggleAssetSelection(box.closest('.asset').dataset.id,event.shiftKey,visibleIds);
  });
  $$('.asset-check').forEach(box => box.onpointerdown = event => event.stopPropagation());
}
function toggleAssetSelection(id,shiftKey,visibleIds) {
  const nextChecked=!selectedIds.has(id);
  if(shiftKey && lastSelectedId && visibleIds.includes(lastSelectedId)) {
    const a=visibleIds.indexOf(lastSelectedId), b=visibleIds.indexOf(id), [start,end]=a<b?[a,b]:[b,a];
    visibleIds.slice(start,end+1).forEach(x=>nextChecked?selectedIds.add(x):selectedIds.delete(x));
  } else nextChecked ? selectedIds.add(id) : selectedIds.delete(id);
  lastSelectedId=id; renderList();
}
function bindGroupToggles() {
  $$('.group-toggle').forEach(button => button.onclick = () => {
    const group=button.dataset.group;
    collapsedGroups.has(group)?collapsedGroups.delete(group):collapsedGroups.add(group);
    localStorage.setItem('collapsedGroups',JSON.stringify([...collapsedGroups])); renderList();
  });
}
function updateSelectionBar() {
  $('#selectionBar').hidden=selectedIds.size===0; $('#selectionCount').textContent=`已选 ${selectedIds.size} 项`;
}
function bindLibraryDragDrop() {
  $$('.asset[draggable="true"]').forEach(card => {
    card.ondragstart = e => {
      const id=card.dataset.id, ids=selectedIds.has(id)?[...selectedIds]:[id];
      e.dataTransfer.effectAllowed='move'; e.dataTransfer.setData('application/json',JSON.stringify(ids)); e.dataTransfer.setData('text/plain',id); card.classList.add('dragging');
    };
    card.ondragend = () => { card.classList.remove('dragging'); $$('.library-group').forEach(g=>g.classList.remove('drop-ready')); };
  });
  $$('.library-group').forEach(groupEl => {
    groupEl.ondragover = e => { e.preventDefault(); e.dataTransfer.dropEffect='move'; groupEl.classList.add('drop-ready'); };
    groupEl.ondragleave = e => { if(!groupEl.contains(e.relatedTarget)) groupEl.classList.remove('drop-ready'); };
    groupEl.ondrop = async e => {
      e.preventDefault(); groupEl.classList.remove('drop-ready');
      const group=groupEl.dataset.group;
      let ids; try{ids=JSON.parse(e.dataTransfer.getData('application/json'));}catch{ids=[e.dataTransfer.getData('text/plain')];}
      const moving=assets.filter(a=>ids.includes(a.asset_id)&&a.group!==group);
      if(!moving.length) return;
      const previous=new Map(moving.map(a=>[a.asset_id,a.group])); moving.forEach(a=>a.group=group); renderList();
      try {
        await api('/api/group-batch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({asset_ids:moving.map(a=>a.asset_id),group})});
        if(selected&&ids.includes(selected.asset_id)){selected.group=group;renderDetail();}
        selectedIds.clear(); updateSelectionBar(); toast(`已移动 ${moving.length} 项到“${group}”`);
      } catch(err) { moving.forEach(a=>a.group=previous.get(a.asset_id)); renderList(); toast(`移动失败：${err.message}`); }
    };
  });
}
async function select(id) {
  selected = assets.find(a => a.asset_id === id); $('#welcome').hidden = true; $('#detail').hidden = false;
  renderList(); renderDetail(); await loadTab(); watch();
}
function renderDetail() {
  if (!selected) return;
  $('#assetType').textContent = selected.pipeline === 'video' ? 'VIDEO ANALYSIS' : 'AUDIO ANALYSIS';
  $('#assetTitle').textContent = selected.asset_id; $('#assetFile').textContent = selected.filename;
  $('#statusBadge').textContent = stateText(selected.status);
  $('#process').textContent = selected.status === 'running' ? '处理中…' : selected.status === 'needs_ai' ? '继续检查' : selected.has_markdown ? '重新处理' : '开始处理';
  $('#process').disabled = selected.status === 'running'; $('#download').hidden = !selected.has_markdown;
  $('#download').href = `/download/${encodeURIComponent(selected.asset_id)}`;
  const groups = libraryGroups;
  $('#groupSelect').innerHTML = groups.map(g=>`<option value="${esc(g)}" ${g===(selected.group||'未分组')?'selected':''}>${esc(g)}</option>`).join('') + '<option value="__new__">＋ 新建分组…</option>';
  const stages = Object.keys(selected.stages).length ? selected.stages : selected.pipeline === 'video' ? {extract_audio:'pending',speech:'pending',scene_detect:'pending',extract_frames:'pending',vision:'pending',multimodal:'pending',knowledge:'pending',markdown:'pending'} : {speech:'pending',text_analysis:'pending',knowledge:'pending',markdown:'pending'};
  $('#stages').innerHTML = Object.entries(stages).map(([k,v]) => `<div class="stage ${v}"><div class="stage-bar"></div><small title="${esc(labels[k]||k)}">${esc(labels[k]||k)}</small></div>`).join('');
}
async function loadTab() {
  if (!selected) return; const pre = $('#content'); pre.textContent = '正在读取…';
  try {
    if (tab === 'log') { const d = await api(`/api/job/${encodeURIComponent(selected.asset_id)}`); pre.textContent = d.log?.join('\n') || '尚无本次运行记录。'; }
    else { const d = await api(`/api/${tab}/${encodeURIComponent(selected.asset_id)}`); pre.textContent = d.content || `尚未生成${tab==='markdown'?'总结':'转写'}。`; }
  } catch(e) { pre.textContent = e.message; }
}
function watch() {
  clearInterval(timer);
  if (selected?.status === 'running' || selected?.status === 'queued') timer = setInterval(async()=>{ await load(); await loadTab(); if(!['running','queued'].includes(selected.status)) clearInterval(timer); },1800);
}
async function processAsset() {
  if (!selected) return; await api(`/api/process/${encodeURIComponent(selected.asset_id)}`,{method:'POST'});
  selected.status='running'; renderDetail(); tab='log'; $$('.tab').forEach(e=>e.classList.toggle('active',e.dataset.tab===tab)); await loadTab(); watch(); toast('已开始处理');
}


async function uploadMany(fileList) {
  const files = [...fileList];
  if (!files.length || uploading) return;
  uploading = true; $('#uploadBtn').disabled = true;
  const panel = $('#batch'); panel.hidden = false; $('#batchTitle').textContent = '正在批量导入';
  let success = 0, failed = [];
  const batchGroup = files.length > 1 ? `导入批次 ${new Date().toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false})}` : '未分组';
  for (let i=0; i<files.length; i++) {
    const file = files[i];
    $('#batchCount').textContent = `${i+1}/${files.length}`; $('#batchFile').textContent = file.name;
    $('#batchBar').style.width = `${(i/files.length)*100}%`;
    try {
      await api('/api/upload',{method:'POST',headers:{'X-Filename':encodeURIComponent(file.name),'X-Group':encodeURIComponent(batchGroup),'Content-Type':'application/octet-stream'},body:file});
      success++;
    } catch(e) { failed.push(`${file.name}：${e.message}`); }
    $('#batchBar').style.width = `${((i+1)/files.length)*100}%`;
  }
  await load(); uploading = false; $('#uploadBtn').disabled = false;
  $('#batchTitle').textContent = failed.length ? '批量导入完成（部分失败）' : '批量导入完成';
  $('#batchCount').textContent = `${success} 成功 / ${failed.length} 失败`;
  $('#batchFile').textContent = failed.length ? failed.join('；') : `已导入 ${success} 个素材`;
  setTimeout(()=>{ panel.hidden = true; $('#batchBar').style.width='0'; }, failed.length ? 6000 : 2600);
  $('#fileInput').value = '';
}

$('#process').onclick = processAsset;
$('#uploadBtn').onclick = () => $('#fileInput').click();
$('#fileInput').onchange = e => uploadMany(e.target.files);
$('#clearSelection').onclick = () => { selectedIds.clear(); lastSelectedId=null; renderList(); };
function openGroupDialog(mode='create') {
  groupDialogMode = mode; $('#groupModalTitle').textContent = mode==='assign' ? '新建并移动到分组' : '新建分组';
  $('#groupConfirm').textContent = mode==='assign' ? '创建并移动' : '创建分组';
  $('#groupName').value=''; $('#groupModal').hidden=false; setTimeout(()=>$('#groupName').focus(),0);
}
function closeGroupDialog() { $('#groupModal').hidden=true; }
async function confirmGroupDialog() {
  const group = $('#groupName').value.trim();
  if (!group) { toast('请输入分组名称'); $('#groupName').focus(); return; }
  try {
    await api('/api/groups',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({group})});
    if (groupDialogMode==='assign' && selected) {
      await api(`/api/group/${encodeURIComponent(selected.asset_id)}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({group})});
      selected.group=group;
    }
    closeGroupDialog(); await load(); toast(`已创建分组“${group}”`);
  } catch(e) { toast(e.message); }
}
$('#newGroup').onclick = () => openGroupDialog('create');
$('#groupCancel').onclick = closeGroupDialog;
$('#groupConfirm').onclick = confirmGroupDialog;
$('#groupName').onkeydown = e => { if(e.key==='Enter') confirmGroupDialog(); if(e.key==='Escape') closeGroupDialog(); };
$('#groupModal').onclick = e => { if(e.target===$('#groupModal')) closeGroupDialog(); };
$('#groupSelect').onchange = async e => {
  if (!selected) return;
  let group = e.target.value;
  if (group === '__new__') {
    renderDetail(); openGroupDialog('assign'); return;
  }
  await api(`/api/group/${encodeURIComponent(selected.asset_id)}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({group})});
  selected.group = group.trim(); await load(); toast('已更新分组');
};
$$('.filter').forEach(e => e.onclick=()=>{filter=e.dataset.filter;$$('.filter').forEach(x=>x.classList.toggle('active',x===e));renderList();});
$$('.tab').forEach(e => e.onclick=async()=>{tab=e.dataset.tab;$$('.tab').forEach(x=>x.classList.toggle('active',x===e));await loadTab();});
const dz = $('#dropzone');
['dragenter','dragover'].forEach(n=>dz.addEventListener(n,e=>{e.preventDefault();dz.classList.add('drag');}));
['dragleave','drop'].forEach(n=>dz.addEventListener(n,e=>{e.preventDefault();dz.classList.remove('drag');}));
dz.ondrop = e => uploadMany(e.dataTransfer.files);
dz.onclick = () => $('#fileInput').click();
load().catch(e=>toast(e.message));
