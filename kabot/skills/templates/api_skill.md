---
name: api-skill-template
description: Template for creating API integration skills
---

# [API Name] Skill

## Overview
This skill enables Kabot to interact with the [API Name] API.

## Authentication
- API Key: Configure via `kabot auth login [provider]`
- Or set environment variable: `[ENV_VAR_NAME]`

## Available Actions
List the actions this skill provides:
1. **[action_name]** — Description
   - Endpoint: `GET/POST [url]`
   - Parameters: [list]

## Usage Instructions for Agent
When the user asks about [topic], use the `web_fetch` tool:

### Example: [Action Name]
```json
{
  "url": "[api_endpoint]",
  "method": "GET",
  "headers": {"Authorization": "Bearer [API_KEY]"}
}
```

## Response Formatting
After receiving the API response:
- Extract relevant data from the JSON
- Format in a user-friendly way
- Include units, timestamps, etc.
