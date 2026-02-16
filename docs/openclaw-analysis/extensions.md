# Plugin & Extension System

OpenClaw features a robust plugin system located in `src/plugins`, designed to extend functionality without modifying the core codebase.

## Core Components

### Registry (`src/plugins/registry.ts`)
The central store for all loaded plugins. It manages the lifecycle and state of plugins.

### Loader (`src/plugins/loader.ts`)
Responsible for discovering and loading plugins from disk. It supports:
-   **NPM Packages**: Plugins installed in `node_modules`.
-   **Local Paths**: Plugins loaded from specific directories.

### Manifest (`src/plugins/manifest.ts`)
Each plugin must have a `manifest.json` or equivalent metadata defining:
-   `id`: Unique identifier.
-   `name`: Human-readable name.
-   `version`: Semantic version.
-   `permissions`: Requested permissions (e.g., specific scopes).

## Hooks (`src/plugins/hooks.ts`)
Plugins interact with the core system primarily through hooks.
-   `message_received`: Triggered when a message arrives.
-   `tool_call`: Intercepts or augments tool execution.
-   `reply_generated`: Post-processing of generated replies.

## Configuration
Plugins are configured via the main `config.json` under the `plugins` key.
```json
"plugins": {
  "enabled": true,
  "entries": {
    "my-plugin": {
      "enabled": true,
      "config": { "apiKey": "..." }
    }
  }
}
```
