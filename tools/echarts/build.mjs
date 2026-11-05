import { copyFileSync, mkdirSync, statSync } from "node:fs";
import { build } from "esbuild";

const out = new URL("../../addons/levelix_board/static/lib/echarts/", import.meta.url).pathname;
mkdirSync(out, { recursive: true });
await build({
    entryPoints: ["entry.js"], bundle: true, minify: true, format: "iife", target: "es2020",
    outfile: out + "echarts.min.js", legalComments: "none",
    banner: { js: "/*! Apache ECharts 5.6.0 (c) The Apache Software Foundation, Apache-2.0. Custom build, see NOTICE. */" },
});
copyFileSync("node_modules/echarts/LICENSE", out + "LICENSE");
copyFileSync("node_modules/echarts/NOTICE", out + "NOTICE");
console.log("built", out + "echarts.min.js", Math.round(statSync(out + "echarts.min.js").size / 1024), "KB");
