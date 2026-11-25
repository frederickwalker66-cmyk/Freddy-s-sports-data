import {zoomVideoReadiness,signZoomVideoToken,zoomVideoChecks} from "./zoom-video-token.js";

/**
 * Freddy's V9 private voice gateway, intentionally NOT deployed by GitHub Actions.
 *
 * Cloudflare Access must protect the Worker, and this Worker independently
 * verifies Access JWT signature, issuer, audience, email and expiration.
 * No API key, signed session URL, voice agent ID or CEO email belongs in git.
 */
const ROLES = Object.freeze({
  bella: "ELEVENLABS_BELLA_AGENT_ID",
  david: "ELEVENLABS_DAVID_AGENT_ID",
  cassidy: "ELEVENLABS_CASSIDY_AGENT_ID",
  roger: "ELEVENLABS_ROGER_AGENT_ID",
  sarah: "ELEVENLABS_SARAH_AGENT_ID",
  adam: "ELEVENLABS_ADAM_AGENT_ID",
});

// Persona IDs come from the connected owner's Anam account. These are not API secrets.
const ANAM_PERSONAS = Object.freeze({
  bella:"14d4d30f-220b-4286-8d9e-93bdb6b0e725",
  david:"272ceabe-cf93-4c0a-9ec9-ad678aaee263",
  cassidy:"abf651d6-5de8-4fe9-9cb2-d728484be449",
  roger:"684c4388-4aed-4104-b4a7-16323c05fe45",
  sarah:"6b8b30a6-d11c-41c7-9156-dae9696d396e",
  adam:"6b97e944-0138-461d-ba9f-c8382072e711",
  "bella-studio":"5b176814-9acf-48e5-9253-0530fc48122f",
  "roger-studio":"23074722-867e-4666-b641-bc5ebea64cd0",
  "cassidy-studio":"e415a998-584c-432a-8dbe-b3123555120e",
});

const ANAM_AVATARS = Object.freeze({
  bella:"410bd990-d7ca-4054-bf5b-ce862d249a8a",
  david:"fa2b8027-f776-4485-820f-a79cf8412b6f",
  cassidy:"9bff6b0b-d649-4b28-ae1c-241ec7ebafe3",
  roger:"2a900f85-6f8e-4070-825e-07ac8a55b7c4",
  sarah:"2891de34-9f0c-4b47-a7f5-091844dda047",
  adam:"046fd8cf-e5cb-43d6-9f63-729e5b695c5c",
  "bella-studio":"1957d20f-11c1-494f-bfcf-885925701292",
  "roger-studio":"0f601e66-ac3f-44f8-9834-6eecdd7d58ff",
  "cassidy-studio":"5d0de80c-7668-4bdc-8e9d-c01a82ec62fe",
});

const NO_CACHE = {
  "Cache-Control": "private, no-store, max-age=0",
  "Pragma": "no-cache",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
  "X-Frame-Options": "DENY",
  "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
};

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...NO_CACHE, "Content-Type": "application/json; charset=utf-8" },
  });
}

function fromBase64url(value) {
  if (typeof value !== "string" || !/^[A-Za-z0-9_-]+$/.test(value)) throw Error("bad-jwt-segment");
  const padded = value.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(value.length / 4) * 4, "=");
  const decoded = atob(padded);
  return Uint8Array.from(decoded, c => c.charCodeAt(0));
}

function parseJwtSection(value) {
  return JSON.parse(new TextDecoder().decode(fromBase64url(value)));
}

