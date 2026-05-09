#!/usr/bin/env node
/**
 * Compatibility shim: forwards Jest-style --testPathPattern=<re> to Vitest positional filters.
 */
import { spawnSync } from 'node:child_process';

const forwarded = [];
let pathPattern;
for (const arg of process.argv.slice(2)) {
  const m = arg.match(/^--testPathPattern=(.*)$/);
  if (m) {
    pathPattern = m[1];
    continue;
  }
  forwarded.push(arg);
}

const vitestArgs = ['vitest', 'run'];
if (pathPattern) vitestArgs.push(pathPattern);
vitestArgs.push(...forwarded);

const r = spawnSync('npx', vitestArgs, { stdio: 'inherit', shell: process.platform === 'win32' });
process.exit(r.status ?? 1);
