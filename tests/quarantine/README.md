# Quarantine Tests

Folder ini untuk file test/manual check yang:
- belum stabil,
- environment-dependent,
- atau tidak dipakai di CI utama.

Tujuan:
- struktur repo lebih rapi,
- test utama tetap bersih dan konsisten.

Catatan:
- `pytest` utama diatur untuk mengabaikan `tests/quarantine`.
- Jalankan manual bila perlu:
  - `python tests/quarantine/manual_scripts/_test_openai.py`
  - `python tests/quarantine/manual_scripts/_debug_router.py`

Subfolder:
- `manual_scripts/`: skrip validasi manual/non-pytest.
- `failing/`: test pytest yang sedang tidak stabil di environment saat ini.