export async function verifyAccessJwt(token, env, fetcher = fetch, nowMs = Date.now()) {
  if (!token || typeof token !== "string" || token.length > 8192) throw Error("missing-jwt");
  const team = env.ACCESS_TEAM_DOMAIN;
  if (typeof team !== "string" ||
      !/^https:\/\/[a-zA-Z0-9-]+\.cloudflareaccess\.com$/.test(team) ||
      typeof env.ACCESS_AUD !== "string" || env.ACCESS_AUD.length < 8 ||
      typeof env.CEO_EMAIL !== "string" || !env.CEO_EMAIL.includes("@")) {
    throw Error("access-not-configured");
  }
  const pieces = token.split(".");
  if (pieces.length !== 3) throw Error("malformed-jwt");
  const header = parseJwtSection(pieces[0]);
  const claims = parseJwtSection(pieces[1]);
  if (!header || header.alg !== "RS256" || typeof header.kid !== "string" || header.kid.length > 200) {
    throw Error("unsupported-jwt-algorithm");
  }
  const now = Math.floor(nowMs / 1000);
  const audiences = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
  if (claims.iss !== team || !audiences.includes(env.ACCESS_AUD) ||
      typeof claims.exp !== "number" || now >= claims.exp ||
      typeof claims.nbf === "number" && now < claims.nbf ||
      typeof claims.iat === "number" && claims.iat > now + 30 ||
      typeof claims.email !== "string" ||
      claims.email.toLowerCase() !== env.CEO_EMAIL.toLowerCase()) {
    throw Error("access-claims-not-authorized");
  }
  const certsResp = await fetcher(team + "/cdn-cgi/access/certs", {
    method: "GET", headers: { "Accept": "application/json" },
  });
  if (!certsResp.ok) throw Error("access-jwks-unavailable");
  const certs = await certsResp.json();
  const keys = Array.isArray(certs.keys) ? certs.keys : [];
  const keyData = keys.find(k => k && k.kid === header.kid && k.kty === "RSA" && k.use !== "enc");
  if (!keyData) throw Error("access-signing-key-unavailable");
  const publicKey = await crypto.subtle.importKey(
    "jwk", keyData, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
  const ok = await crypto.subtle.verify(
    "RSASSA-PKCS1-v1_5", publicKey,
    fromBase64url(pieces[2]), new TextEncoder().encode(pieces[0] + "." + pieces[1]));
  if (!ok) throw Error("invalid-access-signature");
  return { email: claims.email.toLowerCase(), sub: claims.sub || "" };
}

function validatedZoomJoinUrl(env) {
  // Optional owner-supplied Zoom link. No Zoom OAuth, meetings API, or bot calls.
  const value = env && env.ZOOM_JOIN_URL;
  if (typeof value !== "string" || value.length > 1000) return null;
  try {
    const url = new URL(value);
    const host = url.hostname.toLowerCase();
    if (url.protocol !== "https:" ||
        !(host === "zoom.us" || host.endsWith(".zoom.us")) ||
        url.username || url.password || url.port || url.hash ||
        !new RegExp("^/j/[0-9]{9,11}/?$").test(url.pathname)) return null;
    // Only the usual Zoom invite password token is preserved, if present.
    if ([...url.searchParams.keys()].some(key => key !== "pwd") ||
        url.searchParams.getAll("pwd").length > 1) return null;
    return url.href;
  } catch {
    return null;
  }
}

function configured(env) {
  return env && typeof env.ELEVENLABS_API_KEY === "string" &&
    env.ELEVENLABS_API_KEY.length > 8 &&
    env.VOICE_LIMITER && typeof env.VOICE_LIMITER.limit === "function" &&
    env.ASSETS && typeof env.ASSETS.fetch === "function";
}

function readinessReport(env) {
  // Only served after cryptographic CEO Access identity verification.
  // Never include secret values, agent identifiers or provider credentials.
  const agentRoles = Object.keys(ROLES);
  const configuredEmployees = agentRoles.filter(role =>
    typeof env[ROLES[role]] === "string" &&
    /^agent_[a-z0-9]{15,60}$/i.test(env[ROLES[role]])).length;
  const checks = {
    signing_key_present: typeof env.ELEVENLABS_API_KEY === "string" &&
      env.ELEVENLABS_API_KEY.length > 8,
    voice_rate_limiter_bound: !!env.VOICE_LIMITER &&
      typeof env.VOICE_LIMITER.limit === "function",
    private_assets_bound: !!env.ASSETS && typeof env.ASSETS.fetch === "function",
    all_six_employee_ids_present: configuredEmployees === agentRoles.length,
  };
  return {
    status: Object.values(checks).every(Boolean)
      ? "CONFIGURATION_READY_FOR_SHORT_VOICE_TEST"
      : "CONFIGURATION_INCOMPLETE",
    configured_employees: configuredEmployees,
    required_employees: agentRoles.length,
    checks,
    live_voice_call_tested: false,
    certified_bets: 0,
    external_provider_queried: false,
  };
}

async function signedSession(request, env, identity, fetcher) {
  if (request.method !== "POST") return json({ error: "method_not_allowed" }, 405);
  const origin = request.headers.get("Origin");
  if (origin !== new URL(request.url).origin ||
      !String(request.headers.get("Content-Type")).startsWith("application/json")) {
    return json({ error: "same_origin_post_required" }, 403);
  }
  const length = Number(request.headers.get("content-length") || "0");
  if (length > 1024) return json({ error: "body_too_large" }, 413);
  let body;
  try {
    body = JSON.parse(await request.text());
  } catch {
    return json({ error: "invalid_json" }, 400);
  }
  if (!body || typeof body !== "object" ||
      Object.keys(body).length !== 1 || typeof body.role !== "string" ||
      !Object.hasOwn(ROLES, body.role)) {
    return json({ error: "unsupported_employee" }, 400);
  }
  const agentId = env[ROLES[body.role]];
  if (typeof agentId !== "string" || !/^agent_[a-z0-9]{15,60}$/i.test(agentId)) {
    return json({ error: "voice_employee_not_configured" }, 503);
  }
  const limit = await env.VOICE_LIMITER.limit({ key: identity.email });
  if (!limit || limit.success !== true) return json({ error: "voice_rate_limit" }, 429);

  const target = "https://api.elevenlabs.io/v1/convai/conversation/get-signed-url?agent_id=" +
    encodeURIComponent(agentId);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 9000);
  let response;
  try {
    response = await fetcher(target, {
      method: "GET", headers: { "xi-api-key": env.ELEVENLABS_API_KEY,
        "Accept": "application/json" }, signal: controller.signal,
    });
  } catch {
    return json({ error: "voice_provider_unreachable" }, 502);
  } finally {
    clearTimeout(timer);
  }
  if (!response.ok) return json({ error: "voice_provider_unavailable" }, 502);
  let signed;
  try { signed = (await response.json()).signed_url; }
  catch { return json({ error: "invalid_provider_response" }, 502); }
  try {
    const url = new URL(signed);
    if (url.protocol !== "wss:" || url.hostname !== "api.elevenlabs.io" ||
        !url.pathname.startsWith("/v1/convai/conversation")) throw Error();
  } catch {
    return json({ error: "invalid_provider_response" }, 502);
  }
  // Ephemeral signed URL: never persist, log, cache, or include it in links.
  return json({ signedUrl: signed, role: body.role });
}

