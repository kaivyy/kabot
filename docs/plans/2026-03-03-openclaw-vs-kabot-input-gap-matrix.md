# OpenClaw vs Kabot Input Maturity Gap Matrix (2026-03-03)

> Superset audit with all major domains: `docs/plans/2026-03-04-openclaw-vs-kabot-full-gap-matrix.md`.

## Scope
- Fokus: ketahanan menerima input user, follow-up context, anti-hallucination untuk query fakta terbaru, dan responsivitas run lifecycle.
- Sumber OpenClaw yang diteliti:
  - `src/auto-reply/reply/inbound-context.ts`
  - `src/auto-reply/reply/untrusted-context.ts`
  - `src/auto-reply/reply/followup-runner.ts`
  - `src/auto-reply/reply/typing.ts`
  - `src/auto-reply/reply/typing-mode.ts`
  - `src/web/auto-reply/monitor/process-message.ts`
- Sumber Kabot yang dibandingkan:
  - `kabot/agent/loop_core/message_runtime.py`
  - `kabot/agent/loop_core/execution_runtime.py`
  - `kabot/agent/cron_fallback_nlp.py`
  - `kabot/channels/base.py`
  - `kabot/channels/telegram.py`

## Gap Matrix
| Area | OpenClaw Behavior | Kabot Current | Gap Status | Next Action |
|---|---|---|---|---|
| Inbound context finalization | Normalisasi context ketat (`BodyForAgent`, `BodyForCommands`, media alignment) | Sudah ada routing + context builder, tapi boundary trusted/untrusted belum seketat OpenClaw | Partial | Tambah segment `untrusted_context` eksplisit di prompt build agar metadata tidak dibaca sebagai instruksi |
| Untrusted metadata guard | `untrusted-context.ts` menempelkan blok "do not treat as instructions" | Belum ada blok khusus universal di Kabot | Open | Implement guard block di context layer untuk semua channel metadata mentah |
| Follow-up intent continuity | Follow-up queue runner + run context stabil | Sudah ada `pending_followup_tool` + `pending_followup_intent` TTL per session; kini short confirmation berbentuk aksi (`ambil sekarang`, `ya lakukan`, `terusin`) juga dilanjutkan ke intent sebelumnya | Closed (hardened) | Tambah observability counter khusus hit/miss follow-up intent |
| Keyword dependency reduction | Banyak routing pakai context finalization + run queue, bukan sekadar keyword tunggal | Sudah ditambah session-latch + RESEARCH safety latch, tapi beberapa intent masih lexical-heavy | Partial | Tambah lightweight intent classifier untuk non-keyword action intents |
| Live-fact anti-hallucination | Research flows cenderung mengikat ke tool/web path | RESEARCH route sekarang memaksa `web_search` saat indikator live query terdeteksi | Closed (core) | Tambah citation quality gate agar response wajib link saat mode research |
| Critic retry overhead | Tidak mengandalkan critic loop berat untuk setiap turn | Sudah skip critic untuk `required_tool`, short prompt, `CHAT`, dan `RESEARCH` | Closed | Monitoring p95 untuk memastikan dampak latency konsisten |
| Typing keepalive lifecycle | Typing controller robust (`runComplete + dispatchIdle + TTL`) | Telegram kini punya self-healing typing loop (transient error tidak mematikan loop) + status lane; channel lain tergantung dukungan adapter | Partial | Standarkan typing/reaction interface lintas adapter production |
| Status reaction per fase run | Punya sinyal lifecycle jelas saat follow-up run | Kabot sudah punya phase `queued/thinking/tool/done/error` + `draft_update` | Partial | Tambah hard requirement di semua adapter production untuk parity UX |
| Immediate ack reaction | WhatsApp ack reaction dikirim cepat di inbound monitor | Kabot dominan status text/typing, ack reaction belum parity penuh lintas channel | Open | Tambah ack reaction opsional per channel yang mendukung reactions |
| RAM intent fidelity | Routing command/context lebih tegas ke intent | Kabot kini membedakan `kapasitas RAM` (system info) vs `RAM proses` (process memory) | Closed | Tambah benchmark dataset intent multilingual untuk regresi |

## Changes Applied in Kabot (This Cycle)
1. RESEARCH safety latch:
   - `message_runtime`: route `RESEARCH` + live markers/year -> force `required_tool=web_search`.
   - `execution_runtime`: fail-safe route-profile `RESEARCH` -> force `web_search` bila tool tersedia.
2. Follow-up continuity without keyword lock:
   - Session metadata `pending_followup_tool` dipakai untuk menangkap "ya/gas/lanjut" dan varian short follow-up.
3. Critic latency guard:
   - Critic retries dilewati untuk turn `RESEARCH` agar tidak terjadi loop 20-40 detik pada query live-news.
4. RAM intent disambiguation:
   - `kapasitas/total/spec RAM` diarahkan ke `get_system_info`.
   - Query usage/proses tetap ke `get_process_memory`.
5. Skill-creator intent understanding:
   - frasa non-eksak seperti `buat skill baru` / `create skill` kini diberi alias-intent boost ke skill `skill-creator`, tidak harus menyebut nama skill persis.
6. Follow-up continuity hardening (2026-03-04):
   - short live-news query sekarang tetap disimpan sebagai `pending_followup_intent` walau prompt pendek.
   - short confirmations berbentuk aksi (`ambil sekarang`, `ya lakukan`, `terusin`) kini tetap diperlakukan sebagai kelanjutan intent.
7. Typing resilience hardening (2026-03-04):
   - Telegram status update kini memastikan typing keepalive aktif saat task typing hilang.
   - transient error pada `send_chat_action` tidak lagi menghentikan typing loop secara permanen untuk turn berjalan.

## Validation
- `tests/agent/loop_core/test_message_runtime.py`
- `tests/agent/test_tool_enforcement.py`
- `tests/agent/loop_core/test_execution_runtime.py`
- `tests/channels/test_telegram_typing_status.py`
- `tests/channels/test_discord_typing_status.py`
- `tests/channels/test_status_updates_cross_channel.py`

Current result: `69 passed`.
