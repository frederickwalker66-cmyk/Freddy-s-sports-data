import {test} from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
const read = name => readFileSync(new URL("../web/"+name,import.meta.url),"utf8");
test("podcast page is host-only, without employee avatars or auto-publishing",()=>{
 const h=read("podcast.html");
 assert.match(h,/YOU TALKING/);
 assert.match(h,/Record audio/);
 assert.match(h,/Audience questions/);
 assert.match(h,/Invite a guest/);
 for(const label of ["Bella","David","Cassidy","Roger","Sarah","Adam Stone","agent_","api key"])assert.ok(!h.includes(label),"Unexpected employee or credential: "+label);
});
test("podcast recording is click-initiated and never automatically uploads",()=>{
 const s=read("podcast.js");
 assert.match(s,/getUserMedia/);
 assert.match(s,/MediaRecorder/);
 assert.match(s,/URL.createObjectURL/);
 assert.match(s,/localStorage/);
 assert.ok(!s.includes("/api/upload"));
 assert.ok(!s.includes("fetch(\"https://"));
});
test("Cloudflare build includes protected podcast assets",()=>{
 const b=readFileSync(new URL("../build.mjs",import.meta.url),"utf8");
 for(const f of ["podcast.html","podcast.css","podcast.js"])assert.ok(b.includes(f));
});