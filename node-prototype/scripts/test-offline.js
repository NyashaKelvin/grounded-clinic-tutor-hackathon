// Offline tests for the grounding safeguard (no API key needed): node scripts/test-offline.js
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const { classify } = require("../gemini");
const source = fs.readFileSync(path.join(__dirname, "..", "..", "sample", "hyperkalemia.txt"), "utf8");

// 1. Model says grounded + real verbatim excerpt (with different whitespace/case) -> grounded
let r = classify({ grounded: true, explanation: "x", mnemonic: "C-I-K", source_excerpt_used: "Give IV calcium (calcium gluconate 10%,\n10 mL over 2 to 3 minutes) FIRST", confidence_note: "" }, source);
assert.strictEqual(r.status, "grounded");

// 2. Model says grounded but invents an excerpt -> unverified (downgraded)
r = classify({ grounded: true, explanation: "x", mnemonic: "m", source_excerpt_used: "Give 40 mg IV furosemide to excrete potassium", confidence_note: "" }, source);
assert.strictEqual(r.status, "unverified");
assert.ok(r.confidence_note.includes("could not be found"));

// 3. Model says grounded with empty excerpt -> unverified
r = classify({ grounded: true, explanation: "x", mnemonic: "m", source_excerpt_used: "", confidence_note: "" }, source);
assert.strictEqual(r.status, "unverified");

// 4. Refusal -> not_found, mnemonic/excerpt stripped even if model leaked some
r = classify({ grounded: false, explanation: "Not covered.", mnemonic: "leaked", source_excerpt_used: "leaked", confidence_note: "" }, source);
assert.strictEqual(r.status, "not_found");
assert.strictEqual(r.mnemonic, "");
assert.strictEqual(r.source_excerpt_used, "");

console.log("All offline safeguard tests passed (4/4).");
