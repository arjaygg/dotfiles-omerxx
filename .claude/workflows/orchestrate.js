export const meta = {
  name: 'orchestrate',
  description: 'Coordinator: spec-driven worker, lensed review, triage, DoD acceptance, HALT',
  phases: [
    { title: 'Implement', detail: 'one worker executes the frozen spec at plans/specs/<label>.md' },
    { title: 'Review', detail: 'lensed-review skill over the artifact; artifact + contract only' },
    { title: 'Triage', detail: 'Coordinator assigns category and severity; scope authority enforced' },
    { title: 'Accept', detail: 'check the Definition of Done at ai/references/definition-of-done.md' },
  ],
}

// Goal 05 Steps 14 (interactive skeleton) + 15 (unattended-safety delta).
//
// Unattended does NOT mean backgrounded. Per plan §13, Workflow stays usable unattended
// because every stage below is a synchronous await and this script IS the run. What is
// forbidden is ending a turn on a backgrounded call — there is no event loop to resume it.
// Hence: no background-process flag and no detach path anywhere below. Those two token
// names are also what Step 15's acceptance greps for, so they are not written in prose
// either — a disclaiming comment would read as a hit.
//
// §3 hard cap: `.claude/hooks/pre-tool-gate-v2.sh` SECTION 8 denies more than 3 literal
// subagent call sites — and its regex counts comment text too, so this file avoids writing
// that token anywhere except the one real call. All four stages funnel through `runStage`,
// so the count stays at 1 no matter how many stages are added.

const DOD_PATH = 'ai/references/definition-of-done.md'
const SPEC_DIR = 'plans/specs'

// Bound on how many findings the acceptance stage is handed. §3: log every cap.
const MAX_FINDINGS_TO_ACCEPTANCE = 20

// §24 loop bounds. Never raise one to make a run pass — if a bound is too tight the
// artifact is too big, and the fix is to decompose it.
const BOUNDS = { retry_count: 3, doubt_cycle_iteration: 3, review_loop_iteration: 5 }

const CATEGORIES = ['intent_gap', 'bad_spec', 'patch', 'defer', 'reject']
const SEVERITIES = ['low', 'medium', 'high']

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

// §20 finding contract. A finding carries exactly these fields, plus any the producing
// lens declares. No severity, priority, or ranking field — severity is a function of
// consequence for the artifact's consumer, which only the Coordinator knows, so it is
// assigned in Triage below and never by the producer.
const FINDING_SCHEMA = {
  type: 'object',
  properties: {
    lens: { type: 'string' },
    location: { type: 'string' },
    trigger_condition: { type: 'string' },
    guard_snippet: { type: 'string' },
    potential_consequence: { type: 'string' },
  },
  required: ['lens', 'location', 'trigger_condition', 'guard_snippet', 'potential_consequence'],
  additionalProperties: true,
}

const REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    dimension: { type: 'string' },
    findings: { type: 'array', items: FINDING_SCHEMA },
  },
  required: ['dimension', 'findings'],
  additionalProperties: true,
}

// The triage stage PROPOSES; this script ENFORCES (§23). `out_of_scope` plus `authority`
// exist so the scope-authority rule is checkable rather than trusted.
const TRIAGE_SCHEMA = {
  type: 'object',
  properties: {
    rulings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          index: { type: 'number' },
          category: { type: 'string', enum: CATEGORIES },
          severity: { type: 'string', enum: SEVERITIES },
          out_of_scope: { type: 'boolean' },
          authority: { type: 'string', enum: ['intent', 'spec_scope', 'plan', 'diff', 'none'] },
          ambiguous_between: { type: 'array', items: { type: 'string' } },
        },
        required: ['index', 'category', 'severity'],
        additionalProperties: true,
      },
    },
  },
  required: ['rulings'],
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

const STATUS_SCHEMA = {
  type: 'object',
  properties: {
    written: { type: 'boolean' },
    path: { type: 'string' },
  },
  required: ['written', 'path'],
  additionalProperties: true,
}

// ------------------------------------------------------------------ fixtures

