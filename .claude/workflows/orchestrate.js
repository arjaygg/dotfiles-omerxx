export const meta = {
  name: 'orchestrate',
  description: 'Interactive Coordinator skeleton: spec-driven worker, lensed review, DoD acceptance',
  phases: [
    { title: 'Implement', detail: 'one worker executes the frozen spec at plans/specs/<label>.md' },
    { title: 'Review', detail: 'lensed-review skill over the artifact; artifact + contract only' },
    { title: 'Accept', detail: 'check the Definition of Done at ai/references/definition-of-done.md' },
  ],
}

// Goal 05 Step 14 — interactive mode ONLY.
// Unattended paths (detached runs, HALT protocol, cron/CI entry points) are Step 15's
// scope and are deliberately absent here. See plan §13.
//
// §3 hard cap: `.claude/hooks/pre-tool-gate-v2.sh` SECTION 8 denies more than 3 literal
// subagent call sites — and its regex counts comment text too, so this file avoids writing
// that token anywhere except the one real call. Every stage funnels through `runStage`, so
// the count stays at 1 no matter how many stages are added.

const DOD_PATH = 'ai/references/definition-of-done.md'
const SPEC_PATH = 'plans/specs'

// Bound on how many findings the acceptance stage is handed. §3: log every cap.
const MAX_FINDINGS_TO_ACCEPTANCE = 20

const WORKER_SCHEMA = {
  type: 'object',
  properties: {
    changedFiles: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
    valid: { type: 'boolean' },
    issues: { type: 'array', items: { type: 'string' } },
  },
  required: ['changedFiles', 'summary', 'valid'],
  additionalProperties: true,
}

// Mirrors REVIEW_SCHEMA in ai/skills/cap/references/schemas.md (Step 10 finding contract).
// No ranking/priority field on a finding — the producing lens does not rank its own output.
const REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    dimension: { type: 'string' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          lens: { type: 'string' },
          category: { type: 'string' },
          file: { type: 'string' },
          line: { type: 'number' },
          description: { type: 'string' },
          fix: { type: 'string' },
          confidence: { type: 'number' },
        },
        required: ['lens', 'category', 'file', 'line', 'description', 'fix', 'confidence'],
        additionalProperties: true,
      },
    },
  },
  required: ['dimension', 'findings'],
  additionalProperties: true,
}

const ACCEPT_SCHEMA = {
  type: 'object',
  properties: {
    dodPath: { type: 'string' },
    dodFound: { type: 'boolean' },
    unmet: { type: 'array', items: { type: 'string' } },
    accepted: { type: 'boolean' },
  },
  required: ['dodPath', 'dodFound', 'unmet', 'accepted'],
  additionalProperties: true,
}

// Schema-shaped fixtures for `args.dryRun`. Each mirrors the schema its stage declares,
// so a dry run exercises the same null-guards and result handling as a live run.
function fixtureFor(stage, opts) {
  if (stage === 'implement') {
    return {
      changedFiles: ['.claude/workflows/orchestrate.js'],
      summary: 'dry-run fixture: worker did not execute',
      valid: true,
      issues: [],
    }
  }
  if (stage === 'review') {
    return {
      dimension: 'correctness',
      findings: [
        {
          lens: 'correctness',
          category: 'quality',
          file: '.claude/workflows/orchestrate.js',
          line: 1,
          description: 'dry-run fixture finding',
          fix: 'none — fixture',
          confidence: 0.5,
        },
      ],
    }
  }
  // accept — `opts.dodMissing` exercises the absent-DoD path without a live agent.
  const found = !opts.dodMissing
  return {
    dodPath: DOD_PATH,
    dodFound: found,
    unmet: found ? [] : ['definition-of-done.md not found'],
    accepted: found,
  }
}

// The ONLY literal subagent call site in this script (§3). Every stage routes through it,
// and it always supplies both `schema` and `label`.
async function runStage(stage, prompt, opts) {
  if (opts.dryRun) {
    log(`[dry-run] stage=${stage} label=${opts.label} — returning schema-shaped fixture`)
    return fixtureFor(stage, opts)
  }
  return agent(prompt, { schema: opts.schema, label: opts.label, phase: opts.phase })
}

