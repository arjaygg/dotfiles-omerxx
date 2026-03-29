#!/usr/bin/env node
// PreToolUse hook: Enforce plan file naming convention
// Runs before Write operations to ensure plan files follow YYYY-MM-DD-context.md format

import fs from 'fs';
import path from 'path';
import os from 'os';

const input = JSON.parse(fs.readFileSync('/dev/stdin', 'utf8'));
const { tool_name, parameters } = input;

// Only process Write operations targeting plan files
if (tool_name !== 'Write') process.exit(0);

const filePath = parameters?.path;
if (!filePath) process.exit(0);

// Check if this is a plan file (in plans/ directory and .md extension)
const isInPlansDir = filePath.includes('/plans/') || filePath.startsWith('plans/');
const isMdFile = filePath.endsWith('.md');

if (!isInPlansDir || !isMdFile) process.exit(0);

// Extract filename from path
const filename = path.basename(filePath);

// Check if filename follows YYYY-MM-DD-context.md pattern
const datePattern = /^\d{4}-\d{2}-\d{2}-.+\.md$/;

if (datePattern.test(filename)) {
    // Already follows convention, allow it
    process.exit(0);
}

// Check if it's a random generated name that needs fixing
const randomPattern = /^[a-z]+-[a-z]+-[a-z]+\.md$/i;
if (randomPattern.test(filename)) {
    // Generate suggested name based on current date
    const today = new Date().toISOString().split('T')[0]; // YYYY-MM-DD format
    
    console.error(`[PLAN NAMING] File "${filename}" doesn't follow naming convention.`);
    console.error(`Expected format: YYYY-MM-DD-context.md`);
    console.error(`Suggestion: ${today}-your-task-description.md`);
    console.error(`Please rename the file to follow the convention in CLAUDE.md`);
    
    // Don't block the operation, just warn
    process.exit(0);
}

// For other non-conforming names, provide guidance
if (!filename.startsWith('active-context') && 
    !filename.startsWith('decisions') && 
    !filename.startsWith('progress') &&
    !filename.startsWith('session-handoff')) {
    
    const today = new Date().toISOString().split('T')[0];
    console.error(`[PLAN NAMING] Plan file "${filename}" should follow YYYY-MM-DD-context.md format.`);
    console.error(`Example: ${today}-refactor-auth-flow.md`);
}

process.exit(0);