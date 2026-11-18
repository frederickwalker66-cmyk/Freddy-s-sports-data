import {test, before} from "node:test";
import assert from "node:assert/strict";
import {webcrypto} from "node:crypto";
import {handleRequest} from "../src/worker.js";

globalThis.crypto ??= webcrypto;
const enc = obj => Buffer.from(JSON.stringify(obj)).toString("base64url");
let keyPair, jwk;
const origin="https://freddys-v9-private-voice.workers.dev";
const team="https://example-team.cloudflareaccess.com";

before(async()=>{
  keyPair=await crypto.subtle.generateKey({
    name:"RSASSA-PKCS1-v1_5",modulusLength:2048,
    publicExponent:new Uint8Array([1,0,1]),hash:"SHA-256",
  },true,["sign","verify"]);
  jwk=await crypto.subtle.exportKey("jwk",keyPair.publicKey);
  jwk.kid="test-key";
  jwk.use="sig";
  jwk.alg="RS256";
});

function env(overrides={}) {
  return {
    ACCESS_TEAM_DOMAIN:team,ACCESS_AUD:"test-v9-access-application",
    CEO_EMAIL:"ceo@example.com",
    ELEVENLABS_API_KEY:"test-elevenlabs-private-key",
    ELEVENLABS_BELLA_AGENT_ID:"agent_bella1234567890123456789",
    ELEVENLABS_DAVID_AGENT_ID:"agent_david1234567890123456789",
    VOICE_LIMITER:{async limit(){return{success:true}}},
    ASSETS:{async fetch(){return new Response("private static app",{status:200})}},
    ...overrides,
  };
}
async function jwt(claims={},header={}) {
  const now=Math.floor(Date.now()/1000);
  const rawHeader=enc({alg:"RS256",kid:"test-key",typ:"JWT",...header});
  const rawClaims=enc({
    iss:team,aud:["test-v9-access-application"],email:"ceo@example.com",
    iat:now-10,nbf:now-10,exp:now+120,sub:"ceo-123",...claims,
  });
  const bytes=new TextEncoder().encode(rawHeader+"."+rawClaims);
  const sig=await crypto.subtle.sign("RSASSA-PKCS1-v1_5",keyPair.privateKey,bytes);
  return rawHeader+"."+rawClaims+"."+Buffer.from(sig).toString("base64url");
}
const mockFetch=async(url)=>{
  if(url===team+"/cdn-cgi/access/certs")return Response.json({keys:[jwk]});
  if(url.startsWith("https://api.elevenlabs.io/v1/convai/conversation/get-signed-url?"))
    return Response.json({signed_url:"wss://api.elevenlabs.io/v1/convai/conversation?conversation_signature=testtoken"});
  throw Error("unexpected outbound request");
};
function request(path="/",method="GET",token=null,role="bella",extra={}) {
  const headers=new Headers(extra);
  if(token)headers.set("Cf-Access-Jwt-Assertion",token);
  if(method==="POST"){headers.set("Origin",origin);headers.set("Content-Type","application/json")}
  return new Request(origin+path,{
    method,headers,body:method==="POST"?JSON.stringify({role}):undefined,
  });
}

test("deny missing secrets, credentials and configuration by default",async()=>{
  // CEO sees the private setup/meeting entry screen before voice secrets exist.
  // Only paid ElevenLabs signing endpoint stays blocked.
  const missing=await handleRequest(request("/", "GET", await jwt()),env({ELEVENLABS_API_KEY:undefined}),mockFetch);
  assert.equal(missing.status,200);
  const deniedSigning=await handleRequest(
    request("/api/session","POST",await jwt()),env({ELEVENLABS_API_KEY:undefined}),mockFetch);
  assert.equal(deniedSigning.status,503);
  const noAuth=await handleRequest(request(),env(),mockFetch);
  assert.equal(noAuth.status,401);
  assert.equal(noAuth.headers.get("Cache-Control").includes("no-store"),true);
});

test("deny forged, expired, wrong-app or wrong-user tokens",async()=>{
  for(const token of [
    await jwt({email:"stranger@example.com"}),
    await jwt({aud:["some-other-app"]}),
    await jwt({iss:"https://evil.example.com"}),
    await jwt({exp:Math.floor(Date.now()/1000)-1}),
    await jwt({}, {alg:"none"}),
    "this.is.not.jwt",
  ]){
    const response=await handleRequest(request("/", "GET", token),env(),mockFetch);
    assert.equal(response.status,401);
  }
});