const dryRun = Boolean(args && args.dryRun)
const dodMissing = Boolean(args && args.dodMissing)
const label = (args && args.label) || 'unlabeled'
const specPath = `${SPEC_PATH}/${label}.md`

if (dryRun) log('dry-run mode: no subagents are spawned; every stage returns a fixture')

// ---------------------------------------------------------------- Implement
phase('Implement')

const impl = await runStage(
  'implement',
  `Read the frozen spec at ${specPath} and implement it yourself. Do not spawn subagents. ` +
    `Return the files you changed and whether the spec's acceptance criteria are met.`,
  { dryRun, dodMissing, label: `implement:${label}`, phase: 'Implement', schema: WORKER_SCHEMA },
)

if (!impl) {
  // A skipped or dead worker yields null here; guard before touching the result.
  log('implement stage returned null (skipped or failed) — aborting before review')
  return { ok: false, stage: 'implement', reason: 'null result' }
}
if (!impl.valid) {
  log(`implement stage reported invalid: ${(impl.issues || []).join('; ') || 'no issues given'}`)
}

// ------------------------------------------------------------------- Review
phase('Review')

// §21 reviewer input isolation: ARTIFACT + CONTRACT only. The reviewer is given the changed
// file paths (artifact) and the finding contract, and is given NEITHER the worker's summary
// or claim of validity, NOR any prior reasoning, NOR another reviewer's findings.
const artifact = (impl.changedFiles || []).join('\n')

const review = await runStage(
  'review',
  `Invoke the \`lensed-review\` skill over the artifact below. Do not embed your own review ` +
    `logic — lensed-review owns the lenses and their stances.\n\n` +
    `ARTIFACT (changed files):\n${artifact}\n\n` +
    `CONTRACT: return REVIEW_SCHEMA as defined in ai/skills/cap/references/schemas.md — ` +
    `{dimension, findings[]} where each finding is {lens, category, file, line, description, ` +
    `fix, confidence}. Do not rank or prioritise findings; the Coordinator triages.`,
  { dryRun, dodMissing, label: `review:${label}`, phase: 'Review', schema: REVIEW_SCHEMA },
)

let findings = []
if (!review) {
  log('review stage returned null (skipped or failed) — proceeding to acceptance with 0 findings')
} else {
  findings = review.findings || []
}

// §3: log every cap. Silent truncation reads as "covered everything."
if (findings.length > MAX_FINDINGS_TO_ACCEPTANCE) {
  log(
    `CAP APPLIED: ${findings.length} findings produced, only the first ` +
      `${MAX_FINDINGS_TO_ACCEPTANCE} are passed to acceptance; ` +
      `${findings.length - MAX_FINDINGS_TO_ACCEPTANCE} dropped.`,
  )
  findings = findings.slice(0, MAX_FINDINGS_TO_ACCEPTANCE)
}
log(`review produced ${findings.length} finding(s) after caps`)

// ------------------------------------------------------------------- Accept
phase('Accept')

const accept = await runStage(
  'accept',
  `Read the standing Definition of Done at ${DOD_PATH}. If the file does not exist, set ` +
    `dodFound=false and list that as the sole unmet item — do not invent criteria. ` +
    `Otherwise evaluate each DoD item against the changed files below and the ` +
    `${findings.length} review finding(s) supplied.\n\n` +
    `CHANGED FILES:\n${artifact}\n\n` +
    `FINDINGS:\n${JSON.stringify(findings)}`,
  { dryRun, dodMissing, label: `accept:${label}`, phase: 'Accept', schema: ACCEPT_SCHEMA },
)

if (!accept) {
  log('accept stage returned null (skipped or failed) — cannot certify acceptance')
  return { ok: false, stage: 'accept', reason: 'null result', findings }
}
if (!accept.dodFound) {
  // Absent-DoD path: recorded explicitly rather than silently treated as "nothing to check."
  log(`Definition of Done not found at ${accept.dodPath} — acceptance is unverified`)
}

return {
  ok: Boolean(accept.accepted),
  dryRun,
  label,
  specPath,
  changedFiles: impl.changedFiles || [],
  findings,
  dodFound: accept.dodFound,
  unmet: accept.unmet || [],
}
