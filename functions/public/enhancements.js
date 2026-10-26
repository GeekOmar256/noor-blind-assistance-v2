'use strict';
// Extends the caregiver interface while keeping the original flows intact.
Object.assign(ar,{
  'Use this photo for recognition':'استخدم هذه الصورة للتعرف على الوجه',
  'Person':'الشخص','＋ New person':'＋ شخص جديد',
  'Add photo & rebuild faces':'أضف الصورة وأعد تدريب التعرف',
  'Use a clear photo with one face. The Pi will update its selected recognition model.':'استخدم صورة واضحة بوجه واحد. سيحدّث الجهاز نموذج التعرف المحدد.',
  'Sent voice notes':'الرسائل الصوتية المرسلة',
  'Listen again here or replay a note through the Pi speaker.':'استمع إليها هنا مجدداً أو أعد تشغيلها من سماعة الجهاز.',
  'Recognition model':'نموذج التعرف',
  'Changing models rebuilds the gallery on the Pi. dlib needs its additional model files installed.':'سيعيد الجهاز بناء معرض الوجوه عند تغيير النموذج. يتطلب dlib تثبيت ملفاته الإضافية.',
  'Scene description':'وصف المشهد'
});
let historyURL=null;
const renderBeforeEnhancements=render;
render=function(){
  renderBeforeEnhancements();
  if(!settingsDirty){
    $('setting-face').checked=state.settings.faceRecognition??false;
    $('setting-scene').checked=state.settings.sceneDescription??true;
    $('setting-face-model').value=state.settings.faceModel||'sface';
  }
  const model=state.settings.faceModel||'sface';
  $('model-readiness').textContent=model==='dlib'&&!state.status?.modelsAvailable?.dlib?
    'dlib needs installation on the Pi before it can recognize faces. The SFace gallery remains separate.':'';
  $('snapshot-enroll').hidden=!state.snapshot?.media;
  const selected=$('snapshot-person').value;
  $('snapshot-person').innerHTML='<option value="">＋ New person</option>'+state.persons.map(p=>`<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');
  $('snapshot-person').value=state.persons.some(p=>p.id===selected)?selected:'';
  $('snapshot-new').hidden=Boolean($('snapshot-person').value);
  $('voice-history').innerHTML=state.commands.filter(c=>c.type==='voice'&&c.media).slice(0,20).map(c=>`<div class="voice-note"><small>${esc(time(c.createdAt))} · ${esc(c.state)}</small><div class="row"><button type="button" data-listen="${esc(c.media)}">▶ Listen here</button><button type="button" data-replay="${esc(c.media)}">↻ Replay on Pi</button></div></div>`).join('')||'<p>No voice notes sent yet.</p>';
  $('voice-history').querySelectorAll('[data-listen]').forEach(b=>b.onclick=safe(async()=>{
    let source;
    if(demo){source=audioURL;if(!source)throw Error('Record or choose a note in this preview first')}
    else{const blob=await media(b.dataset.listen);if(historyURL)URL.revokeObjectURL(historyURL);historyURL=URL.createObjectURL(blob);source=historyURL}
    const player=$('history-player');player.src=source;player.hidden=false;player.play().catch(()=>{});
  }));
  $('voice-history').querySelectorAll('[data-replay]').forEach(b=>b.onclick=safe(()=>command('voice',{media:b.dataset.replay})));
  if(demo&&state.snapshot?.media==='preview'){
    const sample=$('snapshot');sample.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360"><rect width="640" height="360" fill="#eae5fd"/><text x="50%" y="49%" text-anchor="middle" fill="#6956df" font-size="24" font-family="Arial">Sample camera photo</text></svg>');
    sample.hidden=false;document.querySelector('.camera-placeholder').hidden=true;$('snapshot-time').textContent='Preview image';
  }
};
$('snapshot-person').onchange=()=>{$('snapshot-new').hidden=Boolean($('snapshot-person').value)};
$('snapshot-enroll').onsubmit=safe(async e=>{
  e.preventDefault();const button=e.submitter;button.disabled=true;
  try{
    const id=$('snapshot-person').value;
    if(!state.snapshot?.media)throw Error('Capture a photo first');
    const payload=id?{personId:id}:{newPerson:{name:$('snapshot-name').value.trim(),relation:$('snapshot-relation').value,note:$('snapshot-note').value}};
    if(!id&&!payload.newPerson.name)throw Error('Enter the new person’s name');
    if(demo){
      const person=id?state.persons.find(p=>p.id===id):{id:crypto.randomUUID().replaceAll('-',''),...payload.newPerson,images:[]};
      if(!id)state.persons.push(person);
      if(!person.images.includes('preview'))person.images.push('preview');
      await command('train');
    }else{
      await api('snapshot/enroll',payload);
      toast('Photo added. The Pi is rebuilding the selected face gallery.');
      await sync();
    }
    $('snapshot-name').value='';$('snapshot-relation').value='';$('snapshot-note').value='';
  }finally{button.disabled=false}
});
const previousCapture=$('capture').onclick;
$('capture').onclick=safe(async e=>{
  await previousCapture(e);
  if(demo){state.snapshot={media:'preview',capturedAt:new Date().toISOString()};render()}
});
$('settings-form').onsubmit=safe(async e=>{
  e.preventDefault();
  const oldModel=state.settings.faceModel||'sface';
  const nextModel=$('setting-face-model').value;
  await api('settings',{
    theme:$('setting-theme').value,language:$('setting-language').value,
    voice:$('setting-voice').value,speech:$('setting-speech').checked,
    faceRecognition:$('setting-face').checked,faceModel:nextModel,
    sceneDescription:$('setting-scene').checked
  });
  settingsDirty=false;
  if(nextModel!==oldModel&&state.persons.some(p=>(p.images||[]).length)&&
      (nextModel==='sface'||state.status?.modelsAvailable?.dlib)){
    await command('train');
    toast('Settings saved. Rebuilding the '+nextModel+' face gallery on the Pi.');
  }else{
    await sync();toast(nextModel==='dlib'&&!state.status?.modelsAvailable?.dlib?
      'Model saved. Install dlib on the Pi, then tap Sync & train on Pi.':'Settings saved');
  }
  go('settings');
});
