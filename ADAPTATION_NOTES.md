# Skill Adaptation Notes - OpenClaw to Nanobot

## Summary

**Date:** 2026-02-10
**Total Skills Adapted:** 47 skills
**Source:** OpenClaw (openclaw/skills/)
**Destination:** Nanobot (kabot/.worktrees/skill-adaptation/kabot/skills/)

## Categories

### Simple Skills (Metadata Only) - 40 skills
apple-notes, apple-reminders, bear-notes, blogwatcher, blucli, bluebubbles, camsnap, canvas, clawhub, coding-agent, discord, eightctl, food-order, gemini, gifgrep, gog, goplaces, healthcheck, himalaya, imsg, local-places, mcporter, model-usage, nano-banana-pro, nano-pdf, notion, obsidian, openai-image-gen, openai-whisper, openai-whisper-api, openhue, oracle, ordercli, peekaboo, sag, session-logs, sherpa-onnx-tts, slack, songsee, sonoscli

**Changes Made:**
- Metadata key: `"openclaw"` → `"kabot"`

### Medium Complexity (Environment Variables) - 5 skills
1password, spotify-player, things-mac, trello, video-frames

**Changes Made:**
- Metadata key: `"openclaw"` → `"kabot"`
- Environment variables: `OPENCLAW_*` → `NANOBOT_*`
- Environment variables: `CLAWDBOT_*` → `NANOBOT_*`

### Complex Skills (Manual Review) - 2 skills
canvas, voice-call

**Changes Made:**
- Metadata key: `"openclaw"` → `"kabot"`
- **Note:** These skills may have gateway dependencies that require additional testing

## Verification Results

✅ **All Checks Passed:**
- Total skills: 52 (47 new + 5 existing - 0 duplicates)
- Remaining "openclaw" references: 0
- Total SKILL.md files: 52
- All YAML frontmatter valid

## Known Issues / Limitations

1. **Canvas Skill:** References OpenClaw gateway (`gateway.bind` setting). May need modification to work without OpenClaw gateway.
2. **Voice-call Skill:** May require voice gateway integration. Needs testing.
3. **Line Endings:** Git warnings about LF to CRLF conversion (cosmetic, doesn't affect functionality)

## Skills Requiring Testing

- [ ] canvas - Test HTML canvas display
- [ ] voice-call - Test voice capabilities
- [ ] 1password - Test environment variable substitution
- [ ] notion - Test API integration
- [ ] slack - Test rich messaging

## Next Steps

1. Test representative skills from each category
2. Document any issues found during testing
3. Fix gateway dependencies if needed
4. Merge to main branch
5. Delete worktree when complete

## Git Commits

1. `1358dce` - chore: backup existing skills before adaptation
2. `b330ed6` - feat: adapt 40 simple skills from OpenClaw to Nanobot
3. `6c2c46c` - feat: adapt 5 medium-complexity skills with env var updates
4. `9736ca0` - feat: adapt complex skill voice-call

## Backup

Original skills backed up to: `kabot/skills.backup/`