test("authorized CEO may read static app, not leak API key",async()=>{
  const response=await handleRequest(request("/", "GET", await jwt()),env(),mockFetch);
  assert.equal(response.status,200);
  assert.equal(await response.text(),"private static app");
  assert.ok(response.headers.get("Content-Security-Policy").includes("frame-ancestors 'none'"));
  assert.ok(response.headers.get("Cache-Control").includes("no-store"));
});

test("signed voice session requires owner, valid role and same-origin POST",async()=>{
  const token=await jwt();
  const ok=await handleRequest(request("/api/session","POST",token,"bella"),env(),mockFetch);
  assert.equal(ok.status,200);
  const body=await ok.json();
  assert.equal(body.role,"bella");
  assert.ok(body.signedUrl.startsWith("wss://api.elevenlabs.io/"));
  assert.equal(JSON.stringify(body).includes("private-key"),false);
  const badRole=await handleRequest(request("/api/session","POST",token,"arbitrary"),env(),mockFetch);
  assert.equal(badRole.status,400);
  const badOrigin=request("/api/session","POST",token,"bella",{"Origin":"https://evil.example.com"});
  badOrigin.headers.set("Origin","https://evil.example.com");
  const originDenied=await handleRequest(badOrigin,env(),mockFetch);
  assert.equal(originDenied.status,403);
  const getMethod=await handleRequest(request("/api/session","GET",token),env(),mockFetch);
  assert.equal(getMethod.status,405);
});

test("provider failures and rate limits fail closed without call session",async()=>{
  const token=await jwt();
  const limited=await handleRequest(
    request("/api/session","POST",token),
    env({VOICE_LIMITER:{async limit(){return{success:false}}}}),mockFetch);
  assert.equal(limited.status,429);
  const providerError=await handleRequest(request("/api/session","POST",token),env(),
    async(url)=>url.includes("cloudflareaccess.com")
      ?Response.json({keys:[jwk]}):new Response("error",{status:503}));
  assert.equal(providerError.status,502);
  const missingAgent=await handleRequest(request("/api/session","POST",token,"roger"),env(),mockFetch);
  assert.equal(missingAgent.status,503);
});

test("API has no public fallback or hidden wager routes",async()=>{
  const token=await jwt();
  const response=await handleRequest(request("/api/bet","POST",token),env(),mockFetch);
  assert.equal(response.status,404);
  const outsider=await handleRequest(request("/api/session","POST"),env(),mockFetch);
  assert.equal(outsider.status,401);
});

test("private readiness is inaccessible to outsiders and never calls ElevenLabs",async()=>{
  const outsider=await handleRequest(request("/api/readiness","GET"),env(),mockFetch);
  assert.equal(outsider.status,401);
  let providerCalls=0;
  const onlyCloudflare=async url=>{
    if(url===team+"/cdn-cgi/access/certs") return Response.json({keys:[jwk]});
    providerCalls+=1;
    throw Error("unexpected downstream provider call");
  };
  const result=await handleRequest(
    request("/api/readiness","GET",await jwt()),
    env({ELEVENLABS_API_KEY:undefined}),onlyCloudflare);
  assert.equal(result.status,200);
  const report=await result.json();
  assert.equal(report.status,"CONFIGURATION_INCOMPLETE");
  assert.equal(report.configured_employees,2);
  assert.equal(report.required_employees,6);
  assert.equal(report.checks.signing_key_present,false);
  assert.equal(report.checks.all_six_employee_ids_present,false);
  assert.equal(report.live_voice_call_tested,false);
  assert.equal(report.certified_bets,0);
  assert.equal(report.external_provider_queried,false);
  assert.equal(providerCalls,0);
  assert.equal(JSON.stringify(report).includes("test-elevenlabs"),false);
  assert.equal(JSON.stringify(report).includes("agent_bella"),false);
  assert.equal(result.headers.get("Cache-Control").includes("no-store"),true);
});

test("readiness becomes ready when all six agent bindings exist without a voice call",async()=>{
  const token=await jwt();
  const complete=env({
    ELEVENLABS_CASSIDY_AGENT_ID:"agent_cassidy12345678901234567",
    ELEVENLABS_ROGER_AGENT_ID:"agent_roger123456789012345678",
    ELEVENLABS_SARAH_AGENT_ID:"agent_sarah123456789012345678",
    ELEVENLABS_ADAM_AGENT_ID:"agent_adam1234567890123456789",
  });
  const result=await handleRequest(request("/api/readiness","GET",token),complete,mockFetch);
  assert.equal(result.status,200);
  const report=await result.json();
  assert.equal(report.status,"CONFIGURATION_READY_FOR_SHORT_VOICE_TEST");
  assert.equal(report.configured_employees,6);
  assert.equal(report.live_voice_call_tested,false);
  const blocked=await handleRequest(request("/api/readiness","POST",token),complete,mockFetch);
  assert.equal(blocked.status,405);
  const rejected=await handleRequest(request("/api/readiness","GET",await jwt({email:"other@example.com"})),complete,mockFetch);
  assert.equal(rejected.status,401);
});

