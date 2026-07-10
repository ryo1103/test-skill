import fs from 'node:fs';
import path from 'node:path';
import {bundle} from '@remotion/bundler';
import {renderFrames, selectComposition} from '@remotion/renderer';

const [entryPoint, compositionId, outputDir, propsPath, publicDir] = process.argv.slice(2);
if (!entryPoint || !compositionId || !outputDir || !propsPath || !publicDir) {
  throw new Error('Usage: render-sequence.mjs <entry> <composition> <output-dir> <props-json> <public-dir>');
}
const inputProps = JSON.parse(fs.readFileSync(propsPath, 'utf8'));
fs.mkdirSync(outputDir, {recursive: true});
const serveUrl = await bundle({entryPoint: path.resolve(entryPoint), publicDir: path.resolve(publicDir)});
const composition = await selectComposition({serveUrl, id: compositionId, inputProps});
await renderFrames({
  composition,
  serveUrl,
  outputDir: path.resolve(outputDir),
  inputProps,
  imageFormat: 'png',
  concurrency: 4,
  frame: [0, composition.durationInFrames - 1],
});
