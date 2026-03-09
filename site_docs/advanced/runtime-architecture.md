# Runtime Architecture

Kabot is built as a layered runtime rather than a single chat loop.

## Key Layers

### CLI and Gateway Surfaces
The outer layer exposes Kabot through:
- CLI commands
- gateway routes
- dashboard/operator surfaces
- channel adapters

### Agent Runtime
The agent runtime is responsible for:
- prompt and context assembly
- skill matching and workflow steering
- routing and semantic intent handling
- tool selection or suppression
- model fallback behavior

### Tool and Execution Runtime
This layer handles:
- direct-tool fast paths
- simple no-tool responses
- guarded execution loops
- tool result handling
- provider/model retry logic

### Memory Layer
The memory system can use lightweight or hybrid strategies and now includes lazy probe behavior to keep cold-start costs down for one-shot runs.

## Important Design Themes

### AI-Driven, Not Template-Driven
Kabot tries to keep the assistant natural instead of turning every prompt into a hardcoded command parser.

Where deterministic behavior is necessary, it is generally used narrowly for:
- direct file/path actions
- tiny temporal replies
- safety or operator-critical routing

### Direct Paths For High-Confidence Cases
Recent runtime work introduced faster direct paths for:
- tiny temporal prompts
- deterministic filesystem listings
- safe direct-tool actions

This helps latency without forcing the whole product into a rigid rule engine.

### Refactor-For-Stability Approach
Major runtime files were split into smaller package parts so behavior stayed intact while maintainability improved. That matters because Kabot is now large enough that runtime clarity directly affects correctness.

## Why This Matters Operationally

When Kabot feels fast, natural, and stable, it is usually because these layers are doing the right thing together:
- context stays small enough
- routing avoids unnecessary LLM hops
- deterministic paths are used only where confidence is high
- tool and model retries stay observable and bounded
