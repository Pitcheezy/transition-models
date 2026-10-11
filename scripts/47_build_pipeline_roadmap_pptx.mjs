import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const HOME = process.env.HOME || process.env.USERPROFILE || "C:\\Users\\zpfh1";
process.env.HOME = HOME;

async function latestPresentationUtils() {
  const base = path.join(HOME, ".codex", "plugins", "cache", "openai-primary-runtime", "presentations");
  const versions = (await fs.readdir(base, { withFileTypes: true }))
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();
  if (!versions.length) throw new Error(`No presentation runtime found under ${base}`);
  return path.join(
    base,
    versions.at(-1),
    "skills",
    "presentations",
    "scripts",
    "artifact_tool_utils.mjs",
  );
}

const utils = await import(pathToFileURL(await latestPresentationUtils()).href);
const {
  createSlideContext,
  ensureArtifactToolWorkspace,
  importArtifactTool,
  saveBlobToFile,
} = utils;

const workspaceDir = path.join(ROOT, "outputs", "manual-20260602-pipeline-roadmap", "presentations", "pipeline-roadmap");
const outputDir = path.join(ROOT, "outputs", "presentations");
const previewDir = path.join(outputDir, "pipeline_roadmap_preview");
const slideSize = { width: 1600, height: 900 };

const slides = [
  {
    title: "project_full_pipeline",
    image: path.join(ROOT, "outputs", "figures", "project_full_pipeline.png"),
  },
  {
    title: "future_work_roadmap_slide",
    image: path.join(ROOT, "outputs", "figures", "future_work_roadmap_slide.png"),
  },
];

await ensureArtifactToolWorkspace(workspaceDir);
const artifact = await importArtifactTool(workspaceDir);
const { Presentation, PresentationFile } = artifact;
const presentation = Presentation.create({ slideSize });

for (const item of slides) {
  const slide = presentation.slides.add();
  slide.background.fill = "#FFFFFF";
  const ctx = createSlideContext(artifact, {
    slideSize,
    workspaceDir,
    outputDir,
  });
  await ctx.addImage(slide, {
    path: item.image,
    x: 0,
    y: 0,
    w: slideSize.width,
    h: slideSize.height,
    fit: "contain",
    alt: item.title,
  });
}

await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });

for (let i = 0; i < presentation.slides.count; i += 1) {
  const slide = presentation.slides.getItem(i);
  const png = await presentation.export({ slide, format: "png", scale: 1 });
  await saveBlobToFile(png, path.join(previewDir, `slide-${String(i + 1).padStart(2, "0")}.png`));
}

const outputPptx = path.join(outputDir, "project_pipeline_future_plan.pptx");
const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(outputPptx);

const stat = await fs.stat(outputPptx);
console.log(JSON.stringify({
  outputPptx,
  outputBytes: stat.size,
  previewDir,
  slideCount: presentation.slides.count,
}, null, 2));
