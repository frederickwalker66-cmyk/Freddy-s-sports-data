import {createClient} from "@anam-ai/js-sdk";
const $=id=>document.getElementById(id);
let avatar=null,starting=false,cameraStream=null,captureStream=null,captureRecorder=null,clipChunks=[],clipUrl=null;
function status(s){$("bella-status").textContent=s}
function buttons(){$("start").disabled=!!avatar||starting;$("stop").disabled=!avatar||starting;$("check").disabled=starting}
async function finishAvatar(){
 if(!avatar)return;const old=avatar;avatar=null;buttons();
 try{await old.stopStreaming()}catch{}
 const video=$("bella-video");video.srcObject=null;video.removeAttribute("src");
 status("Bella disconnected. No live AI session.");
}
$("check").onclick=async()=>{
 $("check").disabled=true;status("Checking protected Anam configuration; no call is started…");
 try{const r=await fetch("/api/anam/readiness",{credentials:"same-origin",cache:"no-store"});if(r.status===401)throw Error("Sign in through your Cloudflare Access account.");if(!r.ok)throw Error("Private avatar setup check unavailable.");const data=await r.json();status(data.ready?"Bella's Anam gateway is configured. Start a call when you're ready. This does not verify a live conversation.":"The Anam key or rate-limiter binding is missing; review Cloudflare ANAM_API_KEY.")}catch(e){status(e.message||"Readiness check unavailable.")}finally{buttons()}
};
$("start").onclick=async()=>{
 if(avatar||starting)return;
 if(!window.isSecureContext||!navigator.mediaDevices?.getUserMedia){status("HTTPS and microphone support are required.");return}
 starting=true;buttons();status("Requesting the private Bella Studio session…");
 try{
   const resp=await fetch("/api/anam/session-token",{method:"POST",credentials:"same-origin",cache:"no-store",headers:{"Content-Type":"application/json","Accept":"application/json"},body:JSON.stringify({role:"bella-studio"})});
   if(resp.status===401)throw Error("Cloudflare Access sign-in is required.");if(resp.status===429)throw Error("Session limit reached.");if(!resp.ok)throw Error("Bella's Anam session could not start; check the configured provider secret and minutes.");
   const data=await resp.json();if(typeof data.sessionToken!=="string"||data.sessionToken.length<10)throw Error("Invalid avatar session token.");
   avatar=createClient(data.sessionToken);status("Connecting Bella's speaking avatar and microphone…");await avatar.streamToVideoElement("bella-video");
   status("Bella is connected. Speak naturally, then let her respond.");
 }catch(e){if(avatar){try{await avatar.stopStreaming()}catch{}avatar=null}$("bella-video").srcObject=null;status(e.message||"Unable to connect Bella.")}finally{starting=false;buttons()}
};
$("stop").onclick=finishAvatar;
$("camera").onclick=async()=>{
 if(cameraStream){cameraStream.getTracks().forEach(t=>t.stop());cameraStream=null;$("host-video").srcObject=null;$("host-video").hidden=true;$("camera").textContent="Show my camera";$("camera-status").textContent="Camera off.";return}
 try{cameraStream=await navigator.mediaDevices.getUserMedia({video:true,audio:false});$("host-video").srcObject=cameraStream;$("host-video").hidden=false;$("camera").textContent="Turn camera off";$("camera-status").textContent="Local camera preview on; not sent to Bella."}catch(e){$("camera-status").textContent="Camera not available or permission denied."}
};
function clipState(on){$("clip-start").disabled=on;$("clip-stop").disabled=!on}
function cleanCapture(){captureStream?.getTracks().forEach(t=>t.stop());captureStream=null;captureRecorder=null;clipState(false)}
$("clip-start").onclick=async()=>{
 if(captureRecorder||!navigator.mediaDevices?.getDisplayMedia||!window.MediaRecorder){$("clip-status").textContent="Tab capture is unsupported in this browser. Use a desktop screen recorder instead.";return}
 try{
   captureStream=await navigator.mediaDevices.getDisplayMedia({video:{frameRate:30},audio:true});
   const type=["video/webm;codecs=vp8,opus","video/webm"].find(MediaRecorder.isTypeSupported);
   captureRecorder=new MediaRecorder(captureStream,type?{mimeType:type}:undefined);
   clipChunks=[];
   if(clipUrl){URL.revokeObjectURL(clipUrl);clipUrl=null}$("clip-download").replaceChildren();
   const hasAudio=captureStream.getAudioTracks().length>0;
   captureRecorder.ondataavailable=e=>{if(e.data.size)clipChunks.push(e.data)};
   captureRecorder.onstop=()=>{
     const blob=new Blob(clipChunks,{type:captureRecorder?.mimeType||"video/webm"});
     if(blob.size){clipUrl=URL.createObjectURL(blob);const a=document.createElement("a");a.href=clipUrl;a.download="you-talking-to-me-bella-clip-"+Date.now()+".webm";a.textContent="Download captured clip ("+(blob.size/1048576).toFixed(1)+" MB)";$("clip-download").replaceChildren(a)}
     $("clip-status").textContent=blob.size?"Capture completed. Review video and audio before posting. File is not uploaded.":"No clip data was captured.";
     cleanCapture();
   };
   captureStream.getVideoTracks().forEach(t=>t.addEventListener("ended",()=>{if(captureRecorder?.state==="recording")captureRecorder.stop()},{once:true}));
   captureRecorder.start(1000);clipState(true);
   $("clip-status").textContent="Capturing selected screen/tab "+(hasAudio?"with an audio track":"WITHOUT audio")+". Make sure Freddy and Bella are both audible.";
 }catch(e){cleanCapture();$("clip-status").textContent="Capture canceled, unsupported or blocked. Nothing recorded."}
};
$("clip-stop").onclick=()=>{if(captureRecorder?.state==="recording"){captureRecorder.stop();clipState(false);$("clip-status").textContent="Finishing capture…"}};
try{$("topic").value=localStorage.getItem("freddys-podcast-bella-topic")||""}catch{}
$("save-topic").onclick=()=>{try{localStorage.setItem("freddys-podcast-bella-topic",$("topic").value.slice(0,1000));$("topic-status").textContent="Saved on this device only."}catch{$("topic-status").textContent="Local storage unavailable; copy your topic manually."}};
window.addEventListener("pagehide",()=>{if(avatar)void avatar.stopStreaming();cameraStream?.getTracks().forEach(t=>t.stop());captureStream?.getTracks().forEach(t=>t.stop())});
buttons();clipState(false);