test("Zoom and WhatsApp integrations are owner-only and do not contact providers",async()=>{
  const outsider=await handleRequest(request("/api/integrations","GET"),env(),mockFetch);
  assert.equal(outsider.status,401);
  let outsideCalls=0;
  const noProviders=async url=>{
    if(url===team+"/cdn-cgi/access/certs")return Response.json({keys:[jwk]});
    outsideCalls++;
    throw Error("No Zoom, WhatsApp, or ElevenLabs requests permitted");
  };
  const token=await jwt();
  const missing=await handleRequest(request("/api/integrations","GET",token),
    env({ELEVENLABS_API_KEY:undefined}),noProviders);
  assert.equal(missing.status,200);
  const body=await missing.json();
  assert.equal(body.zoom.configured,false);
  assert.equal(body.zoom.join_url,null);
  assert.equal(body.whatsapp.share_only,true);
  assert.equal(body.whatsapp.automated_messages,false);
  assert.equal(body.live_meeting_started,false);
  assert.equal(body.provider_api_called,false);
  assert.equal(outsideCalls,0);
  assert.equal(JSON.stringify(body).includes("private-key"),false);
  assert.equal(JSON.stringify(body).includes("agent_bella"),false);
  assert.equal(missing.headers.get("Cache-Control").includes("no-store"),true);
  const posted=await handleRequest(request("/api/integrations","POST",token),env(),noProviders);
  assert.equal(posted.status,405);
  const wrongUser=await handleRequest(
    request("/api/integrations","GET",await jwt({email:"intruder@example.com"})),env(),noProviders);
  assert.equal(wrongUser.status,401);
  assert.equal(outsideCalls,0);
});

test("Only strict Zoom meeting join URLs are returned to authenticated owner",async()=>{
  const token=await jwt();
  const good=["https://zoom.us/j/12345678901",
    "https://us02web.zoom.us/j/12345678901?pwd=example-token"];
  for(const joinUrl of good){
    const result=await handleRequest(request("/api/integrations","GET",token),
      env({ZOOM_JOIN_URL:joinUrl}),mockFetch);
    assert.equal(result.status,200);
    const body=await result.json();
    assert.equal(body.zoom.configured,true);
    assert.equal(body.zoom.join_url,joinUrl);
  }
  const bad=["https://zoom.us.evil.example/j/12345678901",
    "https://evil.example/j/12345678901",
    "http://zoom.us/j/12345678901",
    "https://zoom.us@evil.example/j/12345678901",
    "https://evil.example@zoom.us/j/12345678901",
    "https://zoom.us:8443/j/12345678901",
    "https://zoom.us/j/12345678",
    "https://zoom.us/admin",
    "https://zoom.us/j/12345678901?redirect=https://evil.example",
    "https://zoom.us/j/12345678901#secret"];
  for(const joinUrl of bad){
    const result=await handleRequest(request("/api/integrations","GET",token),
      env({ZOOM_JOIN_URL:joinUrl}),mockFetch);
    const body=await result.json();
    assert.equal(body.zoom.configured,false,joinUrl);
    assert.equal(body.zoom.join_url,null,joinUrl);
  }
});

test("Zoom Video SDK readiness is CEO-only, no-cost and reports no actual users",async()=>{
  const outsider=await handleRequest(request("/api/zoom-video-readiness"),env(),mockFetch);
  assert.equal(outsider.status,401);
  const owner=await jwt();
  const res=await handleRequest(request("/api/zoom-video-readiness","GET",owner),env(),mockFetch);
  assert.equal(res.status,200);
  const report=await res.json();
  assert.equal(report.status,"CONFIGURATION_INCOMPLETE");
  assert.equal(report.connected_zoom_video_users,0);
  assert.equal(report.connected_ai_video_bots,0);
  assert.equal(report.video_sdk_session_started,false);
  assert.equal(report.signed_token_created,false);
  assert.equal(report.zoom_sdk_provider_called,false);
  const notGet=await handleRequest(request("/api/zoom-video-readiness","POST",owner),env(),mockFetch);
  assert.equal(notGet.status,405);
  assert.equal(res.headers.get("Cache-Control").includes("no-store"),true);
});

