import {test,before} from "node:test";
import assert from "node:assert/strict";
import {webcrypto} from "node:crypto";
import {handleRequest} from "../src/worker.js";
import {createZoomVideoSdkJwt,VIDEO_SESSION_NAME} from "../src/zoom-video.js";

globalThis.crypto ??= webcrypto;
let keyPair,jwk;
const team="https://v9-test.cloudflareaccess.com";
const origin="https://freddys-v9-private-voice.frederickwalker66.workers.dev";
const ZOOM_KEY="test-zoom-videosdk-application-key";
const ZOOM_SECRET="test-zoom-videosdk-server-only-secret";
const encodeJSON=obj=>Buffer.from(JSON.stringify(obj)).toString("base64url");
before(async()=>{
  keyPair=await crypto.subtle.generateKey({
    name:"RSASSA-PKCS1-v1_5",modulusLength:2048,
    publicExponent:new Uint8Array([1,0,1]),hash:"SHA-256",
  },true,["sign","verify"]);
  jwk=await crypto.subtle.exportKey("jwk",keyPair.publicKey);
  jwk.kid="zoom-verify";jwk.use="sig";jwk.alg="RS256";
});
async function accessJwt(options={}){
  const now=Math.floor(Date.now()/1000);
  const header=encodeJSON({alg:"RS256",kid:"zoom-verify"});
  const claims=encodeJSON({iss:team,aud:"v9-zoom-access",
    email:"ceo@example.com",iat:now-10,nbf:now-10,exp:now+240,...options});
  const signingInput=header+"."+claims;
  const sig=await crypto.subtle.sign("RSASSA-PKCS1-v1_5",keyPair.privateKey,new TextEncoder().encode(signingInput));
  return signingInput+"."+Buffer.from(sig).toString("base64url");
}
function environment(overrides={}){
  return {ACCESS_TEAM_DOMAIN:team,ACCESS_AUD:"v9-zoom-access",CEO_EMAIL:"ceo@example.com",
    ZOOM_VIDEO_SDK_KEY:ZOOM_KEY,ZOOM_VIDEO_SDK_SECRET:ZOOM_SECRET,
    ASSETS:{async fetch(){return new Response("Zoom video private HTML page")}},
    VOICE_LIMITER:{async limit(){return {success:true}}},
    ...overrides};
}
function request(path,token,{method="GET",originHeader=origin,body}={}){
  const headers=new Headers();
  if(token)headers.set("Cf-Access-Jwt-Assertion",token);
  if(method==="POST"){
    headers.set("Origin",originHeader);
    headers.set("Content-Type","application/json");
  }
  return new Request(origin+path,{method,headers,body:method==="POST"?JSON.stringify(body??{approved:true}):undefined});
}
let downstreamRequests=0;
async function fetchJwksOnly(url){
  if(url===team+"/cdn-cgi/access/certs")return Response.json({keys:[jwk]});
  downstreamRequests++;
  throw Error("No provider calls allowed in offline verification");
}

test("private Zoom Video SDK readiness is owner-only and not a paid provider call",async()=>{
  downstreamRequests=0;
  const outsider=await handleRequest(request("/api/zoom-video-readiness"),environment(),fetchJwksOnly);
  assert.equal(outsider.status,401);
  const valid=await accessJwt();
  const response=await handleRequest(request("/api/zoom-video-readiness",valid),
    environment(),fetchJwksOnly);
  assert.equal(response.status,200);
  const body=await response.json();
  assert.equal(body.zoom_video_sdk_configured,true);
  assert.equal(body.live_video_session_started,false);
  assert.equal(body.video_bots_connected,0);
  assert.equal(body.remote_provider_contacted,false);
  assert.equal(response.headers.get("Cache-Control").includes("no-store"),true);
  assert.equal(JSON.stringify(body).includes(ZOOM_SECRET),false);
  assert.equal(JSON.stringify(body).includes(ZOOM_KEY),false);
  const unconfigured=await handleRequest(request("/api/zoom-video-readiness",valid),
    environment({ZOOM_VIDEO_SDK_SECRET:undefined}),fetchJwksOnly);
  assert.equal((await unconfigured.json()).zoom_video_sdk_configured,false);
  assert.equal(downstreamRequests,0);
});

