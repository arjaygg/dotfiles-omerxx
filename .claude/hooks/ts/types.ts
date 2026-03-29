// Custom types for your hook ecosystem

export interface PlanNamingConfig {
  datePattern: RegExp;
  randomPattern: RegExp;
  systemFiles: string[];
  enforceMode: 'warn' | 'block';
}

export interface ValidationResult {
  valid: boolean;
  suggestion?: string;
  message?: string;
}

export interface HookContext {
  sessionId: string;
  cwd: string;
  transcriptPath: string;
}

export interface PlanFileInfo {
  path: string;
  filename: string;
  isInPlansDir: boolean;
  isMarkdown: boolean;
  isPlanFile: boolean;
}