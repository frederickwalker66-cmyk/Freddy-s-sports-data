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
  const missing=await handleRequest(request(),env({ELEVENLABS_API_KEY:undefined}),mockFetch);
  assert.equal(missing.status,503);
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