function anamReadiness(env) {
  // CEO-only, no provider or billable call. Never return secrets.
  return { ready: typeof env.ANAM_API_KEY === "string" &&
    env.ANAM_API_KEY.length > 8 &&
    !!env.VOICE_LIMITER && typeof env.VOICE_LIMITER.limit === "function",
    configured_personas: Object.keys(ANAM_PERSONAS).length,
    live_session_started: false, provider_called: false };
}

async function anamSessionToken(request,env,identity,fetcher) {
  if(request.method!=="POST")return json({error:"method_not_allowed"},405);
  if(request.headers.get("Origin")!==new URL(request.url).origin ||
    !String(request.headers.get("Content-Type")).startsWith("application/json"))
    return json({error:"same_origin_post_required"},403);
  if(typeof env.ANAM_API_KEY!=="string" || env.ANAM_API_KEY.length<=8 ||
    !env.VOICE_LIMITER || typeof env.VOICE_LIMITER.limit!=="function")
    return json({error:"anam_not_configured"},503);
  if(Number(request.headers.get("content-length")||"0")>160)
    return json({error:"body_too_large"},413);
  let body;
  try{const raw=await request.text();if(raw.length>160)return json({error:"body_too_large"},413);body=JSON.parse(raw)}
  catch{return json({error:"invalid_json"},400)}
  if(!body || Array.isArray(body) || typeof body!=="object" ||
    Object.keys(body).length!==1 || typeof body.role!=="string" ||
    !Object.hasOwn(ANAM_PERSONAS,body.role))
    return json({error:"unsupported_anam_persona"},400);
  const limit=await env.VOICE_LIMITER.limit({key:"anam:"+identity.email});
  if(!limit || limit.success!==true)return json({error:"anam_session_rate_limit"},429);
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),9000);
  let response;
  try{
    response=await fetcher("https://api.anam.ai/v1/auth/session-token",{
      method:"POST",
      headers:{"Authorization":"Bearer "+env.ANAM_API_KEY,
        "Content-Type":"application/json","Accept":"application/json"},
      body:JSON.stringify({personaConfig:{personaId:ANAM_PERSONAS[body.role]}}),
      signal:controller.signal,
    });
  }catch{return json({error:"anam_provider_unreachable"},502)}
  finally{clearTimeout(timer)}
  if(!response.ok)return json({error:"anam_provider_unavailable"},502);
  let token;
  try{token=(await response.json()).sessionToken}
  catch{return json({error:"invalid_anam_response"},502)}
  if(typeof token!=="string" || token.length<10 || token.length>16384)
    return json({error:"invalid_anam_response"},502);
  return json({sessionToken:token,role:body.role});
}

