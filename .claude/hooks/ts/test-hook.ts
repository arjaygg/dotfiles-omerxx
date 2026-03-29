#!/usr/bin/env bun

console.error("Starting hook...");

const input = await Bun.stdin.json();
console.error(`Received input: ${JSON.stringify(input)}`);

if (input.tool_name === 'Write' && input.tool_input?.path?.includes('plans/')) {
  const filename = input.tool_input.path.split('/').pop();
  console.error(`[PLAN NAMING] Checking file: ${filename}`);
  
  if (filename?.match(/^[a-z]+-[a-z]+-[a-z]+\.md$/)) {
    console.error(`[PLAN NAMING] File "${filename}" doesn't follow naming convention.`);
    console.error('Expected format: YYYY-MM-DD-context.md');
  }
}

console.log('{}'); // Return empty success response