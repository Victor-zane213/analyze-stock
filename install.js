#!/usr/bin/env node
// analyze-stock skill installer for Claude Code
// Usage: npx analyze-stock          → install to ~/.claude/skills/
//        npx analyze-stock --project  → install to ./.claude/skills/

const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const SKILL_NAME = "analyze-stock";
const PROJECT_FLAG = process.argv.includes("--project");

const targetDir = PROJECT_FLAG
  ? path.join(process.cwd(), ".claude", "skills", SKILL_NAME)
  : path.join(process.env.HOME, ".claude", "skills", SKILL_NAME);

// Files/dirs to copy (relative to this script's location)
const payloads = [
  "SKILL.md",
  "config.yaml",
  "macro_risks.yaml",
  "niushan.yaml",
  "sectors.yaml",
  "valuation_reference.yaml",
  "requirements.txt",
  "financial.md",
  "scripts",
  "docs",
];

const srcRoot = path.resolve(__dirname);

console.log(`\n📦 Installing ${SKILL_NAME} to ${targetDir} ...\n`);

// clean old install
if (fs.existsSync(targetDir)) {
  fs.rmSync(targetDir, { recursive: true, force: true });
}
fs.mkdirSync(targetDir, { recursive: true });

// copy payloads
for (const p of payloads) {
  const src = path.join(srcRoot, p);
  const dest = path.join(targetDir, p);
  if (!fs.existsSync(src)) {
    console.warn(`  ⚠ skipping missing: ${p}`);
    continue;
  }
  fs.cpSync(src, dest, { recursive: true });
  console.log(`  ✓ ${p}`);
}

// install python deps
console.log(`\n📦 Installing Python dependencies ...`);
try {
  execSync(`pip install -r "${path.join(targetDir, 'requirements.txt')}"`, {
    stdio: "inherit",
  });
} catch (e) {
  console.warn("  ⚠ pip install failed — run manually:");
  console.warn(`    pip install -r "${path.join(targetDir, 'requirements.txt')}"`);
}

console.log(`\n✅ ${SKILL_NAME} installed!`);
console.log(`\nNext:`);
console.log(`  1. Edit ${path.join(targetDir, 'config.yaml')} and set your LLM API key`);
console.log(`  2. Restart Claude Code (or /reload)`);
console.log(`  3. Try: 分析 贵州茅台  |  选股  |  板块排名\n`);
console.log(`Get a free LLM API key: https://platform.deepseek.com\n`);
