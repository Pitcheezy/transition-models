// node-three-hooks.mjs — node-three.mjs가 등록하는 해석 훅. 'three' → ../vendor/three.module.js, 'three/addons/X' → ../vendor/addons/X
const VENDOR = new URL("../vendor/", import.meta.url);
export async function resolve(specifier, context, next) {
  if (specifier === "three") return { url: new URL("three.module.js", VENDOR).href, shortCircuit: true };
  if (specifier.startsWith("three/addons/")) return { url: new URL("addons/" + specifier.slice("three/addons/".length), VENDOR).href, shortCircuit: true };
  return next(specifier, context);
}
