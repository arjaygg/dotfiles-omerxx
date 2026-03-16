---
name: youtube-title
description: Generate high-performing YouTube video titles optimized for click-through rate (CTR). Creates curiosity-driven titles that complement thumbnails and compel viewers to click.
---

# YouTube Title Generator

This skill enables generation of high-performing YouTube video titles optimized for click-through rate (CTR). Titles are designed to spark curiosity, complement thumbnails, and compel viewers to click.

## When to Use This Skill

Use this skill when:

- The user asks to create a title for a YouTube video
- The user requests title ideas or brainstorming for video content
- The user wants to improve or optimize an existing video title
- Working on YouTube content creation and a title is needed
- The user asks for multiple title variations to test
- Researching and ideating a new YouTube video idea

## Core Principles (MANDATORY)

1. **Curiosity is Mandatory**: Every title MUST prompt a specific question in the viewer's mind
2. **Complement, Don't Duplicate**: Title must work WITH the thumbnail, not repeat it
3. **No Generic Descriptions**: Titles that merely describe content are rejected
4. **Question Over Answer**: Raise questions, don't answer them in the title

## Prerequisites - Gather Context

Before generating titles, gather the following information:

### Required Information
- **Video topic/content**: What is the video about?
- **Target audience**: Who is this video for?
- **Key message**: What's the main takeaway or hook?

### Highly Recommended Information
- **Thumbnail description or image**: What does the thumbnail show? What text is on it?
- **Target emotion**: What emotion should the title evoke? (curiosity, shock, excitement, etc.)
- **Content type**: Educational, entertainment, vlog, tutorial, etc.

## Title Generation Workflow

### Step 1: Gather Context

Ask the user for required information if not already provided:

```text
To create an optimized title, I need to understand:
1. What is the video about? (topic/content)
2. Who is your target audience?
3. What's the main hook or takeaway?
4. Do you have a thumbnail? If so, what does it show and what text is on it?
5. What emotion should the title evoke?
```

### Step 2: Identify the Question

Before writing any title, identify the specific question you want in the viewer's mind:

- What question will make them curious enough to click?
- Does this question align with the video content?
- Is the curiosity gap strong enough to drive action?

**Examples of good questions to prompt:**
- "What mistakes am I making?" -> "Big Mistakes Small YouTube Creators Still Make!"
- "What happened?" -> "I Should Have Seen This Coming..."
- "Why would someone do that?" -> "the GRILLED CHEESE I ate every other day for 2 years"
- "Did they accept?" -> "Offering People $100,000 To Quit Their Job"

### Step 3: Generate Title Options

Generate 3-5 title variations that:

1. Prompt the identified question
2. Complement (not duplicate) the thumbnail
3. Align with the target emotion
4. Follow content type best practices (educational vs entertainment)

**For each title, verify against the checklist:**
- [ ] **Curiosity Test**: Does this prompt a specific question?
- [ ] **Complementarity Test**: Does this work WITH the thumbnail (not duplicate it)?
- [ ] **Click Compulsion Test**: Is the curiosity gap strong enough?
- [ ] **Non-Descriptive Test**: Does this go beyond merely describing?
- [ ] **Target Audience Test**: Will this resonate with the demographic?

### Step 4: Present and Refine

Present the title options to the user with:

1. The title itself
2. The question it prompts in the viewer's mind
3. How it complements the thumbnail (if applicable)
4. Why it should drive clicks

Example presentation:

```text
Here are 3 optimized title options:

1. "The AI Agent Mistake That Cost Me 10 Hours"
   - Prompts: "What mistake? How can I avoid it?"
   - Complements thumbnail showing frustrated face + error message
   - Creates urgency through time cost

2. "I Built This AI Agent Wrong (Here's What I Learned)"
   - Prompts: "What did they do wrong? What's the lesson?"
   - Personal experience framing creates relatability
   - Implies valuable learning without giving it away

3. "Why Your AI Agents Keep Breaking (And Mine Don't)"
   - Prompts: "Why do mine break? What's their secret?"
   - Creates contrast and curiosity
   - Positions viewer problem + solution tease
```

### Step 5: Iterate Based on Feedback

If the user requests changes:
1. Understand what aspect needs adjustment (curiosity, tone, length, etc.)
2. Regenerate while maintaining design requirements compliance
3. Re-verify against the checklist

## Common Patterns by Content Type

### Educational Content (How-to, Tutorials)

**Goal**: Frame instruction to spark curiosity, not just inform

- "The Secret Technique Pro Chefs Don't Want You to Know"
- "I Tried the 'Impossible' Coding Challenge"
- "Why Everyone Does [X] Wrong (And How to Fix It)"

**AVOID:**
- "How to Chop Onions Properly"
- "Python Tutorial for Beginners"

### Entertainment Content (Vlogs, Gaming)

**Goal**: Create intrigue through outcome uncertainty

- "Offering People $100,000 To Quit Their Job"
- "I Ate the Same Meal for 30 Days Straight"
- "They Didn't Believe Me Until..."

**AVOID:**
- "My Daily Vlog"
- "Playing Minecraft"

### Tech/AI Content

**Goal**: Combine education with curiosity and problem-solving

- "The AI Agent Pattern Nobody Talks About"
- "I Broke Production With This One Line of Code"
- "Why Your AI Agents Fail (And How to Fix Them)"

**AVOID:**
- "Building AI Agents Tutorial"
- "How to Use Claude API"

## Quality Assurance

### Priority Order

1. **Spark curiosity** (highest priority)
2. **Complement thumbnail**
3. **Raise viewer question**
4. **Create click compulsion**

### Rejection Criteria

**REJECT and regenerate if the title:**
- Merely describes the content without sparking curiosity
- Duplicates text that appears on the thumbnail
- Answers the question instead of raising it
- Uses generic patterns like "[Topic] Tutorial" without intrigue
- Fails the "What question does this raise?" test

### Success Criteria

**A successful title:**
- Prompts a specific, compelling question in the viewer's mind
- Works synergistically with the thumbnail
- Creates a curiosity gap strong enough to drive clicks
- Aligns with the target audience and content type
- Passes all 5 checklist items

## Notes

- **Curiosity is non-negotiable**: Description alone is insufficient
- **Always verify against checklist**: Every title must pass all 5 tests
- **Thumbnail coordination**: When possible, coordinate title with thumbnail design
- **Test multiple options**: Provide 3-5 variations for A/B testing consideration
- **Iterate ruthlessly**: Reject titles that don't meet standards, even if they're accurate
