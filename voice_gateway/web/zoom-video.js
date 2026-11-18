"use strict";
/**
 * Freddy's Picks AI V9 Zoom Video SDK web client.
 * No external video/audio session begins until the CEO explicitly presses Join.
 * Agent portraits are placeholders; do not represent them as live SDK users.
 */
const $ = id => document.getElementById(id);
const status = message => { $("zoom-status").textContent = message; };
let zoom = null;
let client = null;
let stream = null;
let connected = false;
let busy = false;
let audioOn = false;
let audioMuted = false;
let videoOn = false;
const renderedUsers = new Set();

function controls() {
  $("join-zoom-sdk").disabled = connected || busy;
  $("enable-zoom-audio").disabled = !connected || audioOn;
  $("mute-zoom-audio").disabled = !connected || !audioOn;
  $("mute-zoom-audio").textContent = audioMuted ? "Unmute microphone" : "Mute microphone";
  $("enable-zoom-video").disabled = !connected || videoOn;
  $("disable-zoom-video").disabled = !connected || !videoOn;
  $("leave-zoom-sdk").disabled = !connected && !busy;
}
function count() {
  const n = connected && client ? client.getAllUser().length : 0;
  $("connected-count").textContent = n + (n === 1 ? " live participant" : " live participants");
}
function removeVideo(element) {
  const elements = Array.isArray(element) ? element : element ? [element] : [];
  for(const item of elements) if(typeof item.remove === "function") item.remove();
}
async function attach(userId) {
  if(!stream || renderedUsers.has(userId)) return;
  try {
    const element = await stream.attachVideo(userId, 3);
    $("live-zoom-video").appendChild(element);
    renderedUsers.add(userId);
  } catch {
    status("A camera stream could not be displayed. Check video permissions or device support.");
  }
}
async function detach(userId) {
  if(!stream) return;
  renderedUsers.delete(userId);
  try { removeVideo(await stream.detachVideo(userId)); } catch { /* media may already be detached */ }
}
function bindEvents() {
  client.on("peer-video-state-change",async ({action,userId})=>{
    if(!connected) return;
    if(action==="Start") await attach(userId);
    if(action==="Stop") await detach(userId);
  });
  client.on("user-added",count);
  client.on("user-removed",async users=>{
    for(const user of users||[]) await detach(user.userId);
    count();
  });
  client.on("connection-change",evt=>{
    if(evt.state==="Reconnecting")status("Zoom is reconnecting. Keep this page open.");
    if(evt.state==="Connected")status("Connected to Zoom Video SDK. Enable camera or microphone when ready.");
    if(evt.state==="Closed"||evt.state==="Fail"){
      connected=false; busy=false; audioOn=false; videoOn=false; audioMuted=false;
      renderedUsers.clear();
      $("live-zoom-video").replaceChildren();
      count(); controls();
      status(evt.state==="Closed"?"Zoom meeting ended.":"Zoom connection failed. Try again after checking your setup.");
    }
  });
  client.on("active-media-failed",()=>{
    status("Your camera or microphone was interrupted. Check browser permissions and reconnect.");
  });
}

$("check-zoom-setup").addEventListener("click",async()=>{
  const button=$("check-zoom-setup"); button.disabled=true;
  $("zoom-setup-result").textContent="Checking private Zoom SDK setup without starting a meeting…";
  try {
    const res=await fetch("/api/zoom-video-readiness",{
      method:"GET",credentials:"same-origin",cache:"no-store",
      headers:{"Accept":"application/json"},
    });
    if(res.status===401)throw Error("Cloudflare CEO authentication required.");
    if(!res.ok)throw Error("Zoom setup checker unavailable. Confirm the current Cloudflare deployment.");
    const report=await res.json();
    if(report.status==="CONFIGURATION_READY"){
      $("zoom-setup-result").textContent=
        "Zoom Video SDK credentials and room topic are configured. You can choose Join when you approve potential Zoom usage charges. Six AI video bot feeds are not connected.";
    } else {
      const missing=Object.entries(report.checks||{}).filter(([,v])=>v!==true)
        .map(([k])=>k.replaceAll("_"," "));
      $("zoom-setup-result").textContent=
        "Zoom Video SDK configuration incomplete: "+(missing.join(", ")||"unknown issue")+
        ". Configure ZOOM_VIDEO_SDK_KEY, ZOOM_VIDEO_SDK_SECRET and ZOOM_VIDEO_SESSION_TOPIC in Cloudflare Worker Secrets.";
    }
  } catch(e) {
    $("zoom-setup-result").textContent=e instanceof Error?e.message:"Zoom configuration check failed.";
  } finally { button.disabled=false; }
});

