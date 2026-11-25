import {test} from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {handleAudience} from "../src/worker.js";
const req=(path,method="GET",body,headers={})=>new Request("https://questions.example.workers.dev"+path,{method,headers:{Origin:"https://questions.example.workers.dev","Content-Type":"application/json",...headers},...(body?{body:JSON.stringify(body)}:{})});
test("submission is fail-closed when D1, Turnstile or limiter not configured",async()=>{
 const r=await handleAudience(req("/api/questions","POST",{name:"A",question:"What should Bella think about this?",token:"fake-token"}),{});
 assert.equal(r.status,503);
});
test("cannot list pending questions without private authorization",async()=>{
 const db={prepare:()=>({bind:()=>({all:async()=>({results:[]})})})};
 const env={QUESTIONS_DB:db,PODCAST_QUESTIONS_ADMIN_KEY:"a".repeat(48)};
 const r=await handleAudience(req("/api/admin/questions","GET"),env);
 assert.equal(r.status,401);
});
test("valid viewer question requires successful server-side Turnstile verification",async()=>{
 let verified=0,stored=0;
 const db={prepare:()=>({bind:()=>({run:async()=>{stored++;return{success:true}}})})};
 const env={QUESTIONS_DB:db,TURNSTILE_SECRET_KEY:"secret",AUDIENCE_LIMITER:{limit:async()=>({success:true})}};
 const body={name:"Listener",question:"Freddy, what is your favorite topic today?",token:"abcde12345fghij"};
 const fail=await handleAudience(req("/api/questions","POST",body),env,async()=>{verified++;return Response.json({success:false})});
 assert.equal(fail.status,403);assert.equal(stored,0);
 const yes=await handleAudience(req("/api/questions","POST",body),env,async()=>{verified++;return Response.json({success:true})});
 assert.equal(yes.status,202);assert.equal(stored,1);assert.equal(verified,2);
});
test("private producer assets and API routes retain authentication",()=>{
 const worker=readFileSync(new URL("../../voice_gateway/src/worker.js",import.meta.url),"utf8");
 assert.ok(worker.indexOf("identity = await verifyAccessJwt(")<worker.indexOf('path === "/api/podcast/questions-config"'));
 assert.ok(worker.includes("PODCAST_QUESTIONS_ADMIN_KEY"));
 const h=readFileSync(new URL("../../voice_gateway/web/podcast-producer.html",import.meta.url),"utf8");
 assert.match(h,/9:16/);assert.match(h,/Bella/);assert.match(h,/moderate|Moderated|moderation|pending|review/i);
 assert.doesNotMatch(h,/stream_key|sk_live_/);
});
