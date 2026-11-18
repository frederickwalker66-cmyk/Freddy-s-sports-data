/**
 * Freddy's Picks AI V9 — Zoom video participant bridge coordinator.
 *
 * This is a transport-independent controller, NOT a Zoom bot or Meeting SDK.
 * A separate authorized Linux Meeting SDK runtime with permitted virtual
 * microphone/video-frame injection must implement the adapter.
 * No network, Zoom OAuth, media rendering, or ElevenLabs calls occur here.
 */
export const EMPLOYEES = Object.freeze([
  {role:"bella", displayName:"Bella"},
  {role:"david", displayName:"David"},
  {role:"cassidy", displayName:"Cassidy"},
  {role:"roger", displayName:"Roger"},
  {role:"sarah", displayName:"Sarah"},
  {role:"adam", displayName:"Adam Stone"},
]);

export const UNSUPPORTED_PLATFORMS = Object.freeze({
  whatsapp: "WhatsApp Business Calling API is voice-only and has no six-bot native video group-call integration.",
  google_meet: "A production Google Meet AI video-publishing bot integration is not implemented.",
});

export function validateZoomMeetingUrl(input) {
  if(typeof input!=="string" || input.length>1000) return false;
  try {
    const u=new URL(input);
    const h=u.hostname.toLowerCase();
    return u.protocol==="https:" &&
      (h==="zoom.us" || h.endsWith(".zoom.us")) &&
      !u.username && !u.password && !u.port && !u.hash &&
      /^\/j\/[0-9]{9,11}\/?$/.test(u.pathname) &&
      [...u.searchParams.keys()].every(k=>k==="pwd") &&
      u.searchParams.getAll("pwd").length <=1;
  } catch { return false; }
}

export function readiness(config={}) {
  const required = {
    zoom_meeting_url_valid: validateZoomMeetingUrl(config.zoomMeetingUrl),
    zoom_bot_account_authorized: config.zoomAuthorized === true,
    zoom_meeting_sdk_credentials_present: config.zoomSdkCredentialsPresent === true,
    zoom_linux_bot_runtime_deployed: config.zoomBotRuntimeDeployed === true,
    outbound_video_avatar_renderer_available: config.videoAvatarRendererAvailable === true,
    live_audio_bridge_available: config.liveAudioBridgeAvailable === true,
    six_distinct_bot_identities_authorized: config.sixBotIdentitiesAuthorized === true,
    user_consent_for_costs: config.userConsentForCosts === true,
  };
  return Object.freeze({
    status: Object.values(required).every(Boolean)
      ? "EXTERNAL_ADAPTER_CONFIGURATION_CLAIMED_NOT_VERIFIED"
      : "NOT_READY",
    checks: required,
    required_participants: EMPLOYEES.length,
    connected_participants: 0,
    zoom_meeting_created: false,
    zoom_media_sent: false,
    whatsapp_native_video_supported: false,
    paid_call_started: false,
    note: "Pure preflight. This package does not implement or validate the external Zoom SDK bot or media runtime.",
  });
}

export class SixAgentZoomCoordinator {
  #adapter;
  #active = [];
  constructor(adapter){
    if(!adapter || typeof adapter.joinParticipant!=="function" ||
        typeof adapter.leaveParticipant!=="function")
      throw Error("Authorized Zoom Meeting SDK adapter required");
    this.#adapter=adapter;
  }
  get status(){
    return {active:this.#active.map(x=>x.role),count:this.#active.length};
  }
  async joinAll({authorizedCEO,explicitStart,costsApproved,meetingUrl}){
    if(authorizedCEO!==true || explicitStart!==true || costsApproved!==true)
      throw Error("CEO identity, manual start and cost approval required");
    if(!validateZoomMeetingUrl(meetingUrl)) throw Error("Invalid private Zoom meeting URL");
    if(this.#active.length) throw Error("Zoom conference already started");
    try {
      for(const participant of EMPLOYEES){
        // An adapter must implement actual SDK participant join and media streams.
        const receipt=await this.#adapter.joinParticipant({
          role:participant.role, displayName:participant.displayName,meetingUrl
        });
        if(receipt?.joined!==true || receipt?.participantId===undefined)
          throw Error("No verified meeting participant join receipt");
        this.#active.push({...participant,id:String(receipt.participantId)});
      }
      const ids=new Set(this.#active.map(x=>x.id));
      if(ids.size!==6)throw Error("Six unique participant identities were not confirmed");
      return this.status;
    } catch(error){
      await this.leaveAll();
      throw error;
    }
  }
  async leaveAll(){
    const leaving=[...this.#active].reverse();
    this.#active=[];
    for(const item of leaving){
      try {await this.#adapter.leaveParticipant({role:item.role,participantId:item.id});}
      catch { /* maintain fail-closed local state; external service must verify cleanup */ }
    }
    return this.status;
  }
}