async function anamAvatarImage(request, fetcher, role) {
  if(request.method!=="GET")return json({error:"method_not_allowed"},405);
  if(!Object.hasOwn(ANAM_AVATARS,role))
    return json({error:"unsupported_anam_avatar"},404);
  // Image bytes stay behind validated CEO Cloudflare Access; no public image
  // CDN URLs or user portraits are committed to the public GitHub repository.
  // The Anam Lab image route must be accessible without browser session cookies.
  const target="https://lab.anam.ai/api/avatars/"+ANAM_AVATARS[role]+"/image/portrait";
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),7000);
  let response;
  try{response=await fetcher(target,{
    method:"GET",redirect:"follow",signal:controller.signal,
    headers:{"Accept":"image/avif,image/webp,image/png,image/jpeg"},
  })}
  catch{return json({error:"avatar_source_unavailable"},502)}
  finally{clearTimeout(timer)}
  if(!response.ok)return json({error:"avatar_source_unavailable"},502);
  const type=String(response.headers.get("Content-Type")||"").split(";")[0].trim().toLowerCase();
  if(!["image/webp","image/png","image/jpeg","image/avif"].includes(type))
    return json({error:"avatar_unexpected_media"},502);
  const length=Number(response.headers.get("Content-Length")||"0");
  if(length>4000000)return json({error:"avatar_too_large"},502);
  let bytes;
  try{bytes=await response.arrayBuffer()}
  catch{return json({error:"avatar_source_unavailable"},502)}
  if(bytes.byteLength>4000000 || bytes.byteLength<1)
    return json({error:"avatar_invalid_size"},502);
  return new Response(bytes,{status:200,headers:{
    ...NO_CACHE,"Content-Type":type,"Content-Length":String(bytes.byteLength),
  }});
}

