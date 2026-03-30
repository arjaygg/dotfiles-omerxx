#!/usr/bin/env bun

import type { PlanFileInfo, ValidationResult, PlanNamingConfig } from './types';

// Configuration
const config = {
  datePattern: /^\d{4}-\d{2}-\d{2}-.+\.md$/,
  randomPattern: /^[a-z]+-[a-z]+-[a-z]+\.md$/i,
  systemFiles: ['active-context', 'decisions', 'progress', 'session-handoff'],
  enforceMode: 'block' as const // 'warn' | 'block'
};

function getCurrentDate(): string {
  return new Date().toISOString().split('T')[0];
}

function analyzePlanFile(filePath: string): PlanFileInfo {
  const filename = filePath.split('/').pop() || '';
  const isInPlansDir = filePath.includes('/plans/') || filePath.startsWith('plans/');
  const isMarkdown = filePath.endsWith('.md');
  
  return {
    path: filePath,
    filename,
    isInPlansDir,
    isMarkdown,
    isPlanFile: isInPlansDir && isMarkdown
  };
}

function validatePlanNaming(filename: string): ValidationResult {
  // Already follows convention
  if (config.datePattern.test(filename)) {
    return { valid: true };
  }

  // System files are allowed
  if (config.systemFiles.some(sf => filename.startsWith(sf))) {
    return { valid: true };
  }

  const today = getCurrentDate();

  // Random generated name that needs fixing
  if (config.randomPattern.test(filename)) {
    return {
      valid: false,
      suggestion: `${today}-your-task-description.md`,
      message: `File "${filename}" doesn't follow naming convention.\nExpected format: YYYY-MM-DD-context.md`
    };
  }

  // Other non-conforming names
  return {
    valid: false,
    suggestion: `${today}-refactor-auth-flow.md`,
    message: `Plan file "${filename}" should follow YYYY-MM-DD-context.md format.`
  };
}

// Main hook logic
try {
  const input = await Bun.stdin.json();
  
  // Only process PreToolUse events for Write operations
  if (input.hook_type !== 'PreToolUse' || input.tool_name !== 'Write') {
    console.log('{}');
    process.exit(0);
  }

  const filePath = input.tool_input?.path as string;
  if (!filePath) {
    console.log('{}');
    process.exit(0);
  }

  const fileInfo = analyzePlanFile(filePath);
  if (!fileInfo.isPlanFile) {
    console.log('{}');
    process.exit(0);
  }

  const validation = validatePlanNaming(fileInfo.filename);

  if (!validation.valid) {
    console.error(`[PLAN NAMING] ${validation.message}`);
    
    if (validation.suggestion) {
      console.error(`Suggestion: ${validation.suggestion}`);
    }
    console.error('Please rename the file to follow the convention in CLAUDE.md');
    
    // Enforce based on configuration
    if (config.enforceMode === 'block') {
      console.log(JSON.stringify({
        decision: 'block',
        reason: `Plan naming violation: ${validation.message}`
      }));
      process.exit(2); // Block the operation
    }
  }

  // Allow the operation
  console.log('{}');
  process.exit(0);

} catch (error) {
  console.error(`Hook error: ${error}`);
  console.log('{}'); // Allow operation on error
  process.exit(0);
}