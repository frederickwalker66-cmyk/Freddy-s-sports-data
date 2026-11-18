import {zoomVideoReadiness,signZoomVideoToken,zoomVideoChecks,ZOOM_STAFF_ROLES} from "./zoom-video-token.js";

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

export async function handleRequest(request, env, fetcher = fetch) {
  let identity;
  try {
    identity = await verifyAccessJwt(
      request.headers.get("Cf-Access-Jwt-Assertion"), env, fetcher);
  } catch {
    return json({ error: "authenticated_ceo_access_required" }, 401);
  }
  const path = new URL(request.url).pathname;
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
  if (path === "/api/zoom-staff-readiness") {
    if (request.method !== "GET") return json({error:"method_not_allowed"},405);
    const zoomChecks=zoomVideoChecks(env);
    return json({
      role_signing_configured:Object.values(zoomChecks).every(Boolean),
      role_count:ZOOM_STAFF_ROLES.length,
      roles:ZOOM_STAFF_ROLES,
      connected_live_bots:0,
      externally_hosted_bot_runtime_verified:false,
      elevenlabs_media_bridge_verified:false,
      whatsapp_native_group_video_supported:false,
      live_zoom_session_started:false,
      provider_contacted:false,
    });
  }
  if (path === "/api/zoom-staff-token") {
    if (request.method !== "POST") return json({error:"method_not_allowed"},405);
    if (request.headers.get("Origin")!==new URL(request.url).origin ||
        !String(request.headers.get("Content-Type")).startsWith("application/json"))
      return json({error:"same_origin_post_required"},403);
    if (Number(request.headers.get("content-length")||"0")>160)
      return json({error:"body_too_large"},413);
    let body;
    try {
      const raw=await request.text();
      if(raw.length>160) return json({error:"body_too_large"},413);
      body=JSON.parse(raw);
    } catch {return json({error:"invalid_json"},400)}
    if(!body || typeof body!=="object" || Array.isArray(body) ||
        Object.keys(body).length!==2 ||
        body.confirm!=="prepare" ||
        typeof body.role!=="string" || !ZOOM_STAFF_ROLES.includes(body.role))
      return json({error:"invalid_role_or_explicit_prepare_required"},400);
    if(!Object.values(zoomVideoChecks(env)).every(Boolean))
      return json({error:"zoom_video_sdk_not_configured"},503);
    const result=await env.VOICE_LIMITER.limit({key:"zoom-staff:"+identity.email});
    if(!result || result.success!==true)return json({error:"zoom_staff_token_rate_limit"},429);
    try {
      return json(await signZoomVideoToken(env,{participant:body.role}));
    } catch {
      return json({error:"zoom_staff_signing_unavailable"},503);
    }
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
  headers.set("Content-Security-Policy",isZoomVideo
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
