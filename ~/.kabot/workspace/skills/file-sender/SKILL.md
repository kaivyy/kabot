---
name: file-sender
description: Capability to send files to the user
---

# File Sender

You have the ability to send local files directly to the user's chat (Telegram/WhatsApp).

## How to use

When a user asks for a file (e.g., "send me that file", "upload the logo"), use the core `message` tool.
The `message` tool has a `files` parameter.

## Examples

### Sending a single file
**User:** "Kirim file logo google yang tadi didownload"
**Tool Call:**
```json
{
  "name": "message",
  "arguments": {
    "content": "Berikut adalah file logo Google yang Anda minta.",
    "files": ["downloads/googlelogo_color_272x92dp.png"]
  }
}
```

### Sending multiple files
**Tool Call:**
```json
{
  "name": "message",
  "arguments": {
    "content": "Ini dokumen-dokumen yang Anda butuhkan.",
    "files": ["docs/report.pdf", "docs/summary.txt"]
  }
}
```

**Note:** Always ensure the file path exists locally before sending.
