# Security Guide

Kabot can execute tools, hold credentials, and expose gateway surfaces, so security choices matter.

## First Principles

- never commit secrets
- prefer least privilege
- treat `allowFrom` and auth tokens as mandatory in real deployments
- avoid running Kabot as a highly privileged system user

## API Keys And Tokens

Recommendations:
- keep credentials local
- rotate sensitive keys regularly
- use dedicated keys per environment where possible
- do not paste secrets into source-controlled files

## Gateway Security

For any non-trivial deployment:
- enable gateway auth token
- use scoped tokens instead of broad all-access tokens
- expose the dashboard carefully
- prefer safer network surfaces such as Tailscale or a controlled reverse proxy

## Channel Security

Always think about who can send messages to your bot.

Use:
- `allowFrom`
- DM/group policy controls where applicable
- explicit review of who is permitted

## Tool Execution Security

Kabot can execute commands and work with files. That is powerful and requires operational judgment.

Recommended habits:
- review what tools are enabled
- use safer execution policies where possible
- avoid unnecessary write/destructive permissions
- run Kabot under a user account appropriate for its job

## Production Checklist

- auth token enabled
- scoped gateway access configured
- `allowFrom` configured
- logs monitored
- updates applied
- provider usage limits set
- backup plan for config and workspace

## Security Reporting

If you discover a vulnerability, report it privately rather than opening a public exploit issue.
