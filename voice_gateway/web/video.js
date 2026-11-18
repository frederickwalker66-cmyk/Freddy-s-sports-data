// Zoom Video SDK for Web. No Zoom or ElevenLabs session starts on page load.
// Import only upon explicit CEO-approved join. Private JWT comes from Worker.
const $=id=>document.getElementById(id);
const SDK_SRC="https://source.zoom.us/videosdk/zoom-video-2.6.10.min.js";
let zoomSdkPromise=null,client=null,stream=null,joined=false,joining=false;
let cameraOn=false,audioOn=false,audioMuted=false;
const remoteVideoIds=new Set();

function state(text){
  $("zoom-status").textContent=text;
  $("zoom-state").textContent=joined?"Connected":joining?"Connecting":"Disconnected";
}
function controls(){
  $("join").disabled=joined||joining;
  $("leave").disabled=!joined;
  $("camera").disabled=!joined;
  $("audio").disabled=!joined||audioOn;
  $("mute").disabled=!joined||!audioOn;
  $("camera").textContent=cameraOn?"Stop camera":"Start camera";
  $("audio").textContent=audioOn?"Microphone connected":"Connect microphone";
  $("mute").textContent=audioMuted?"Unmute microphone":"Mute microphone";
  $("camera-label").textContent=cameraOn?"Camera on":"Camera off · permissions are never requested automatically";
}
function sdk(){
  if(zoomSdkPromise)return zoomSdkPromise;
  zoomSdkPromise=new Promise((resolve,reject)=>{
    const script=document.createElement("script");
    script.src=SDK_SRC;
    script.async=true;
    script.onload=()=>{
      const sdk=window.WebVideoSDK?.default || window.WebVideoSDK;
      if(sdk && typeof sdk.createClient==="function")resolve(sdk);
      else reject(Error("Zoom Video SDK did not initialize. Check browser or network restrictions."));
    };
    script.onerror=()=>reject(Error("Zoom CDN did not load. Please check your internet connection and try again."));
    document.head.append(script);
  }).catch(error=>{zoomSdkPromise=null;throw error;});
  return zoomSdkPromise;
}
function zoomError(error){
  return error?.reason || error?.message || "Zoom could not complete this request.";
}
async function zoomReadiness(){
  const b=$("check-zoom");
  b.disabled=true;
  $("config-report").textContent="Checking Cloudflare configuration only (no Zoom API calls)…";
  try{
    const response=await fetch("/api/zoom-video-readiness",{
      credentials:"same-origin",cache:"no-store",headers:{Accept:"application/json"},
    });
    if(response.status===401)throw Error("Sign in through Cloudflare Access first.");
    if(!response.ok)throw Error("Zoom setup check not available; wait for the new Cloudflare deployment.");
    const data=await response.json();
    $("config-report").textContent=data.zoom_video_sdk_configured
      ?"Zoom Video SDK key and secret detected. No Zoom session has started. The six employee bot processes are still not connected."
      :"Add ZOOM_VIDEO_SDK_KEY and ZOOM_VIDEO_SDK_SECRET privately in Cloudflare Worker Settings → Variables and Secrets. Do not paste them into chat or GitHub.";
  }catch(error){$("config-report").textContent=zoomError(error);}
  finally{b.disabled=false;}
}

async function renderUser(user){
  if(!joined||!stream||!user||!user.bVideoOn)return;
  const id=user.userId;
  if(id===client.getCurrentUserInfo()?.userId || remoteVideoIds.has(id))return;
  const card=document.querySelector('[data-remote-id="'+String(id)+'"]');
  if(!card)return;
  try{
    const element=await stream.attachVideo(id,2);
    if(!joined||!card.isConnected)return;
    const host=card.querySelector("video-player-container");
    host.replaceChildren(element);
    remoteVideoIds.add(id);
  }catch{
    const label=card.querySelector(".remote-label");
    if(label)label.textContent="Video stream unavailable";
  }
}
async function updateRemote(){
  if(!joined||!client)return;
  const me=client.getCurrentUserInfo()?.userId;
  const users=(client.getAllUser()||[]).filter(user=>user.userId!==me);
  $("remote-count").textContent=String(users.length);
  const area=$("remote-tiles");
  const ids=new Set(users.map(u=>u.userId));
  for(const id of [...remoteVideoIds]){
    if(!ids.has(id)){remoteVideoIds.delete(id);try{await stream?.detachVideo(id);}catch{}}
  }
  if(!users.length){
    area.replaceChildren();
    const p=document.createElement("p");p.className="caption";
    p.textContent="No other Video SDK clients connected. Employee portraits are not remote video participants.";
    area.append(p);
    return;
  }
  for(const old of [...area.querySelectorAll("[data-remote-id]")]){
    if(!ids.has(Number(old.dataset.remoteId)))old.remove();
  }
  for(const user of users){
    let card=area.querySelector('[data-remote-id="'+String(user.userId)+'"]');
    if(!card){
      card=document.createElement("div");card.className="remote-item";
      card.dataset.remoteId=String(user.userId);
      const name=document.createElement("strong");
      // Zoom participant's actual SDK-provided display name, never a guessed AI identity.
      name.textContent=(user.displayName||"Zoom participant").slice(0,70);
      const host=document.createElement("video-player-container");
      const label=document.createElement("p");label.className="caption remote-label";
      label.textContent="Camera off";
      card.append(name,host,label);
      area.append(card);
    }
    if(user.bVideoOn)await renderUser(user);
  }
}
function installEvents(){
  client.on("user-added",()=>{void updateRemote();});
  client.on("user-updated",()=>{void updateRemote();});
  client.on("user-removed",()=>{void updateRemote();});
  client.on("peer-video-state-change",()=>{void updateRemote();});
  client.on("auto-play-audio-failed",()=>state("Your browser blocked audio autoplay. Tap Connect microphone to enable audio."));
}

