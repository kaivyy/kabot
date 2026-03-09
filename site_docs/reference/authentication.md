# Authentication Reference

Kabot supports multiple authentication styles depending on provider.

## Common Modes

- API key
- OAuth
- device-style flow for some providers
- provider-specific methods such as setup tokens or subscription codes

## Practical Commands

```bash
kabot auth status
kabot auth login openai
kabot auth login google --method oauth
```

## Important Advice

- use one provider first
- verify it works before adding more
- prefer the native supported auth path before adding skill-based alternatives
- treat expired tokens as runtime issues to diagnose, not mysterious AI failures

## Related Guide

See the main [Configuration guide](../guide/configuration.md) and [Google Suite guide](../guide/google-suite.md).