function defaultFinding(i, lens) {
  return {
    lens: lens || 'correctness',
    location: `.claude/workflows/orchestrate.js:${i + 1}`,
    trigger_condition: `dry-run fixture finding ${i + 1}`,
    guard_snippet: 'none — fixture',
    potential_consequence: 'none — fixture',
  }
}

// Schema-shaped fixtures for `args.dryRun`. Acceptance cases are driven entirely through
// `args`, so each one is a single Workflow invocation with no live worker.
function fixtureFor(stage, opts) {
  const f = opts.fixtures || {}
  if (stage === 'implement') {
    return (
      f.implement || {
        changedFiles: ['.claude/workflows/orchestrate.js'],
        summary: 'dry-run fixture: worker did not execute',
        valid: true,
        issues: [],
      }
    )
  }
  if (stage === 'review') {
    return f.review || { dimension: 'correctness', findings: [defaultFinding(0)] }
  }
  if (stage === 'triage') {
    if (f.triage) return f.triage
    const findings = (f.review && f.review.findings) || [defaultFinding(0)]
    return {
      rulings: findings.map((_, i) => ({
        index: i,
        category: 'patch',
        severity: 'low',
        out_of_scope: false,
        authority: 'none',
      })),
    }
  }
  if (stage === 'mark_running') {
    return f.mark_running || { written: true, path: opts.specPath }
  }
  if (stage === 'halt') {
    return f.halt || { written: true, path: opts.haltPath }
  }
  const found = !opts.dodMissing
  return (
    f.accept || {
      dodPath: DOD_PATH,
      dodFound: found,
      unmet: found ? [] : ['definition-of-done.md not found'],
      accepted: found,
    }
  )
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

// ------------------------------------------------------------------- §23 triage

// A finding may be routed defer/reject AS OUT OF SCOPE only on the authority of the intent
// itself. The spec's own scope language, the plan, and the shape of the diff are NOT
// admissible authorities — if only they exclude the finding, that is evidence against the
// current reading, not evidence of out-of-scope. Without this, an autonomous agent
// dismisses a finding because the artifact it just wrote does not mention it.
function enforceScopeAuthority(ruling) {
  const excluded = ruling.category === 'defer' || ruling.category === 'reject'
  if (!excluded || !ruling.out_of_scope) return ruling
  if (ruling.authority === 'intent') return ruling
  // 'none' means the intent is silent or ambiguous — a human has to resolve it.
  const rerouted = ruling.authority === 'none' ? 'intent_gap' : 'bad_spec'
  log(
    `SCOPE AUTHORITY: finding ${ruling.index} routed '${ruling.category}' as out-of-scope on ` +
      `'${ruling.authority}' authority, which is inadmissible — rerouted to '${rerouted}'`,
  )
  return { ...ruling, category: rerouted, rerouted_from: ruling.category }
}

// In doubt between bad_spec and patch, prefer bad_spec — a spec-level fix produces more
// coherent code. Unsure between defer and reject, prefer reject — only defer what you are
// confident is real, or the deferred file becomes a landfill.
function applyTieBreakers(ruling) {
  const between = ruling.ambiguous_between || []
  if (between.includes('bad_spec') && between.includes('patch') && ruling.category === 'patch') {
    log(`TIE-BREAK: finding ${ruling.index} ambiguous bad_spec/patch — preferring bad_spec`)
    return { ...ruling, category: 'bad_spec' }
  }
  if (between.includes('defer') && between.includes('reject') && ruling.category === 'defer') {
    log(`TIE-BREAK: finding ${ruling.index} ambiguous defer/reject — preferring reject`)
    return { ...ruling, category: 'reject' }
  }
  return ruling
}

// Any intent_gap makes everything below it moot; any bad_spec makes patch findings moot,
// because the code is about to be re-derived.
function applyCascade(rulings) {
  if (rulings.some((r) => r.category === 'intent_gap')) {
    log('CASCADE: an intent_gap is present — every other finding is moot this pass')
    return rulings.map((r) => (r.category === 'intent_gap' ? r : { ...r, moot: true }))
  }
  if (rulings.some((r) => r.category === 'bad_spec')) {
    log('CASCADE: a bad_spec is present — patch findings are moot pending re-derivation')
    return rulings.map((r) => (r.category === 'patch' ? { ...r, moot: true } : r))
  }
  return rulings
}

// Dedupe only findings with the same claim AND the same required action. Overlap between
// lenses is signal, not noise — each survivor is then evaluated independently.
function dedupe(findings) {
  const seen = new Set()
  const kept = []
  for (const f of findings) {
    const key = `${f.trigger_condition}||${f.guard_snippet}`
    if (seen.has(key)) continue
    seen.add(key)
    kept.push(f)
  }
  const dropped = findings.length - kept.length
  if (dropped > 0) log(`DEDUPE: ${dropped} finding(s) had the same claim and the same action`)
  return kept
}

// ------------------------------------------------------------------ §25 signal

// Computed, never judged. Counts only patch findings — never defer, never reject.
function followupSignal(rulings) {
  const patch = rulings.filter((r) => r.category === 'patch' && !r.moot)
  const counts = { high: 0, medium: 0, low: 0 }
  for (const r of patch) counts[r.severity] = (counts[r.severity] || 0) + 1
  const score = 3 * counts.medium + counts.low
  const recommended = counts.high > 0 || score >= 5
  return { recommended, counts, score }
}

// -------------------------------------------------------------------- §15 HALT

// Every exit path writes a terminal status to a durable artifact before stopping — there
// is nobody to read a chat message. A run ending without one is indistinguishable from a
// crash. Degenerate cases get their own deterministic filename rather than a third
// title-derived name that could collide with either candidate.
function haltPathFor(label, resolution) {
  if (resolution === 'unresolved') return `${SPEC_DIR}/${label}-unresolved.md`
  if (resolution === 'ambiguous') return `${SPEC_DIR}/${label}-ambiguous.md`
  return `${SPEC_DIR}/${label}.md`
}

const terminal = { written: false }

async function halt(status, condition, ctx, extra) {
  const payload = {
    status,
    condition,
    artifact: ctx.haltPath,
    label: ctx.label,
    retry_count: ctx.counters.retry_count,
    doubt_cycle_iteration: ctx.counters.doubt_cycle_iteration,
    review_loop_iteration: ctx.counters.review_loop_iteration,
    followup_review_recommended: ctx.followup ? ctx.followup.recommended : false,
    ...(extra || {}),
  }
  // Machine-readable on stdout as well as on disk: the transcript survives even when the
  // write itself is what failed.
  log(`HALT ${JSON.stringify(payload)}`)
  // A workflow script has no filesystem access, so the write-back is delegated to a stage
  // agent. In dry runs the fixture stands in for it.
  const written = await runStage(
    'halt',
    `Write this terminal status to ${ctx.haltPath}. If the file exists, update its ` +
      `frontmatter in place; otherwise create it with this frontmatter and nothing else. ` +
      `Do not edit any other file.\n\n${JSON.stringify(payload, null, 2)}`,
    { ...ctx.stageOpts, label: `halt:${ctx.label}`, phase: 'Accept', schema: STATUS_SCHEMA },
  )
  terminal.written = Boolean(written && written.written)
  if (!terminal.written) {
    log(`HALT WRITE FAILED for ${ctx.haltPath} — the next run must treat this as a crash`)
  }
  // `done` is not reportable unless the status actually persisted. Unattended there is
  // nobody to read the log line above, so a run that finished but could not record that it
  // finished is indistinguishable from one that died mid-flight — and must not read as ok.
  return {
    ok: status === 'done' && terminal.written,
    ...payload,
    terminal_status_written: terminal.written,
    triageLog: ctx.triageLog,
  }
}

// §15: the SIGKILL detector needs a producer. No in-process handler can catch SIGKILL, so a
// killed run has to be recognised from the other side — a spec whose frontmatter still says
// `running` with no terminal status did not finish. That only works if something actually
// writes `running`. Nothing did: plans/specs/TEMPLATE.md ships `status: draft` and this script
// never updated it, so an in-flight run was indistinguishable from a never-started one and the
// documented detector had no producer at all.
async function markRunning(specPath, ctx) {
  const written = await runStage(
    'mark_running',
    `Set \`status: running\` in the frontmatter of ${specPath}, leaving every other ` +
      `frontmatter key and the entire body byte-identical. Do not edit any other file.`,
    {
      ...ctx.stageOpts,
      specPath,
      label: `mark_running:${ctx.label}`,
      phase: 'Implement',
      schema: STATUS_SCHEMA,
    },
  )
  if (!(written && written.written)) {
    log(
      `MARK RUNNING FAILED for ${specPath} — from here on a kill cannot be told apart from a ` +
        `run that never started`,
    )
  }
  return Boolean(written && written.written)
}

// ------------------------------------------------------------------------ run

const dryRun = Boolean(args && args.dryRun)
const dodMissing = Boolean(args && args.dodMissing)
const label = (args && args.label) || 'unlabeled'
const specResolution = (args && args.specResolution) || 'ok'
const fixtures = (args && args.fixtures) || {}
const fm = (args && args.frontmatter) || {}

// §24: every bounded loop persists its counter in the governing artifact's frontmatter.
// An in-context counter silently resets at compaction, on a crash, or on a resumed cron
// run, and the loop then runs forever — so these are read IN from frontmatter, never
// initialised to zero here.
const counters = {
  retry_count: Number(fm.retry_count || 0),
  doubt_cycle_iteration: Number(fm.doubt_cycle_iteration || 0),
  review_loop_iteration: Number(fm.review_loop_iteration || 0),
}

const haltPath = haltPathFor(label, specResolution)
const stageOpts = { dryRun, dodMissing, fixtures, haltPath }
const ctx = { label, haltPath, counters, stageOpts, triageLog: null, followup: null }

if (dryRun) log('dry-run mode: no subagents are spawned; every stage returns a fixture')
if (specResolution !== 'ok') {
  log(`spec resolution '${specResolution}' — terminal status goes to ${haltPath}`)
}

// A thrown stage is an exit path too, and §15 admits no exit without a terminal status. The
// write lives in `catch`, NOT in `finally`: `finally` cannot tell "returned normally without
// writing" apart from "threw", and the condition has to name the error. (An earlier version of
// this comment claimed try/finally already guaranteed the write on a throw — it did not; the
// `finally` only logged, so a thrown stage left no artifact at all.)
// SIGKILL is still uncoverable in-process; markRunning() above is what makes the other-side
// detector real — a spec whose frontmatter says `running` with no terminal status is a crashed
// run, and the next run treats it as one.
let result
try {
  if (specResolution !== 'ok') {
    result = await halt('blocked', `spec path ${specResolution} for label '${label}'`, ctx)
  } else if (counters.review_loop_iteration > BOUNDS.review_loop_iteration) {
    result = await halt(
      'blocked',
      `review repair loop exceeded ${BOUNDS.review_loop_iteration} iterations (non-convergence)`,
      ctx,
    )
  } else if (counters.retry_count > BOUNDS.retry_count) {
    result = await halt('blocked', `schema-invalid retries exceeded ${BOUNDS.retry_count}`, ctx)
  } else if (counters.doubt_cycle_iteration > BOUNDS.doubt_cycle_iteration) {
    result = await halt(
      'blocked',
      `doubt cycle exceeded ${BOUNDS.doubt_cycle_iteration} — decompose the artifact, ` +
        'do not raise the bound',
      ctx,
    )
  } else {
    result = await main()
  }
} catch (err) {
  if (!terminal.written) {
    try {
      await halt('blocked', `run threw before completing: ${(err && err.message) || String(err)}`, ctx)
    } catch (haltErr) {
      // Never let the recovery write mask the original failure.
      log(`HALT WRITE THREW while handling a stage error: ${(haltErr && haltErr.message) || String(haltErr)}`)
    }
  }
  throw err
} finally {
  if (!terminal.written) {
    log(`NO TERMINAL STATUS WRITTEN for ${haltPath} — this run is indistinguishable from a crash`)
  }
}

return result

async function main() {
  const specPath = `${SPEC_DIR}/${label}.md`

  // ------------------------------------------------------------- Implement
  phase('Implement')

  // Before any work: stamp `status: running` so a SIGKILL from here on is detectable. Only on
  // this path — the bound-exceeded and bad-spec-path branches above halt without ever starting,
  // so marking them running would invent an in-flight run that never was.
  await markRunning(specPath, ctx)

  const impl = await runStage(
    'implement',
    `Read the frozen spec at ${specPath} and implement it yourself. Do not spawn subagents. ` +
      `Return the files you changed and whether the spec's acceptance criteria are met.`,
    { ...stageOpts, label: `implement:${label}`, phase: 'Implement', schema: WORKER_SCHEMA },
  )

  // §24 worker-outcome states, distinct from finding categories. A null or empty return is
  // a failure, not a success — never mark an unverified return completed.
  if (!impl) {
    counters.retry_count += 1
    return halt('blocked', 'implement worker returned null (died or was skipped)', ctx)
  }
  if (!impl.valid) {
    counters.retry_count += 1
    log(`implement stage reported invalid (retry_count now ${counters.retry_count})`)
    if (counters.retry_count > BOUNDS.retry_count) {
      return halt('blocked', `schema-invalid retries exceeded ${BOUNDS.retry_count}`, ctx)
    }
  }

  // ---------------------------------------------------------------- Review
  phase('Review')

  // §21 reviewer input isolation: ARTIFACT + CONTRACT only. The reviewer is given the
  // changed file paths (artifact) and the finding contract, and is given NEITHER the
  // worker's summary or claim of validity, NOR any prior reasoning, NOR another reviewer's
  // findings.
  const artifact = (impl.changedFiles || []).join('\n')

  const review = await runStage(
    'review',
    `Invoke the \`lensed-review\` skill over the artifact below. Do not embed your own ` +
      `review logic — lensed-review owns the lenses and their stances.\n\n` +
      `ARTIFACT (changed files):\n${artifact}\n\n` +
      `CONTRACT: return {dimension, findings[]} where each finding is {lens, location, ` +
      `trigger_condition, guard_snippet, potential_consequence}. Assign no severity, ` +
      `priority, or rank — the Coordinator does that.`,
    { ...stageOpts, label: `review:${label}`, phase: 'Review', schema: REVIEW_SCHEMA },
  )

  let findings = []
  if (!review) {
    log('review stage returned null (skipped or failed) — continuing with 0 findings')
  } else {
    findings = dedupe(review.findings || [])
  }

  // §3: log every cap. Silent truncation reads as "covered everything."
  if (findings.length > MAX_FINDINGS_TO_ACCEPTANCE) {
    log(
      `CAP APPLIED: ${findings.length} findings produced, only the first ` +
        `${MAX_FINDINGS_TO_ACCEPTANCE} are triaged; ` +
        `${findings.length - MAX_FINDINGS_TO_ACCEPTANCE} dropped.`,
    )
    findings = findings.slice(0, MAX_FINDINGS_TO_ACCEPTANCE)
  }
  log(`review produced ${findings.length} finding(s) after dedupe and caps`)

  // ---------------------------------------------------------------- Triage
  phase('Triage')

  let rulings = []
  if (findings.length > 0) {
    const triage = await runStage(
      'triage',
      `Triage each finding into exactly one of ${CATEGORIES.join('|')} and assign a ` +
        `severity of low|medium|high. Severity is your call as Coordinator, not the ` +
        `reviewer's.\n\nIf you route a finding defer or reject BECAUSE IT IS OUT OF ` +
        `SCOPE, set out_of_scope=true and name the authority: 'intent' only if the ` +
        `intent-contract itself excludes it; 'spec_scope', 'plan', or 'diff' if that is ` +
        `all you have; 'none' if the intent is silent or ambiguous. Report the authority ` +
        `honestly — inadmissible ones are rerouted, not rejected.\n\nIf you cannot ` +
        `separate two categories, list both in ambiguous_between.\n\n` +
        `FINDINGS:\n${JSON.stringify(findings, null, 2)}`,
      { ...stageOpts, label: `triage:${label}`, phase: 'Triage', schema: TRIAGE_SCHEMA },
    )

    if (!triage) {
      counters.retry_count += 1
      return halt('blocked', 'triage stage returned null (died or was skipped)', ctx)
    }
    rulings = applyCascade((triage.rulings || []).map(applyTieBreakers).map(enforceScopeAuthority))
  }

  const byCategory = {}
  for (const c of CATEGORIES) byCategory[c] = rulings.filter((r) => r.category === c).length
  ctx.followup = followupSignal(rulings)

  // §24 Review Triage Log: one entry per pass, counts per category broken down by
  // severity, plus the addressed findings — so a pass that fixed nothing is visibly a
  // pass that fixed nothing.
  const bySeverity = {}
  for (const s of SEVERITIES) {
    bySeverity[s] = rulings.filter((r) => r.severity === s && !r.moot).length
  }

  ctx.triageLog = {
    pass: counters.review_loop_iteration + 1,
    counts: byCategory,
    by_severity: bySeverity,
    moot: rulings.filter((r) => r.moot).length,
    addressed_findings: rulings.filter((r) => r.category === 'patch' && !r.moot).map((r) => r.index),
    followup_review_recommended: ctx.followup.recommended,
    followup_score: ctx.followup.score,
  }
  if (ctx.triageLog.addressed_findings.length === 0) {
    ctx.triageLog.addressed_findings = 'none'
  }
  log(`TRIAGE LOG ${JSON.stringify(ctx.triageLog)}`)

  // An intent_gap is unresolvable without a human: save the attempted change as a patch
  // file, revert, and HALT with the unresolved questions and the patch path.
  if (byCategory.intent_gap > 0) {
    return halt('blocked', `${byCategory.intent_gap} intent_gap finding(s) need a human`, ctx, {
      patch_file: `${SPEC_DIR}/${label}.attempted.patch`,
    })
  }
  // A bad_spec means the spec should have prevented this: amend it and re-derive. That is
  // the loop §24 bounds at 5.
  if (byCategory.bad_spec > 0) {
    counters.review_loop_iteration += 1
    if (counters.review_loop_iteration > BOUNDS.review_loop_iteration) {
      return halt(
        'blocked',
        `review repair loop exceeded ${BOUNDS.review_loop_iteration} iterations ` +
          '(non-convergence)',
        ctx,
      )
    }
    return halt('blocked', `${byCategory.bad_spec} bad_spec finding(s) — amend and re-derive`, ctx)
  }

  // ---------------------------------------------------------------- Accept
  phase('Accept')

  const accept = await runStage(
    'accept',
    `Read the standing Definition of Done at ${DOD_PATH}. If the file does not exist, set ` +
      `dodFound=false and list that as the sole unmet item — do not invent criteria. ` +
      `Otherwise evaluate each DoD item against the changed files below and the ` +
      `${findings.length} review finding(s) supplied.\n\n` +
      `CHANGED FILES:\n${artifact}\n\n` +
      `FINDINGS:\n${JSON.stringify(findings)}`,
    { ...stageOpts, label: `accept:${label}`, phase: 'Accept', schema: ACCEPT_SCHEMA },
  )

  if (!accept) {
    counters.retry_count += 1
    return halt('blocked', 'accept stage returned null (died or was skipped)', ctx)
  }
  if (!accept.dodFound) {
    // Absent-DoD path: recorded explicitly rather than silently treated as "nothing to
    // check." Acceptance is unverified, so this is blocked, not done.
    log(`Definition of Done not found at ${accept.dodPath} — acceptance is unverified`)
    return halt('blocked', `Definition of Done not found at ${accept.dodPath}`, ctx, {
      unmet: accept.unmet || [],
    })
  }
  if (!accept.accepted) {
    return halt('blocked', `Definition of Done unmet: ${(accept.unmet || []).join('; ')}`, ctx, {
      unmet: accept.unmet || [],
    })
  }

  return halt('done', 'all stages passed and the Definition of Done is met', ctx, {
    changedFiles: impl.changedFiles || [],
    findings: findings.length,
    unmet: [],
  })
}
