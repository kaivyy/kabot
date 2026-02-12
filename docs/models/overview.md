# AI Model Management in Kabot

Kabot v2.0 features a sophisticated model management system inspired by OpenClaw, supporting 25+ providers and hundreds of models with rich metadata and dynamic discovery.

## 🚀 Key Features

- **Smart Resolver**: Use aliases (`sonnet`), short names (`gpt-4o`), or full IDs (`openai/gpt-4o`).
- **Hybrid Registry**: Combines a hand-curated **Premium Catalog** with **Dynamic Scanning**.
- **Rich Metadata**: View pricing (USD per 1M tokens), context windows, and model capabilities.
- **SQLite Persistence**: Scanned models are saved to a local database for instant offline access.
- **Semi-Auto Config**: Kabot suggests the best models immediately after you login to a provider.

## 🛠️ CLI Commands

### 1. List Available Models
Show all models registered in your system, including their cost and capabilities.
```bash
kabot models list
```
*Filter by provider:* `kabot models list --provider anthropic`
*Show only premium:* `kabot models list --premium`

### 2. Discover New Models
Scan the APIs of your configured providers to find the latest models.
```bash
kabot models scan
```

### 3. View Detailed Info
Get deep technical details about any model.
```bash
kabot models info sonnet
```

### 4. Set Default Model
Quickly change the primary model used by the agent (supports aliases).
```bash
kabot models set gpt4
```

## 🏷️ Using Aliases

You can use short aliases instead of long IDs in any command:
- `sonnet` -> `anthropic/claude-3-5-sonnet-20240620`
- `gpt4` -> `openai/gpt-4o`
- `kimi` -> `moonshot/kimi-k2.5`
- `gemini` -> `google/gemini-1.5-pro`

## 💰 Pricing & Context
Metadata is provided for premium models automatically. For scanned models, Kabot uses safe defaults. Pricing is displayed as **Input / Output** cost per 1 million tokens.
