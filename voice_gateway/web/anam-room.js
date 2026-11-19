import { createClient } from "@anam-ai/js-sdk";
const $ = id => document.getElementById(id);
const NAMES = Object.freeze({
  bella:"Bella",david:"David",cassidy:"Cassidy",roger:"Roger",sarah:"Sarah",adam:"Adam Stone",
  "bella-studio":"Bella · Podcast Studio","roger-studio":"Roger · Podcast Studio","cassidy-studio":"Cassidy · Podcast Studio",
});
let selected = "bella";
let client = null;
let starting = false;
const buttons = [...document.querySelectorAll("[data-role]")];
const status = message => { $("status").textContent = message; };
const controls = () => {
  $("start").disabled = Boolean(client) || starting;
  $("stop").disabled = !client && !starting;
  $("check").disabled = starting;
  buttons.forEach(button => {button.disabled = starting || Boolean(client);});
};
buttons.forEach(button => button.addEventListener("click",()=>{
  if (client || starting) return;
  const role = button.dataset.role;
  if (!Object.hasOwn(NAMES,role)) return;
  selected=role;
  buttons.forEach(item=>{const active=item.dataset.role===selected;item.classList.toggle("selected",active);item.setAttribute("aria-pressed",String(active));});
  $("selected-name").textContent=NAMES[role];
  status("Ready. No call started.");
}));
$("check").addEventListener("click",async()=>{
  status("Checking CEO-only Anam setup without starting a call…");
  try{
    const response=await fetch("/api/anam/readiness",{credentials:"same-origin",cache:"no-store"});
    if(response.status===401)throw Error("CEO Cloudflare Access authentication is required.");
    if(!response.ok)throw Error("Anam readiness endpoint is unavailable.");
    const data=await response.json();
    status(data.ready?"Anam session signing configured. Ready for an explicit Start.":"Anam API key or Worker rate limiter is not configured. Add ANAM_API_KEY as a Cloudflare Worker secret.");
  }catch(e){status(e instanceof Error?e.message:"Setup check failed.");}
});
$("start").addEventListener("click",async()=>{
  if(client||starting)return;
  starting=true;controls();
  status("Requesting a private Anam session for "+NAMES[selected]+"…");
  try{
    if(!window.isSecureContext || !navigator.mediaDevices?.getUserMedia)throw Error("An HTTPS browser with microphone access is required.");
    const response=await fetch("/api/anam/session-token",{method:"POST",credentials:"same-origin",cache:"no-store",headers:{"Content-Type":"application/json","Accept":"application/json"},body:JSON.stringify({role:selected})});
    if(response.status===401)throw Error("Sign in through Cloudflare Access before starting an avatar.");
    if(response.status===429)throw Error("Anam session start limit reached.");
    if(response.status===503)throw Error("Set ANAM_API_KEY in the private Cloudflare Worker's Secrets to enable Anam.");
    if(!response.ok)throw Error("Anam session token was not available. No call started.");
    const data=await response.json();
    if(typeof data.sessionToken!=="string" || data.sessionToken.length<10)throw Error("Invalid Anam session token.");
    client=createClient(data.sessionToken);
    status("Connecting live avatar and microphone…");
    await client.streamToVideoElement("persona-video");
    status("Connected with "+NAMES[selected]+". Talk now; End conversation to disconnect.");
  }catch(e){
    if(client){try{await client.stopStreaming();}catch{} client=null;}
    $("persona-video").srcObject=null;
    status(e instanceof Error?e.message:"Could not start Anam video.");
  }finally{starting=false;controls();}
});
$("stop").addEventListener("click",async()=>{
  if(!client)return;
  const active=client;client=null;controls();
  try{await active.stopStreaming();}catch{}
  $("persona-video").srcObject=null;
  status("Video conversation ended. No active Anam session.");
});
window.addEventListener("pagehide",()=>{if(client){void client.stopStreaming();client=null;}});
controls();
