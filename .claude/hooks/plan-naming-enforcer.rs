use serde_json::Value;
use std::io::{self, Read};
use regex::Regex;
use chrono::Utc;

fn main() -> io::Result<()> {
    // Read JSON input from stdin
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    
    let json: Value = serde_json::from_str(&input).unwrap_or_default();
    
    // Extract tool name and file path
    let tool_name = json["tool_name"].as_str().unwrap_or("");
    let file_path = json["parameters"]["path"].as_str().unwrap_or("");
    
    // Only process Write operations
    if tool_name != "Write" || file_path.is_empty() {
        return Ok(());
    }
    
    // Check if this is a plan file
    if !file_path.contains("/plans/") && !file_path.starts_with("plans/") {
        return Ok(());
    }
    
    if !file_path.ends_with(".md") {
        return Ok(());
    }
    
    // Extract filename
    let filename = file_path.split('/').last().unwrap_or("");
    
    // Check if filename follows YYYY-MM-DD-context.md pattern
    let date_pattern = Regex::new(r"^\d{4}-\d{2}-\d{2}-.+\.md$").unwrap();
    if date_pattern.is_match(filename) {
        return Ok(()); // Already follows convention
    }
    
    // Check if it's a random generated name
    let random_pattern = Regex::new(r"^[a-z]+-[a-z]+-[a-z]+\.md$").unwrap();
    if random_pattern.is_match(filename) {
        let today = Utc::now().format("%Y-%m-%d");
        eprintln!("[PLAN NAMING] File \"{}\" doesn't follow naming convention.", filename);
        eprintln!("Expected format: YYYY-MM-DD-context.md");
        eprintln!("Suggestion: {}-your-task-description.md", today);
        eprintln!("Please rename the file to follow the convention in CLAUDE.md");
        return Ok(());
    }
    
    // For other non-conforming names
    let system_files = ["active-context", "decisions", "progress", "session-handoff"];
    let is_system_file = system_files.iter().any(|&sf| filename.starts_with(sf));
    
    if !is_system_file {
        let today = Utc::now().format("%Y-%m-%d");
        eprintln!("[PLAN NAMING] Plan file \"{}\" should follow YYYY-MM-DD-context.md format.", filename);
        eprintln!("Example: {}-refactor-auth-flow.md", today);
    }
    
    Ok(())
}

// Cargo.toml would be:
// [package]
// name = "plan-naming-enforcer"
// version = "0.1.0"
// edition = "2021"
//
// [dependencies]
// serde_json = "1.0"
// regex = "1.0"
// chrono = { version = "0.4", features = ["serde"] }