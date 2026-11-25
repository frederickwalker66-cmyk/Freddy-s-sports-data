const $=id=>document.getElementById(id);
const KEY="freddys-podcast-studio-draft-v1",QKEY="freddys-podcast-questions-v1";
let stream=null,recorder=null,chunks=[],recordedUrl=null;
function status(s){$("record-status").textContent=s}
function controls(recording){$("audio").disabled=recording;$("video").disabled=recording;$("stop").disabled=!recording}
async function start(kind){
 if(recorder)return;
 if(!window.isSecureContext||!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){status("This browser requires HTTPS and MediaRecorder support.");return}
 try{
   const video=kind==="video";stream=await navigator.mediaDevices.getUserMedia({audio:true,video});
   const options=video?["video/webm;codecs=vp8,opus","video/webm"]:["audio/webm;codecs=opus","audio/webm"];
   const type=options.find(MediaRecorder.isTypeSupported);
   recorder=new MediaRecorder(stream,type?{mimeType:type}:undefined);chunks=[];
   if(recordedUrl){URL.revokeObjectURL(recordedUrl);recordedUrl=null}
   $("download").replaceChildren();
   $("preview").hidden=!video;
   if(video){$("preview").srcObject=stream;$("preview").play().catch(()=>{})}
   recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)};
   recorder.onstop=()=>{
     const blob=new Blob(chunks,{type:recorder?.mimeType||"application/octet-stream"});
     const ext=video?"webm":"webm";
     recordedUrl=URL.createObjectURL(blob);
     const a=document.createElement("a");a.href=recordedUrl;a.download="you-talking-to-me-"+new Date().toISOString().replace(/[:.]/g,"-")+"."+ext;a.textContent="Download "+(video?"video":"audio")+" recording ("+(blob.size/1048576).toFixed(1)+" MB)";
     $("download").replaceChildren(a);
     stream?.getTracks().forEach(t=>t.stop());stream=null;
     $("preview").srcObject=null;$("preview").hidden=true;recorder=null;controls(false);
     status(blob.size?"Recording stopped. Download the file now; it is NOT saved to the cloud.":"No recording data received.");
   };
   recorder.start(1000);controls(true);status("Recording "+kind+" locally. Select Stop when finished.");
 }catch(e){stream?.getTracks().forEach(t=>t.stop());stream=null;recorder=null;controls(false);status("Unable to start: "+(e?.name||"device unavailable")+". Check camera and microphone permission.")}
}
$("audio").addEventListener("click",()=>start("audio"));
$("video").addEventListener("click",()=>start("video"));
$("stop").addEventListener("click",()=>{if(recorder?.state==="recording"){recorder.stop();controls(false);status("Preparing recording…")}});
window.addEventListener("beforeunload",e=>{if(recorder?.state==="recording"){e.preventDefault();e.returnValue=""}});
try{const p=JSON.parse(localStorage.getItem(KEY)||"{}");$("title").value=String(p.title||"");$("topic").value=String(p.topic||"")}catch{}
$("save-plan").addEventListener("click",()=>{try{localStorage.setItem(KEY,JSON.stringify({title:$("title").value.slice(0,120),topic:$("topic").value.slice(0,3000)}));$("plan-status").textContent="Draft saved on this device only."}catch{$("plan-status").textContent="Browser storage unavailable; copy your notes before leaving."}});
function getQuestions(){try{const q=JSON.parse(localStorage.getItem(QKEY)||"[]");return Array.isArray(q)?q.filter(x=>typeof x==="string").slice(0,100):[]}catch{return []}}
function showQuestions(){const q=getQuestions();$("questions").replaceChildren();q.forEach((question,i)=>{const li=document.createElement("li");const content=document.createElement("span");content.textContent=question;const remove=document.createElement("button");remove.type="button";remove.textContent="Remove";remove.setAttribute("aria-label","Remove question "+(i+1));remove.onclick=()=>{q.splice(i,1);try{localStorage.setItem(QKEY,JSON.stringify(q))}catch{}showQuestions()};li.append(remove,content);$("questions").append(li)})}
$("add-question").addEventListener("click",()=>{const val=$("question").value.trim().slice(0,600);if(!val)return;const q=getQuestions();q.unshift(val);try{localStorage.setItem(QKEY,JSON.stringify(q.slice(0,100)));$("question").value="";showQuestions()}catch{alert("Browser storage unavailable. Copy your question to preserve it.")}});
showQuestions();
$("check-zoom").addEventListener("click",async()=>{const b=$("check-zoom"),a=$("zoom-link");b.disabled=true;a.hidden=true;a.removeAttribute("href");$("zoom-status").textContent="Checking protected Zoom setting…";try{const res=await fetch("/api/integrations",{credentials:"same-origin",cache:"no-store"});if(!res.ok)throw Error("Zoom configuration could not be checked. Confirm Cloudflare Access sign-in.");const data=await res.json();const raw=data?.zoom?.join_url;if(!data?.zoom?.configured||typeof raw!=="string")throw Error("No Zoom meeting is configured. Set ZOOM_JOIN_URL in Cloudflare Worker secrets.");const url=new URL(raw);if(url.protocol!=="https:"||!(url.hostname==="zoom.us"||url.hostname.endsWith(".zoom.us"))||!/^\/j\/[0-9]{9,11}\/?$/.test(url.pathname))throw Error("Zoom URL failed validation.");a.href=url.href;a.hidden=false;a.textContent="Open private Zoom meeting";$("zoom-status").textContent="Zoom invite available. Share only through Zoom's guest invitation flow."}catch(e){$("zoom-status").textContent=e.message||"Zoom unavailable."}finally{b.disabled=false}});