test("Zoom signing needs same-origin explicit CEO join, secrets and rate limiter",async()=>{
  const owner=await jwt();
  const zoomConfig={
    ZOOM_VIDEO_SDK_KEY:"zoom-key-example-12345",
    ZOOM_VIDEO_SDK_SECRET:"zoom-server-secret-example-12345",
    ZOOM_VIDEO_SESSION_TOPIC:"Freddys V9 Private Room",
  };
  const post=(token,body={confirm:"join"},headers={})=>{
    const h=new Headers({"Origin":origin,"Content-Type":"application/json",...headers});
    if(token)h.set("Cf-Access-Jwt-Assertion",token);
    return new Request(origin+"/api/zoom-video-token",{
      method:"POST",headers:h,body:JSON.stringify(body),
    });
  };
  const noAccess=await handleRequest(post(null),env(zoomConfig),mockFetch);
  assert.equal(noAccess.status,401);
  const wrongUser=await handleRequest(post(await jwt({email:"stranger@example.com"})),
    env(zoomConfig),mockFetch);
  assert.equal(wrongUser.status,401);
  const missing=await handleRequest(post(owner),env(),mockFetch);
  assert.equal(missing.status,503);
  const noConsent=await handleRequest(post(owner,{confirm:"no"}),env(zoomConfig),mockFetch);
  assert.equal(noConsent.status,400);
  const arbitrary=await handleRequest(post(owner,{confirm:"join",role_type:1}),
    env(zoomConfig),mockFetch);
  assert.equal(arbitrary.status,400);
  const get=await handleRequest(request("/api/zoom-video-token","GET",owner),
    env(zoomConfig),mockFetch);
  assert.equal(get.status,405);
  const evil=post(owner,{confirm:"join"},{Origin:"https://evil.example"});
  const wrongOrigin=await handleRequest(evil,env(zoomConfig),mockFetch);
  assert.equal(wrongOrigin.status,403);
  const limited=await handleRequest(post(owner),
    env({...zoomConfig,VOICE_LIMITER:{async limit(){return{success:false}}}}),mockFetch);
  assert.equal(limited.status,429);
});

test("Authorized CEO gets short-lived valid HS256 Zoom token only on explicit join",async()=>{
  const owner=await jwt();
  const zoomConfig={
    ZOOM_VIDEO_SDK_KEY:"zoom-key-example-12345",
    ZOOM_VIDEO_SDK_SECRET:"zoom-server-secret-example-12345",
    ZOOM_VIDEO_SESSION_TOPIC:"Freddys V9 Private Room",
  };
  let callsToZoom=0;
  const onlyAccess=async url=>{
    if(url===team+"/cdn-cgi/access/certs")return Response.json({keys:[jwk]});
    callsToZoom++;throw Error("Zoom provider was unexpectedly called");
  };
  const req=new Request(origin+"/api/zoom-video-token",{
    method:"POST",
    headers:{"Origin":origin,"Content-Type":"application/json",
      "Cf-Access-Jwt-Assertion":owner},
    body:JSON.stringify({confirm:"join"}),
  });
  const res=await handleRequest(req,env(zoomConfig),onlyAccess);
  assert.equal(res.status,200);
  const result=await res.json();
  assert.equal(result.topic,zoomConfig.ZOOM_VIDEO_SESSION_TOPIC);
  assert.equal(typeof result.token,"string");
  const pieces=result.token.split(".");
  assert.equal(pieces.length,3);
  const decode=s=>JSON.parse(Buffer.from(s,"base64url").toString("utf8"));
  assert.equal(decode(pieces[0]).alg,"HS256");
  const claims=decode(pieces[1]);
  assert.equal(claims.app_key,zoomConfig.ZOOM_VIDEO_SDK_KEY);
  assert.equal(claims.role_type,1);
  assert.equal(claims.tpc,zoomConfig.ZOOM_VIDEO_SESSION_TOPIC);
  assert.equal(claims.version,1);
  assert.equal(claims.exp-claims.iat,3600);
  const key=await crypto.subtle.importKey("raw",
    new TextEncoder().encode(zoomConfig.ZOOM_VIDEO_SDK_SECRET),
    {name:"HMAC",hash:"SHA-256"},false,["verify"]);
  const good=await crypto.subtle.verify("HMAC",key,
    Buffer.from(pieces[2],"base64url"),
    new TextEncoder().encode(pieces[0]+"."+pieces[1]));
  assert.equal(good,true);
  assert.equal(JSON.stringify(result).includes(zoomConfig.ZOOM_VIDEO_SDK_SECRET),false);
  assert.equal(callsToZoom,0);
  assert.equal(res.headers.get("Cache-Control").includes("no-store"),true);
});
