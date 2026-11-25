import {test} from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
const read=name=>readFileSync(new URL("../web/"+name,import.meta.url),"utf8");
test("two-host studio has Bella and Freddy but no six-person panel",()=>{
 const html=read("podcast-bella.html");
 assert.match(html,/Bella/);
 assert.match(html,/Freddy/);
 assert.match(html,/AI co-host/);
 assert.doesNotMatch(html,/Command Center Manager|David|Cassidy|Roger|Sarah|Adam Stone/);
});
test("Anam session requests only saved Bella Studio role behind protected Worker",()=>{
 const js=read("podcast-bella.js");
 assert.match(js,/role:"bella-studio"/);
 assert.match(js,/\/api\/anam\/session-token/);
 assert.match(js,/createClient/);
 assert.match(js,/streamToVideoElement/);
 assert.ok(!js.includes("xi-api-key") && !js.includes("Authorization: Bearer") && !js.includes("localStorage.setItem(\"sessionToken\""));
});
test("recording requires explicit browser screen share and download",()=>{
 const js=read("podcast-bella.js");
 assert.match(js,/getDisplayMedia/);
 assert.match(js,/MediaRecorder/);
 assert.match(js,/createObjectURL/);
 assert.doesNotMatch(js,/api\/upload|autopost|publish/);
});
test("worker keeps Bella page under verified Access and Anam CSP",()=>{
 const src=readFileSync(new URL("../src/worker.js",import.meta.url),"utf8");
 const auth=src.indexOf("identity = await verifyAccessJwt(");
 const path=src.indexOf('path === "/podcast-bella.html"');
 assert.ok(auth>=0 && path>auth);
 assert.match(src,/connect-us\.anam\.ai/);
});
test("build bundles Bella SDK and packages page",()=>{
 const build=readFileSync(new URL("../build.mjs",import.meta.url),"utf8");
 assert.match(build,/podcast-bella\.js/);
 assert.match(build,/podcast-bella\.html/);
 assert.match(build,/podcast-bella\.css/);
});