test("Zoom token signing is HS256, CEO-only, ephemeral and Zoom-compatible",async()=>{
  downstreamRequests=0;
  const ceo=await accessJwt();
  const ok=await handleRequest(request("/api/zoom-video-token",ceo,{method:"POST"}),
    environment(),fetchJwksOnly);
  assert.equal(ok.status,200);
  const data=await ok.json();
  assert.equal(data.session_name,VIDEO_SESSION_NAME);
  assert.equal(data.zoom_provider_called,false);
  assert.equal(data.live_session_started,false);
  assert.equal(ok.headers.get("Cache-Control").includes("no-store"),true);
  assert.equal(JSON.stringify(data).includes(ZOOM_SECRET),false);
  const parts=data.token.split(".");
  assert.equal(parts.length,3);
  const header=JSON.parse(Buffer.from(parts[0],"base64url").toString());
  const claims=JSON.parse(Buffer.from(parts[1],"base64url").toString());
  assert.equal(header.alg,"HS256");
  assert.equal(claims.app_key,ZOOM_KEY);
  assert.equal(claims.role_type,1);
  assert.equal(claims.tpc,VIDEO_SESSION_NAME);
  assert.equal(claims.version,1);
  assert.equal(claims.user_key,"FreddyCEO");
  assert.ok(claims.exp-claims.iat >= 1800);
  assert.ok(claims.exp-claims.iat <= 172800);
  const key=await crypto.subtle.importKey("raw",new TextEncoder().encode(ZOOM_SECRET),
    {name:"HMAC",hash:"SHA-256"},false,["verify"]);
  const valid=await crypto.subtle.verify("HMAC",key,
    Buffer.from(parts[2],"base64url"),new TextEncoder().encode(parts[0]+"."+parts[1]));
  assert.equal(valid,true);
  assert.equal(downstreamRequests,0);
});

test("no auth, wrong CEO, denied consent, forged origin, bad method, missing secret and limiter fail closed",async()=>{
  const token=await accessJwt();
  const stranger=await accessJwt({email:"someoneelse@example.com"});
  const tests=[
    [request("/api/zoom-video-token",null,{method:"POST"}),environment(),401],
    [request("/api/zoom-video-token",stranger,{method:"POST"}),environment(),401],
    [request("/api/zoom-video-token",token),environment(),405],
    [request("/api/zoom-video-token",token,{method:"POST",body:{approved:false}}),environment(),403],
    [request("/api/zoom-video-token",token,{method:"POST",body:{approved:true,extra:1}}),environment(),403],
    [request("/api/zoom-video-token",token,{method:"POST",originHeader:"https://attacker.com"}),environment(),403],
    [request("/api/zoom-video-token",token,{method:"POST"}),environment({ZOOM_VIDEO_SDK_SECRET:undefined}),503],
    [request("/api/zoom-video-token",token,{method:"POST"}),environment({VOICE_LIMITER:undefined}),503],
    [request("/api/zoom-video-token",token,{method:"POST"}),environment({VOICE_LIMITER:{async limit(){return {success:false}}}}),429],
  ];
  for(const [req,env,code] of tests){
    const res=await handleRequest(req,env,fetchJwksOnly);
    assert.equal(res.status,code,await res.text());
  }
});

test("Zoom video static page works before ElevenLabs is configured; video-specific CSP only",async()=>{
  const token=await accessJwt();
  const video=await handleRequest(request("/video.html",token),
    environment({ELEVENLABS_API_KEY:undefined}),fetchJwksOnly);
  assert.equal(video.status,200);
  assert.ok(video.headers.get("Content-Security-Policy").includes("source.zoom.us"));
  assert.ok(video.headers.get("Content-Security-Policy").includes("frame-ancestors 'none'"));
  const voice=await handleRequest(request("/",token),
    environment({ELEVENLABS_API_KEY:undefined}),fetchJwksOnly);
  assert.equal(voice.status,200);
  assert.ok(!voice.headers.get("Content-Security-Policy").includes("unsafe-eval"));
});

test("Zoom credentials must never be included in browser source files",async()=>{
  const {readFile}=await import("node:fs/promises");
  for(const path of ["web/video.js","web/video.html","web/video.css","web/index.html"]){
    const data=await readFile(new URL("../"+path,import.meta.url),"utf8");
    assert.ok(!data.includes(ZOOM_KEY));
    assert.ok(!data.includes(ZOOM_SECRET));
  }
});
