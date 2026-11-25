const NO_STORE={"Cache-Control":"no-store","X-Content-Type-Options":"nosniff","Referrer-Policy":"no-referrer","X-Frame-Options":"DENY"};
const reply=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{...NO_STORE,"Content-Type":"application/json"}});
const localOnly = url => /^(localhost|127\.0\.0\.1|\[::1\])$/.test(url.hostname);
export async function handleAudience(request,env,fetcher=fetch){
 const url=new URL(request.url);
 if(url.pathname==="/healthz"&&request.method==="GET")
   return reply({status:"up",component:"podcast_audience",storage_configured:!!env.QUESTIONS_DB,turnstile_configured:!!env.TURNSTILE_SECRET_KEY});
 if(url.pathname==="/api/questions"&&request.method==="POST"){
  if(!env.QUESTIONS_DB||!env.TURNSTILE_SECRET_KEY||!env.AUDIENCE_LIMITER)return reply({error:"submissions_not_configured"},503);
  if(!request.headers.get("Content-Type")?.startsWith("application/json"))return reply({error:"json_required"},415);
  if(Number(request.headers.get("content-length")||"0")>2500)return reply({error:"request_too_large"},413);
  const origin=request.headers.get("Origin");
  if(origin!==url.origin)return reply({error:"same_origin_required"},403);
  let data;try{const raw=await request.text();if(raw.length>2500)return reply({error:"request_too_large"},413);data=JSON.parse(raw)}catch{return reply({error:"invalid_json"},400)}
  if(!data||typeof data!=="object"||Array.isArray(data)||Object.keys(data).some(k=>!["name","question","token"].includes(k)))return reply({error:"invalid_fields"},400);
  const name=String(data.name||"Anonymous").trim().slice(0,60),question=String(data.question||"").trim(),token=String(data.token||"");
  if(question.length<12||question.length>600||token.length<10||token.length>2048)return reply({error:"invalid_question_or_token"},400);
  const ip=request.headers.get("CF-Connecting-IP")||"unknown";
  const limit=await env.AUDIENCE_LIMITER.limit({key:"q:"+ip});if(!limit?.success)return reply({error:"rate_limited"},429);
  const form=new FormData();form.set("secret",env.TURNSTILE_SECRET_KEY);form.set("response",token);if(ip!=="unknown")form.set("remoteip",ip);
  let verified;try{const r=await fetcher("https://challenges.cloudflare.com/turnstile/v0/siteverify",{method:"POST",body:form});if(!r.ok)return reply({error:"verification_unavailable"},503);verified=await r.json()}catch{return reply({error:"verification_unavailable"},503)}
  if(verified.success!==true)return reply({error:"verification_failed"},403);
  const id=crypto.randomUUID(),now=new Date().toISOString();
  try{await env.QUESTIONS_DB.prepare("INSERT INTO questions(id,received_at,display_name,question,status) VALUES (?,?,?,?,?)").bind(id,now,name||"Anonymous",question,"pending").run()}
  catch{return reply({error:"storage_unavailable"},503)}
  return reply({accepted:true,review_required:true},202);
 }
 if(url.pathname==="/api/admin/questions"&&request.method==="GET"){
  if(typeof env.PODCAST_QUESTIONS_ADMIN_KEY!=="string"||env.PODCAST_QUESTIONS_ADMIN_KEY.length<24||!env.QUESTIONS_DB)return reply({error:"admin_not_configured"},503);
  const bearer=request.headers.get("Authorization")||"";
  if(bearer!=="Bearer "+env.PODCAST_QUESTIONS_ADMIN_KEY)return reply({error:"unauthorized"},401);
  const limit=Math.min(50,Math.max(1,Number(url.searchParams.get("limit")||30)||30));
  try{const result=await env.QUESTIONS_DB.prepare("SELECT id,received_at,display_name,question,status FROM questions WHERE status='pending' ORDER BY received_at DESC LIMIT ?").bind(limit).all();return reply({items:result.results||[],publicly_visible:false})}
  catch{return reply({error:"storage_unavailable"},503)}
 }
 if(url.pathname==="/api/admin/questions/status"&&request.method==="POST"){
  if(typeof env.PODCAST_QUESTIONS_ADMIN_KEY!=="string"||env.PODCAST_QUESTIONS_ADMIN_KEY.length<24||!env.QUESTIONS_DB)return reply({error:"admin_not_configured"},503);
  if(request.headers.get("Authorization")!=="Bearer "+env.PODCAST_QUESTIONS_ADMIN_KEY)return reply({error:"unauthorized"},401);
  if(!request.headers.get("Content-Type")?.startsWith("application/json"))return reply({error:"json_required"},415);
  let data;try{data=JSON.parse((await request.text()).slice(0,500))}catch{return reply({error:"invalid_json"},400)}
  if(!/^[a-f0-9-]{36}$/i.test(String(data?.id||""))||!["approved","dismissed"].includes(data?.status))return reply({error:"invalid_status"},400);
  try{await env.QUESTIONS_DB.prepare("UPDATE questions SET status=? WHERE id=? AND status='pending'").bind(data.status,data.id).run();return reply({updated:true})}catch{return reply({error:"storage_unavailable"},503)}
 }
 if(url.pathname==="/"&&request.method==="GET"){
  if(!env.ASSETS)return reply({error:"public_form_assets_not_configured"},503);
  const r=await env.ASSETS.fetch(request);const h=new Headers(r.headers);Object.entries(NO_STORE).forEach(([k,v])=>h.set(k,v));
  h.set("Content-Security-Policy","default-src 'self'; script-src 'self' https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; connect-src 'self' https://challenges.cloudflare.com; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'");
  return new Response(r.body,{status:r.status,headers:h});
 }
 if(request.method!=="GET"&&request.method!=="HEAD")return reply({error:"method_not_allowed"},405);
 if(env.ASSETS){const r=await env.ASSETS.fetch(request);return new Response(r.body,{status:r.status,headers:{...Object.fromEntries(r.headers),...NO_STORE}})}
 return reply({error:"not_found"},404);
}
export default{fetch(request,env){return handleAudience(request,env)}};
