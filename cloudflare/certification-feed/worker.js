// Secure evidence transport only. This worker NEVER creates or signs predictions.
// Deploy in a separate Cloudflare account/security boundary from the model producer.
// Bind CERTIFICATION_EVIDENCE KV; set FEED_READ_TOKEN and FEED_WRITE_TOKEN as secrets.
// Only an independent evidence custodian should hold FEED_WRITE_TOKEN.
const headers = {"content-type":"application/json","cache-control":"no-store","x-content-type-options":"nosniff"};
const reply = (status, obj) => new Response(JSON.stringify(obj), {status,headers});
const schema = "signed-certification-candidates-v1";
function bearer(req) {
  const h = req.headers.get("authorization") || "";
  return h.startsWith("Bearer ") ? h.slice(7) : "";
}
function constantTimeEqual(a,b) {
  if (typeof a !== "string" || typeof b !== "string" || !a || !b) return false;
  const x = new TextEncoder().encode(a), y = new TextEncoder().encode(b);
  let diff = x.length ^ y.length;
  for (let i=0;i<Math.max(x.length,y.length);i++) diff |= (x[i]||0) ^ (y[i]||0);
  return diff === 0;
}
export default {
 async fetch(request, env) {
  if (!env.CERTIFICATION_EVIDENCE || !env.FEED_READ_TOKEN || !env.FEED_WRITE_TOKEN ||
      env.FEED_READ_TOKEN.length < 32 || env.FEED_WRITE_TOKEN.length < 32 ||
      env.FEED_READ_TOKEN === env.FEED_WRITE_TOKEN) return reply(503,{error:"NOT_CONFIGURED"});
  const url = new URL(request.url);
  if (url.pathname !== "/v1/candidates") return reply(404,{error:"NOT_FOUND"});
  if (request.method === "GET") {
    if (!constantTimeEqual(bearer(request),env.FEED_READ_TOKEN)) return reply(401,{error:"UNAUTHORIZED"});
    const raw = await env.CERTIFICATION_EVIDENCE.get("current");
    if (!raw) return reply(200,{schema,candidates:[]});
    let batch;
    try {batch=JSON.parse(raw)} catch {return reply(503,{error:"INVALID_STORED_BATCH"})}
    if (batch.schema !== schema || !Array.isArray(batch.candidates)) return reply(503,{error:"INVALID_STORED_BATCH"});
    return reply(200,batch);
  }
  if (request.method === "POST") {
    if (!constantTimeEqual(bearer(request),env.FEED_WRITE_TOKEN)) return reply(401,{error:"UNAUTHORIZED"});
    const raw=await request.text();
    if (new TextEncoder().encode(raw).length > 1000000) return reply(413,{error:"TOO_LARGE"});
    let batch;
    try {batch=JSON.parse(raw)} catch {return reply(400,{error:"INVALID_JSON"})}
    if (batch?.schema !== schema || !Array.isArray(batch.candidates) ||
        batch.candidates.length > 500 || batch.candidates.some(x=>!x || typeof x!=="object" ||
        !x.model_attestation || !x.odds_attestation || !x.release_attestation))
      return reply(422,{error:"INVALID_SCHEMA"});
    // Structural checks only. The Python certification gate validates HMACs,
    // provenance, model release, exact quote, and timing independently.
    await env.CERTIFICATION_EVIDENCE.put("current",JSON.stringify(batch),{expirationTtl:900});
    return reply(202,{accepted:batch.candidates.length,certified:false});
  }
  return new Response(null,{status:405,headers:{allow:"GET, POST"}});
 }
};
