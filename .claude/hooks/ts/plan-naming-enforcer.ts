#!/usr/bin/env bun

import { runHook, type HookHandlers } from 'claude-code-ts-hooks';
import { analyzePlanFile, validatePlanNaming, DEFAULT_CONFIG } from './utils';
import type { PlanNamingConfig } from './types';

// Configuration - can be customized per environment
const config: PlanNamingConfig = {
  ...DEFAULT_CONFIG,
  enforceMode: 'warn' // Change to 'block' for strict enforcement
};

const handlers: HookHandlers = {
  preToolUse: async (payload) => {
    console.error(`HOOK CALLED: tool_name=${payload.tool_name}`);
    
    // Only process Write operations
    if (payload.tool_name !== 'Write') {
      return { decision: 'approve' };
    }

    // Extract file path from tool parameters
    const filePath = payload.tool_input?.path as string;
    if (!filePath) {
      return { decision: 'approve' };
    }

    const fileInfo = analyzePlanFile(filePath);
    console.error(`DEBUG: filePath=${filePath}, isPlanFile=${fileInfo.isPlanFile}, filename=${fileInfo.filename}`);
    
    if (!fileInfo.isPlanFile) {
      return { decision: 'approve' };
    }

    const validation = validatePlanNaming(fileInfo.filename, config);
    console.error(`DEBUG: validation.valid=${validation.valid}`);

    if (!validation.valid) {
      const errorMsg = `[PLAN NAMING] ${validation.message}`;
      console.error(errorMsg);
      
      if (validation.suggestion) {
        console.error(`Suggestion: ${validation.suggestion}`);
      }
      console.error('Please rename the file to follow the convention in CLAUDE.md');
      
      // Enforce based on configuration
      if (config.enforceMode === 'block') {
        return { 
          decision: 'block', 
          reason: `Plan naming violation: ${validation.message}` 
        };
      }
    }

    return { decision: 'approve' };
  }
};

// Run the hook
runHook(handlers);