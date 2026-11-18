import { Conversation } from "@elevenlabs/client";

const PEOPLE = Object.freeze({
  bella:"Bella",david:"David",cassidy:"Cassidy",
  roger:"Roger",sarah:"Sarah",adam:"Adam Stone",
});
const $ = id => document.getElementById(id);
let starting = false;
let active = null;
let initialRole = "bella";
let muted = false;

function textStatus(value) { $("status").textContent = value; }
function enabled(on) {
  $("start").disabled = Boolean(on);
  $("stop").disabled = !on;
  $("mute").disabled = !on;
  $("message").disabled = !on;
  $("send").disabled = !on;
}
function speechMode(mode) {
  const speaking = mode && mode.mode === "speaking";
  const orb = $("voice-orb");
  orb.classList.toggle("speaking", speaking);
  orb.classList.toggle("listening", Boolean(mode && mode.mode === "listening"));
  orb.setAttribute("aria-label", speaking ? "Voice agent is speaking" : "Voice agent is listening");
}
function transcript(text, who) {
  if (!text || typeof text !== "string") return;
  const box = $("transcript");
  const row = document.createElement("div");
  row.className = "utterance";
  const speaker = document.createElement("strong");
  speaker.textContent = who;
  const p = document.createElement("p");
  p.textContent = text.slice(0, 1500);
  row.append(speaker,p);
  if (box.children.length === 1 && box.querySelector("p.muted")) box.replaceChildren();
  box.append(row);
  while (box.children.length > 80) box.firstChild.remove();
  box.scrollTop = box.scrollHeight;
}
function selectRole(role) {
  if (!(role in PEOPLE)) return;
  initialRole = role;
  document.querySelectorAll("[data-role]").forEach(button=>{
    const chosen = button.dataset.role === role;
    button.classList.toggle("selected",chosen);
    button.setAttribute("aria-pressed",chosen?"true":"false");
  });
  $("start").textContent = "Start conversation with " + PEOPLE[role];
  if (active) {
    $("speaker-note").textContent = "Selecting a portrait does not change an active voice call. To hand off, ask the employee by voice or send a message. The selected image is not an authenticated speaker indicator.";
  }
}

document.querySelectorAll("[data-role]").forEach(button=>{
  button.addEventListener("click",()=>selectRole(button.dataset.role));
});

async function launch() {
  if (active || starting) return;
  starting = true;
  $("start").disabled = true;
  textStatus("Requesting secure CEO voice session…");
  const role = initialRole;
  try {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      throw Error("HTTPS and microphone support are required.");
    }
    // Explicit user-initiated consent; release this preflight stream immediately.
    const mic = await navigator.mediaDevices.getUserMedia({ audio:true });
    mic.getTracks().forEach(track=>track.stop());
    const response = await fetch("/api/session", {
      method:"POST",
      credentials:"same-origin",
      cache:"no-store",
      headers:{"Content-Type":"application/json","Accept":"application/json"},
      body:JSON.stringify({role}),
    });
    if (!response.ok) {
      if (response.status===401) throw Error("Sign in through your protected CEO boardroom before starting a call.");
      if (response.status===429) throw Error("Voice session limit reached. Try again later.");
      if (response.status===503) throw Error("Private voice gateway needs the CEO's hosting and secrets configuration.");
      throw Error("The voice service is unavailable. No session started.");
    }
    const result = await response.json();
    if (typeof result.signedUrl !== "string" ||
        !result.signedUrl.startsWith("wss://api.elevenlabs.io/v1/convai/conversation")) {
      throw Error("Secure session response was not valid.");
    }
    // Signed URLs are ephemeral and are deliberately never logged, stored,
    // placed in markup, or included in outgoing hyperlinks.
    active = await Conversation.startSession({
      signedUrl:result.signedUrl,
      connectionType:"websocket",
      onConnect:()=>{enabled(true);textStatus("Connected. Speak to your specialist or request a handoff.");},
      onDisconnect:()=>{
        active=null;
        muted=false;
        speechMode(null);
        enabled(false);
        $("mute").textContent="Mute microphone";
        textStatus("Disconnected. Start a new call when ready.");
      },
      onModeChange:speechMode,
      onMessage:message=>{
        const value = typeof message?.message === "string" ? message.message : "";
        const who = message?.source === "user" ? "CEO (microphone)" : "Voice employee (identity not independently authenticated)";
        transcript(value, who);
      },
      onError:()=>textStatus("The voice call encountered an error. You may end and retry."),
    });
    textStatus("Connected to an ElevenLabs voice session. Ask for another employee by name.");
    enabled(true);
  } catch(err) {
    textStatus(err instanceof Error ? err.message : "Unable to start a voice session.");
    if (!active) enabled(false);
  } finally {
    starting=false;
    if(!active) $("start").disabled=false;
  }
}

$("start").addEventListener("click",launch);
$("stop").addEventListener("click",async()=>{
  const current=active;
  if (!current) return;
  $("stop").disabled=true;
  try { await current.endSession(); }
  finally {
    active=null;
    muted=false;
    speechMode(null);
    enabled(false);
    textStatus("Call ended. No votes or betting orders were recorded.");
  }
});
$("mute").addEventListener("click",()=>{
  if (!active) return;
  muted=!muted;
  active.setMicMuted(muted);
  $("mute").textContent=muted?"Unmute microphone":"Mute microphone";
  textStatus(muted?"Microphone muted":"Microphone unmuted");
});
$("text-form").addEventListener("submit",event=>{
  event.preventDefault();
  const field=$("message");
  const value=field.value.trim();
  if (!active || !value) return;
  active.sendUserMessage(value);
  field.value="";
  transcript(value,"CEO (text)");
});
window.addEventListener("pagehide",()=>{
  if (active) { void active.endSession(); active=null; }
});
