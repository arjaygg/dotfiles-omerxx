import type { PlanFileInfo, ValidationResult, PlanNamingConfig } from './types';

export const DEFAULT_CONFIG: PlanNamingConfig = {
  datePattern: /^\d{4}-\d{2}-\d{2}-.+\.md$/,
  randomPattern: /^[a-z]+-[a-z]+-[a-z]+\.md$/i,
  systemFiles: ['active-context', 'decisions', 'progress', 'session-handoff'],
  enforceMode: 'warn' // Change to 'block' for strict enforcement
};

export function getCurrentDate(): string {
  return new Date().toISOString().split('T')[0]; // YYYY-MM-DD format
}

export function analyzePlanFile(filePath: string): PlanFileInfo {
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

export function validatePlanNaming(
  filename: string, 
  config: PlanNamingConfig = DEFAULT_CONFIG
): ValidationResult {
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