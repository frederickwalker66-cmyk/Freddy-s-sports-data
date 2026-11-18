/**
 * Owner-authorized Zoom Video SDK JWT signer.
 * This signs a token LOCALLY using Cloudflare WebCrypto; it never calls Zoom.
 * Zoom session creation is a separate browser-initiated step which may incur costs.
 */
export const VIDEO_SESSION_NAME = "Freddys V9 CEO Private Video";
const encoder = new TextEncoder();

export function zoomVideoConfigured(env){
  return typeof env?.ZOOM_VIDEO_SDK_KEY === "string" &&
    env.ZOOM_VIDEO_SDK_KEY.length >= 8 &&
    typeof env?.ZOOM_VIDEO_SDK_SECRET === "string" &&
    env.ZOOM_VIDEO_SDK_SECRET.length >= 16;
}

function base64url(bytes){
  let result = "";
  for(const byte of bytes) result += String.fromCharCode(byte);
  return btoa(result).replace(/=/g,"").replace(/\+/g,"-").replace(/\//g,"_");
}
function base64urlJson(data){return base64url(encoder.encode(JSON.stringify(data)));}

export async function createZoomVideoSdkJwt(env, nowMs=Date.now()){
  if(!zoomVideoConfigured(env)) throw Error("zoom-video-sdk-not-configured");
  const iat = Math.floor(nowMs/1000)-30;
  // Zoom requires exp >= 1800 seconds after iat.
  const payload = {
    app_key:env.ZOOM_VIDEO_SDK_KEY,
    tpc:VIDEO_SESSION_NAME,
    role_type:1, // The only authorized sign-in is the CEO.
    version:1,
    iat,
    exp:iat+3600,
    user_key:"FreddyCEO",
  };
  const header=base64urlJson({alg:"HS256",typ:"JWT"});
  const body=base64urlJson(payload);
  const input=header+"."+body;
  const signingKey=await crypto.subtle.importKey(
    "raw",encoder.encode(env.ZOOM_VIDEO_SDK_SECRET),
    {name:"HMAC",hash:"SHA-256"},false,["sign"]);
  const signature=await crypto.subtle.sign("HMAC",signingKey,encoder.encode(input));
  return {signature:input+"."+base64url(new Uint8Array(signature)),
    sessionName:VIDEO_SESSION_NAME, expiresAt:payload.exp};
}