$("join-zoom-sdk").addEventListener("click",async()=>{
  if(connected||busy)return;
  busy=true;controls();status("Requesting an owner-authenticated Zoom session token…");
  try {
    if(!window.isSecureContext)throw Error("The Zoom room requires HTTPS.");
    zoom=window.WebVideoSDK?.default || window.WebVideoSDK;
    if(!zoom || typeof zoom.createClient!=="function")
      throw Error("Zoom Video SDK failed to load. Check network and content blockers.");
    const support=zoom.checkSystemRequirements();
    if(!support.video || !support.audio)
      throw Error("This browser does not support the needed Zoom video and audio features.");
    // This request creates a short-lived Zoom token ONLY after CEO clicks Join.
    const res=await fetch("/api/zoom-video-token",{
      method:"POST",credentials:"same-origin",cache:"no-store",
      headers:{"Content-Type":"application/json","Accept":"application/json"},
      body:JSON.stringify({confirm:"join"}),
    });
    if(res.status===401)throw Error("Sign in through Cloudflare Access.");
    if(res.status===429)throw Error("Zoom session rate limit reached. Try later.");
    if(res.status===503)throw Error("Zoom Video SDK credentials are not configured in Cloudflare.");
    if(!res.ok)throw Error("Zoom token request failed. No meeting started.");
    const auth=await res.json();
    if(typeof auth.token!=="string"||typeof auth.topic!=="string")
      throw Error("Zoom session token response was invalid.");
    client=zoom.createClient();
    await client.init("en-US","Global",{patchJsMedia:true,enforceMultipleVideos:true});
    bindEvents();
    status("Connecting to Zoom Video SDK…");
    await client.join(auth.topic,auth.token,"Freddy CEO","");
    // Token intentionally discarded after join; never persisted/logged.
    connected=true;stream=client.getMediaStream();
    for(const user of client.getAllUser()){
      if(user.bVideoOn) await attach(user.userId);
    }
    status("Connected. Camera and microphone remain off until you enable them.");
    count();
  }catch(e){
    status(e instanceof Error?e.message:"Zoom join failed.");
    if(client && !connected)try{await client.leave();}catch{/* no session */}
    if(!connected)client=null;
  }finally{busy=false;controls();}
});

$("enable-zoom-audio").addEventListener("click",async()=>{
  if(!connected||!stream)return;
  try{await stream.startAudio();audioOn=true;audioMuted=false;status("Microphone connected to Zoom.");}
  catch{status("Could not start microphone. Allow microphone permissions and retry.");}
  controls();
});
$("mute-zoom-audio").addEventListener("click",async()=>{
  if(!connected||!audioOn)return;
  try{
    if(audioMuted){await stream.unmuteAudio();audioMuted=false;}
    else{await stream.muteAudio();audioMuted=true;}
    status(audioMuted?"Zoom microphone muted.":"Zoom microphone unmuted.");
  }catch{status("Could not change microphone state.");}
  controls();
});
$("enable-zoom-video").addEventListener("click",async()=>{
  if(!connected||!stream)return;
  try{
    await stream.startVideo();
    videoOn=true;
    await attach(client.getCurrentUserInfo().userId);
    status("Camera on. Your Zoom video is visible in the connected-participants area.");
  }catch{status("Unable to start camera. Check camera permissions and Zoom browser compatibility.");}
  controls();
});
$("disable-zoom-video").addEventListener("click",async()=>{
  if(!connected||!stream)return;
  try{
    await stream.stopVideo();
    await detach(client.getCurrentUserInfo().userId);
    videoOn=false;
    status("Camera stopped.");
  }catch{status("Unable to stop camera. You can leave the Zoom session.");}
  controls();
});
$("leave-zoom-sdk").addEventListener("click",async()=>{
  if(!client)return;
  busy=true;controls();
  try{await client.leave();}catch{/* disconnected elsewhere */}
  connected=false;busy=false;audioOn=false;audioMuted=false;videoOn=false;stream=null;
  renderedUsers.clear();$("live-zoom-video").replaceChildren();
  count();controls();status("You left the Zoom Video SDK session. No virtual staff bots joined.");
});
window.addEventListener("pagehide",()=>{if(client && connected)void client.leave();});
controls();
