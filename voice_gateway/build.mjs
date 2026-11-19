import {build} from "esbuild";
import {mkdir,copyFile} from "node:fs/promises";
import {join} from "node:path";

const root = new URL(".",import.meta.url).pathname;
await mkdir(join(root,"dist"),{recursive:true});
await build({
  entryPoints:[join(root,"web","app.js")],
  outfile:join(root,"dist","app.js"),
  bundle:true,format:"esm",platform:"browser",target:"es2022",
  minify:true,logLevel:"warning",
});
await build({
  entryPoints:[join(root,"web","anam-room.js")],
  outfile:join(root,"dist","anam-room.js"),
  bundle:true,format:"esm",platform:"browser",target:"es2022",
  minify:true,logLevel:"warning",
});
await copyFile(join(root,"web","anam-room.html"),join(root,"dist","anam-room.html"));
await copyFile(join(root,"web","anam-room.css"),join(root,"dist","anam-room.css"));
await copyFile(join(root,"web","index.html"),join(root,"dist","index.html"));
await copyFile(join(root,"web","style.css"),join(root,"dist","style.css"));
for (const file of ["zoom-video.html","zoom-video.css","zoom-video.js"]) {
  await copyFile(join(root,"web",file),join(root,"dist",file));
}
console.log("Built protected CEO meeting room (no embedded agent IDs or keys)");