export async function handleRequest(request, env, fetcher = fetch) {
  // Non-sensitive, no-provider-call external probe. Cloudflare Access may still
  // intercept this route before the request reaches the Worker.
  const probePath = new URL(request.url).pathname;
  if (probePath === "/healthz") {
    if (request.method !== "GET" && request.method !== "HEAD")
      return json({ error: "method_not_allowed" }, 405);
    const response = json({ status: "up", component: "private_voice_gateway",
      check: "worker_reachable", authentication: "not_tested" });
    return request.method === "HEAD"
      ? new Response(null, { status: response.status, headers: response.headers })
      : response;
  }
  let identity;
  try {
    identity = await verifyAccessJwt(
      request.headers.get("Cf-Access-Jwt-Assertion"), env, fetcher);
  } catch (error) {
    // Emit only a fixed diagnostic category. Never log JWTs, emails, claims,
    // headers, request URLs, or credential values.
    const safeReasons = new Set([
      "missing-jwt", "access-not-configured", "malformed-jwt",
      "bad-jwt-segment", "unsupported-jwt-algorithm",
      "access-claims-not-authorized", "access-jwks-unavailable",
      "access-signing-key-unavailable", "invalid-access-signature",
    ]);
    const reason = error instanceof Error && safeReasons.has(error.message)
      ? error.message : "jwt-verification-unexpected-failure";
    console.warn("private_boardroom_access_denied", { reason });
    return json({ error: "authenticated_ceo_access_required" }, 401);
  }
  const path = new URL(request.url).pathname;
  if (path.startsWith("/api/anam/avatar/")) return anamAvatarImage(request,fetcher,path.slice("/api/anam/avatar/".length));
  if (path === "/api/anam/readiness") {
    if(request.method!=="GET")return json({error:"method_not_allowed"},405);
    return json(anamReadiness(env));
  }
  if (path === "/api/anam/session-token") return anamSessionToken(request,env,identity,fetcher);
  if (path === "/api/readiness") {
    if (request.method !== "GET") return json({ error: "method_not_allowed" }, 405);
    return json(readinessReport(env));
  }
  if (path === "/api/integrations") {
    if (request.method !== "GET") return json({ error: "method_not_allowed" }, 405);
    const zoomUrl = validatedZoomJoinUrl(env);
    return json({
      zoom: { configured: Boolean(zoomUrl), join_url: zoomUrl },
      whatsapp: { share_only: true, automated_messages: false },
      live_meeting_started: false,
      provider_api_called: false,
    });
  }
  if (path === "/api/zoom-video-readiness") {
    if (request.method !== "GET") return json({error:"method_not_allowed"},405);
    return json(zoomVideoReadiness(env));
  }
  if (path === "/api/zoom-video-token") {
    if (request.method !== "POST") return json({error:"method_not_allowed"},405);
    if (request.headers.get("Origin") !== new URL(request.url).origin ||
        !String(request.headers.get("Content-Type")).startsWith("application/json"))
      return json({error:"same_origin_post_required"},403);
    if (Number(request.headers.get("content-length")||"0") > 80)
      return json({error:"body_too_large"},413);
    let body;
    try {
      const raw=await request.text();
      if (raw.length > 80) return json({error:"body_too_large"},413);
      body=JSON.parse(raw);
    } catch {return json({error:"invalid_json"},400)}
    if (!body || typeof body!=="object" || Array.isArray(body) ||
        Object.keys(body).length!==1 || body.confirm!=="join")
      return json({error:"explicit_meeting_join_required"},400);
    if (!Object.values(zoomVideoChecks(env)).every(Boolean))
      return json({error:"zoom_video_sdk_not_configured"},503);
    const result=await env.VOICE_LIMITER.limit({key:"zoom:"+identity.email});
    if (!result || result.success!==true) return json({error:"zoom_session_rate_limit"},429);
    try {return json(await signZoomVideoToken(env))}
    catch {return json({error:"zoom_token_signing_unavailable"},503)}
  }
  if (path === "/api/session") {
    if (!configured(env)) return json({ error: "private_voice_gateway_not_configured" }, 503);
    return signedSession(request, env, identity, fetcher);
  }
  if (path.startsWith("/api/")) return json({ error: "not_found" }, 404);
  if (request.method !== "GET" && request.method !== "HEAD") {
    return json({ error: "method_not_allowed" }, 405);
  }
  // Permit authenticated CEO access to the boardroom and setup UI even if
  // ElevenLabs secrets have not been entered. Session signing stays fail-closed.
  if (!env.ASSETS || typeof env.ASSETS.fetch !== "function")
    return json({ error: "private_assets_not_configured" }, 503);
  const result = await env.ASSETS.fetch(request);
  const headers = new Headers(result.headers);
  for (const [k, v] of Object.entries(NO_CACHE)) {
    if (k !== "Content-Security-Policy") headers.set(k, v);
  }
  const isZoomVideo = path === "/zoom-video.html" ||
    path === "/zoom-video.js" || path === "/zoom-video.css";
  const isAnamRoom = path === "/anam-room.html" || path === "/anam-room.js" || path === "/anam-room.css" ||
    path === "/podcast-bella.html" || path === "/podcast-bella.js" || path === "/podcast-bella.css";
  headers.set("Content-Security-Policy",isAnamRoom
    ? "default-src 'self'; img-src 'self' data:; " +
      "connect-src 'self' https://api.anam.ai wss://connect.anam.ai wss://connect-us.anam.ai wss://connect-eu.anam.ai; " +
      "script-src 'self'; style-src 'self'; media-src 'self' blob:; " +
      "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    : isZoomVideo
    ? "default-src 'self'; img-src 'self' https://frederickwalker66-cmyk.github.io data:; " +
      "connect-src 'self' https://source.zoom.us https://*.zoom.us wss://*.zoom.us https://*.zoom.com wss://*.zoom.com; " +
      "script-src 'self' https://source.zoom.us 'wasm-unsafe-eval'; " +
      "style-src 'self' 'unsafe-inline'; worker-src 'self' blob:; " +
      "media-src 'self' blob:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    : "default-src 'self'; img-src 'self' https://frederickwalker66-cmyk.github.io; " +
      "connect-src 'self' https://api.elevenlabs.io wss://api.elevenlabs.io; " +
      "script-src 'self'; style-src 'self'; media-src 'self' blob:; " +
      "frame-ancestors 'none'; base-uri 'none'; form-action 'self'");
  return new Response(result.body, { status: result.status, headers });
}

export default { fetch(request, env) { return handleRequest(request, env); } };