async function join(){
  if(joined||joining)return;
  if(!$("approve-join").checked){
    state("Check the approval box first. Joining can incur Zoom Video SDK usage charges.");
    return;
  }
  joining=true;controls();
  state("Requesting CEO-only Zoom Video SDK authorization…");
  try{
    if(!window.isSecureContext)throw Error("HTTPS is required.");
    const response=await fetch("/api/zoom-video-token",{
      method:"POST",credentials:"same-origin",cache:"no-store",
      headers:{"Content-Type":"application/json",Accept:"application/json"},
      body:JSON.stringify({approved:true}),
    });
    if(response.status===401)throw Error("Please sign in with your approved Cloudflare Access account.");
    if(response.status===503)throw Error("Zoom Video SDK key or secret is missing from Cloudflare. No session started.");
    if(!response.ok)throw Error("Private Zoom session authorization was denied. No session started.");
    const auth=await response.json();
    if(typeof auth.token!=="string"||typeof auth.session_name!=="string")
      throw Error("Invalid authorization response");
    state("Loading Zoom Video SDK. No camera or microphone will start automatically…");
    const ZoomVideo=await sdk();
    client=ZoomVideo.createClient();
    await client.init("en-US","Global",{patchJsMedia:true,leaveOnPageUnload:true});
    installEvents();
    state("Joining Zoom Video SDK session. Usage may be billable…");
    await client.join(auth.session_name,auth.token,"Freddy (CEO)","");
    joined=true;
    stream=client.getMediaStream();
    state("Joined private Zoom Video SDK room. Use separate buttons to activate camera/microphone.");
    await updateRemote();
  }catch(error){
    state(zoomError(error));
    try{if(client)await client.leave();}catch{}
    client=null;stream=null;joined=false;
  }finally{joining=false;controls();}
}
async function camera(){
  if(!joined||!stream)return;
  $("camera").disabled=true;
  try{
    if(cameraOn){
      await stream.stopVideo();
      try{await stream.detachVideo(client.getCurrentUserInfo().userId);}catch{}
      $("ceo-video").replaceChildren();
      cameraOn=false;
      state("Camera off.");
    }else{
      await stream.startVideo();
      const element=await stream.attachVideo(client.getCurrentUserInfo().userId,2);
      $("ceo-video").replaceChildren(element);
      cameraOn=true;
      state("Camera on. Video is being sent to your Zoom Video SDK session.");
    }
  }catch(error){state("Camera: "+zoomError(error));}
  finally{controls();}
}
async function audio(){
  if(!joined||!stream||audioOn)return;
  $("audio").disabled=true;
  try{
    await stream.startAudio();
    audioOn=true;audioMuted=false;
    state("Microphone connected to the Zoom Video SDK session.");
  }catch(error){state("Microphone: "+zoomError(error));}
  finally{controls();}
}
async function mute(){
  if(!joined||!stream||!audioOn)return;
  $("mute").disabled=true;
  try{
    if(audioMuted){await stream.unmuteAudio();audioMuted=false;}
    else{await stream.muteAudio();audioMuted=true;}
    state(audioMuted?"Microphone muted.":"Microphone unmuted.");
  }catch(error){state(zoomError(error));}
  finally{controls();}
}
async function leave(){
  if(!joined && !client)return;
  $("leave").disabled=true;
  try{
    if(cameraOn)try{await stream.stopVideo();}catch{}
    if(audioOn)try{await stream.stopAudio();}catch{}
    if(client)await client.leave();
  }catch(error){state("Leave request: "+zoomError(error));}
  finally{
    client=null;stream=null;joined=false;joining=false;
    cameraOn=false;audioOn=false;audioMuted=false;
    remoteVideoIds.clear();
    $("ceo-video").replaceChildren();
    $("remote-tiles").replaceChildren();
    $("remote-count").textContent="0";
    state("Disconnected. No Zoom meeting is running in this tab.");
    controls();
  }
}
$("check-zoom").addEventListener("click",zoomReadiness);
$("join").addEventListener("click",join);
$("camera").addEventListener("click",camera);
$("audio").addEventListener("click",audio);
$("mute").addEventListener("click",mute);
$("leave").addEventListener("click",()=>{void leave();});
window.addEventListener("pagehide",()=>{
  if(joined && client){void client.leave();joined=false;}
});
controls();
