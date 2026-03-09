# Google Suite Guide

Kabot supports a native Google integration path.

## Important Clarification

Kabot's `Google Suite` setup path is native.

It does not require:
- npm
- Node.js
- `gog`

That makes it the recommended path for most users who simply want Google auth and Google actions from Kabot.

## Typical Flow

1. Run `kabot config`.
2. Open `Google Suite`.
3. Provide the required Google credentials path.
4. Complete the consent flow.
5. Save and verify access.

## What It Can Support

Depending on your configured features and flows, Google access can be used for:
- email-related actions
- calendar workflows
- Drive/Docs style operations
- broader Google-backed automation tasks

## Native vs Skill-Based Google Flows

Use native Google Suite when:
- you want the simplest supported auth path
- you do not want extra Node ecosystem dependencies
- you want the built-in Kabot path

Use a skill-based flow only when:
- you need a specialized external tool or workflow that goes beyond the native integration
- you understand that it may have its own dependency and auth model

## Recommendation

For beginners, always start with native Google Suite first.
