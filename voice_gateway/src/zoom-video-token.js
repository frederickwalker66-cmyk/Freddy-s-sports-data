/**
 * Zoom Video SDK JWT on the protected Cloudflare Worker.
 * No Zoom API calls and no key/secret exposure to browsers or repositories.
 * Zoom official Video SDK JWT: HS256, app_key, role_type, tpc, version, iat, exp.
 */
export function zoomVideoChecks(env) {
  return {
    zoom_video_sdk_key_present: typeof env?.ZOOM_VIDEO_SDK_KEY==="string" &&
      env.ZOOM_VIDEO_SDK_KEY.length>=8,
    zoom_video_sdk_secret_present: typeof env?.ZOOM_VIDEO_SDK_SECRET==="string" &&
      env.ZOOM_VIDEO_SDK_SECRET.length>=16,
    zoom_video_session_topic_valid: typeof env?.ZOOM_VIDEO_SESSION_TOPIC==="string" &&
      /^[A-Za-z0-9 _-]{3,80}$/.test(env.ZOOM_VIDEO_SESSION_TOPIC),
    signing_limiter_bound: !!env?.VOICE_LIMITER && typeof env.VOICE_LIMITER.limit==="function",
  };
}
export function zoomVideoReadiness(env) {
  const checks=zoomVideoChecks(env);
  return {
    status:Object.values(checks).every(Boolean)?"CONFIGURATION_READY":"CONFIGURATION_INCOMPLETE",
    checks,
    video_sdk_session_started:false,
    connected_zoom_video_users:0,
    connected_ai_video_bots:0,
    zoom_sdk_provider_called:false,
    whatsapp_video_supported:false,
    signed_token_created:false,
  };
}
function b64url(bytes) {
  let str="";
  for(const byte of bytes)str+=String.fromCharCode(byte);
  return btoa(str).replaceAll("+","-").replaceAll("/","_").replace(/=+$/,"");
}
function b64json(input) {
  return b64url(new TextEncoder().encode(JSON.stringify(input)));
}
export async function signZoomVideoToken(env,{nowMs=Date.now()}={}) {
  if(!Object.values(zoomVideoChecks(env)).every(Boolean))
    throw Error("zoom_video_not_configured");
  const iat=Math.floor(nowMs/1000)-30;
  const payload={
    app_key:env.ZOOM_VIDEO_SDK_KEY,
    role_type:1,
    tpc:env.ZOOM_VIDEO_SESSION_TOPIC,
    version:1,
    iat,
    exp:iat+3600,
    user_key:"freddys-v9-ceo",
    audio_webrtc_mode:1,
  };
  const header=b64json({alg:"HS256",typ:"JWT"});
  const body=b64json(payload);
  const signingInput=header+"."+body;
  const key=await crypto.subtle.importKey("raw",
    new TextEncoder().encode(env.ZOOM_VIDEO_SDK_SECRET),
    {name:"HMAC",hash:"SHA-256"},false,["sign"]);
  const signature=await crypto.subtle.sign("HMAC",key,new TextEncoder().encode(signingInput));
  return {token:signingInput+"."+b64url(new Uint8Array(signature)),topic:payload.tpc,
    expiresAt:payload.exp};
}
