const $=id=>document.getElementById(id);
const set=(id,message)=>$(id).textContent=message;
let publicQuestionsUrl=null;
$("check-bella").onclick=async()=>{try{const r=await fetch("/api/anam/readiness",{credentials:"same-origin",cache:"no-store"});if(!r.ok)throw Error("Cloudflare Access / avatar readiness unavailable");const x=await r.json();set("bella-status",x.ready?"Anam signing configuration is present. An actual live call still requires a microphone test.":"Anam gateway is not configured; confirm ANAM_API_KEY and rate limiter.")}catch(e){set("bella-status",e.message)}};
async function getQuestionUrl(){const r=await fetch("/api/podcast/questions-config",{credentials:"same-origin",cache:"no-store"});if(!r.ok)throw Error("Owner configuration unavailable");const x=await r.json();publicQuestionsUrl=x.public_question_form_url;return x}
$("questions-share").onclick=async()=>{try{const x=await getQuestionUrl();if(!x.public_question_form_url)throw Error("Public questions not yet deployed. No link can be shared.");await navigator.clipboard.writeText(x.public_question_form_url);set("questions-status","Public submission link copied. Only share after testing Turnstile and storage.")}catch(e){set("questions-status",e.message)}};
$("questions-refresh").onclick=async()=>{const box=$("question-list");box.replaceChildren();set("questions-status","Checking private question inbox…");try{const r=await fetch("/api/podcast/questions",{credentials:"same-origin",cache:"no-store"});const data=await r.json();if(!r.ok)throw Error("Public question service is not yet configured / deployed.");const items=Array.isArray(data.items)?data.items:[];set("questions-status",items.length+" pending viewer questions. Nothing is automatically on-air.");for(const q of items){const li=document.createElement("li"),n=document.createElement("strong"),text=document.createElement("p"),date=document.createElement("small");n.textContent=String(q.display_name||"Viewer");text.textContent=String(q.question||"");date.textContent=String(q.received_at||"");li.append(n,date,text);for(const state of ["approved","dismissed"]){const b=document.createElement("button");b.textContent=state==="approved"?"Approve":"Dismiss";b.onclick=async()=>{b.disabled=true;try{const r=await fetch("/api/podcast/questions/status",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:q.id,status:state})});if(!r.ok)throw Error("Status change failed");li.remove();set("questions-status","Question marked "+state+". Not publicly posted.")}catch(e){b.disabled=false;set("questions-status",e.message)}};li.append(b)}box.append(li)}}catch(e){set("questions-status",e.message)}};
$("guest-check").onclick=async()=>{const link=$("guest-link");link.hidden=true;link.removeAttribute("href");try{const r=await fetch("/api/integrations",{credentials:"same-origin",cache:"no-store"});if(!r.ok)throw Error("Cloudflare private meeting service not available");const x=await r.json();if(!x.zoom?.configured||!x.zoom?.join_url)throw Error("No Zoom guest meeting configured yet.");const url=new URL(x.zoom.join_url);if(url.protocol!=="https:"||!(url.hostname==="zoom.us"||url.hostname.endsWith(".zoom.us"))||!/^\/j\/[0-9]{9,11}\/?$/.test(url.pathname))throw Error("Zoom invite failed URL validation.");link.href=url.href;link.hidden=false;set("guest-status","Verified Zoom invitation is available. Use Zoom invitations for guests.")}catch(e){set("guest-status",e.message)}};
$("copy-layout").onclick=async()=>{const s="You Talking to Me? Podcast OBS setup:\n1. Sign into the protected Freddy + Bella podcast studio in Chrome on the broadcast laptop.\n2. Start Bella and check host mic, headphones, lip movement and audio.\n3. In OBS, add Window Capture of the studio, crop to the two-host stage.\n4. Add host microphone Audio Input Capture. Add desktop/Bella sound via appropriate per-app audio capture or loopback. Prevent audio echo.\n5. Confirm mixer meters for BOTH voices and record a 30-second test.\n6. In OBS Settings > Stream configure your chosen platform account privately. Never paste your stream key into chat or the app.\n7. Start Streaming from OBS only when ready; disclose Bella as AI. Verify the viewer feed.\n8. End the stream in OBS and end the Bella session separately.";try{await navigator.clipboard.writeText(s);set("broadcast-status","OBS setup checklist copied. Broadcasting is still manual.")}catch{set("broadcast-status",s)}};
$("copy-promo").onclick=async()=>{const t=$("show-title").value.trim()||"You Talking to Me?";const s=t+" — Freddy and Bella are debating today's topics. Bella is a live AI avatar. Drop your questions and join the conversation! #YouTalkingToMe #Podcast #FreddyAndBella";try{await navigator.clipboard.writeText(s);set("broadcast-status","Promo draft copied. Posting is not automatic.")}catch{set("broadcast-status",s)}};
$("review").onclick=()=>{const gates=[...document.querySelectorAll(".gate")];set("review-status",gates.every(x=>x.checked)?"Pre-publication checklist completed. Nothing was uploaded or posted.":"Review incomplete: verify consent, sound/captions, AI disclosure, and publication rights.")};
const video=$("source-video"),canvas=$("vertical-preview"),ctx=canvas.getContext("2d");
let videoUrl=null,clipUrl=null,exporting=false,recorder=null,audioCtx=null,capture=null,drawId=null;
function drawFrame(){
 ctx.fillStyle="#080c14";ctx.fillRect(0,0,canvas.width,canvas.height);
 if(video.videoWidth&&video.videoHeight){
  const scale=Math.max(canvas.width/video.videoWidth,canvas.height/video.videoHeight);
  const w=video.videoWidth*scale,h=video.videoHeight*scale;
  ctx.drawImage(video,(canvas.width-w)/2,(canvas.height-h)/2,w,h);
 }else{ctx.fillStyle="#b8cbe1";ctx.font="26px sans-serif";ctx.fillText("Upload a video first",75,canvas.height/2)}
 const c=$("caption").value.trim();if(c){
  const words=c.split(/\s+/),lines=[];let line="";
  for(const word of words){const test=line?line+" "+word:word;if(test.length>20&&line){lines.push(line);line=word}else line=test}if(line)lines.push(line);
  const rendered=lines.slice(0,3);
  ctx.fillStyle="rgba(0,0,0,.75)";ctx.fillRect(10,canvas.height-220,canvas.width-20,rendered.length*48+34);
  ctx.fillStyle="#fff";ctx.font="bold 31px sans-serif";ctx.textAlign="center";ctx.textBaseline="top";
  rendered.forEach((s,i)=>ctx.fillText(s,canvas.width/2,canvas.height-205+i*48,canvas.width-36));ctx.textAlign="start";
 }
}
drawFrame();
$("file").onchange=()=>{if(exporting)return;const f=$("file").files?.[0];if(videoUrl){URL.revokeObjectURL(videoUrl);videoUrl=null}if(!f)return;if(!f.type.startsWith("video/")){set("clip-status","Choose a video file.");return}videoUrl=URL.createObjectURL(f);video.src=videoUrl;video.load();video.onloadedmetadata=()=>{const len=Number(video.duration)||0;$("start").max=len;$("end").max=len;$("end").value=Math.min(30,len).toFixed(1);set("clip-status","Loaded "+len.toFixed(1)+"s video. Choose a segment and export; no upload occurs.");drawFrame()};video.onseeked=drawFrame};
$("caption").oninput=drawFrame;
function enableExport(on){exporting=on;$("export-clip").disabled=on;$("stop-export").disabled=!on;$("file").disabled=on}
async function cleanup(){if(drawId!==null){cancelAnimationFrame(drawId);drawId=null}if(capture){capture.getTracks().forEach(t=>t.stop());capture=null}try{await audioCtx?.close()}catch{}audioCtx=null;video.pause();enableExport(false)}
$("export-clip").onclick=async()=>{
 if(exporting)return;
 if(!videoUrl||!Number.isFinite(video.duration)||!window.MediaRecorder||!canvas.captureStream){set("clip-status","Upload a valid video using a compatible browser first.");return}
 const start=Number($("start").value),end=Number($("end").value);
 if(!Number.isFinite(start)||!Number.isFinite(end)||start<0||end<=start||end-start>60||end>video.duration+.1){set("clip-status","Choose a valid segment up to 60 seconds within your video.");return}
 try{
  enableExport(true);if(clipUrl){URL.revokeObjectURL(clipUrl);clipUrl=null}$("clip-download").replaceChildren();
  video.pause();video.currentTime=start;await new Promise((resolve,reject)=>{if(Math.abs(video.currentTime-start)<.1&&video.readyState>=2)return resolve();const cb=()=>{video.removeEventListener("seeked",cb);resolve()};video.addEventListener("seeked",cb,{once:true});setTimeout(()=>{video.removeEventListener("seeked",cb);resolve()},1800)});
  audioCtx=new (window.AudioContext||window.webkitAudioContext)();
  const source=audioCtx.createMediaElementSource(video),dest=audioCtx.createMediaStreamDestination();source.connect(dest);
  await audioCtx.resume();
  drawFrame();const vstream=canvas.captureStream(30);const tracks=[...vstream.getVideoTracks(),...dest.stream.getAudioTracks()];
  capture=new MediaStream(tracks);
  const mime=["video/webm;codecs=vp8,opus","video/webm"].find(m=>MediaRecorder.isTypeSupported(m));
  if(!mime)throw Error("WebM recording is not supported in this browser.");
  const chunks=[];recorder=new MediaRecorder(capture,{mimeType:mime,videoBitsPerSecond:2100000});
  recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)};
  recorder.onstop=async()=>{const blob=new Blob(chunks,{type:mime});await cleanup();if(blob.size){clipUrl=URL.createObjectURL(blob);const a=document.createElement("a");a.href=clipUrl;a.download="freddy-bella-vertical-"+Date.now()+".webm";a.textContent="Download 9:16 clip ("+(blob.size/1048576).toFixed(1)+" MB)";$("clip-download").replaceChildren(a)}set("clip-status",blob.size?"Export complete. Review picture, BOTH voices, and captions before publishing.":"Export produced no data. Try a different file/browser.")};
  const frame=()=>{if(!exporting)return;drawFrame();if(video.currentTime>=end-.05||video.ended){if(recorder?.state==="recording")recorder.stop();return}drawId=requestAnimationFrame(frame)};
  recorder.start(1000);await video.play();frame();set("clip-status","Generating vertical clip locally…")
 }catch(e){await cleanup();recorder=null;set("clip-status","Export unavailable: "+(e.message||"browser limitation"))}
};
$("stop-export").onclick=()=>{if(recorder?.state==="recording"){recorder.stop();set("clip-status","Stopping export…")}else void cleanup()};
window.addEventListener("pagehide",()=>{if(recorder?.state==="recording")recorder.stop();if(videoUrl)URL.revokeObjectURL(videoUrl);if(clipUrl)URL.revokeObjectURL(clipUrl);void cleanup()});
