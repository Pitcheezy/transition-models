// node-three.mjs — Node에서 vendor three.js를 'three' / 'three/addons/…' 지정자로 쓰게 하는 로더(브라우저 import map의 Node판).
//   node --import ./node-three.mjs <script.mjs> …
import { register } from "node:module";
register("./node-three-hooks.mjs", import.meta.url);
