# Panduan Fitur Baru Kabot: Analogi & Fungsi

Dokumen ini menjelaskan **7 Phase Upgrade** Kabot dengan bahasa manusia dan analogi dunia nyata, supaya Anda paham betul "kenapa kita butuh ini".

---

## 1. Phase 4: OAuth Auto-Refresh (Fix Billing Error)
> **Analogi: "Kartu Member Gym Otomatis Diperpanjang"**

Bayangkan Kabot adalah **Personal Trainer** Anda di Gym (OpenAI).
- **Masalah Sekarang:** Kartu member (Token) Kabot ada masa berlakunya 1 jam. Kalau Anda lagi asik latihan (chatting) dan kartunya habis, Kabot diusir satpam ("Billing Error"). Anda harus manual ke resepsionis buat perpanjang. Ribet!
- **Solusi Upgrade:** Kita kasih Kabot fitur **Auto-Debit**.
- **Hasil:** 5 menit sebelum kartu habis, Kabot otomatis perpanjang sendiri di belakang layar. Anda latihan terus tanpa gangguan seumur hidup.

### Detail Task:
| Task | Fungsi Teknis | Analogi |
|------|---------------|---------|
| **11. Extend AuthProfile** | Tambah kolom `refresh_token` di database. | Dompet khusus buat simpan "kartu sakti" renewal. |
| **12. TokenRefreshService** | Service background yang cek expired time. | Alarm di HP Kabot: "Eh, 5 menit lagi kartu habis, urus dulu ah." |
| **13. Wire Auto-Refresh** | Cek token sebelum request API. | Sebelum ngangkat beban, cek dulu kartunya aktif ga. |
| **14. Error Classification** | Bedain error Auth vs Billing vs Rate Limit. | Tau bedanya "Kartu Expired" (bisa urus sendiri) vs "Saldo Habis" (minta duit ke Bos). |

---

## 2. Phase 1: Cron Tool Upgrade
> **Analogi: "Sekretaris Pribadi yang Disiplin"**

Bayangkan Kabot adalah **Sekretaris** Anda.
- **Masalah Sekarang:** Sekretaris ini cuma ngerti perintah pakai kode komputer (`3600000ms`). Kalau Anda bilang "Ingetin meeting besok", dia bingung. Dia juga suka naruh memo (reminder) sembarangan di meja orang lain (Console).
- **Solusi Upgrade:** Kita sekolahin sekretarisnya biar ngerti bahasa manusia ("Besok jam 9 pagi") dan tau sopan santun (taruh memo di meja yang benar/WhatsApp).

### Detail Task:
| Task | Fungsi Teknis | Analogi |
|------|---------------|---------|
| **1. ISO & Relative Time** | Parsing "5 menit lagi" atau "2026-02-15T10:00". | Ngerti perintah: "Nanti sore" atau "Tanggal 15 jam 10". |
| **2. Actions (Update/Run)** | CRUD jadwal (Edit, Paksa Jalan, Cek Status). | Bisa revisi jadwal: "Eh, meetingnya dimajuin", atau "Kerjain sekarang aja". |
| **3. Context Messages** | Lampirin chat history ke reminder. | Pas ingetin meeting, dia bawa berkasnya: "Pak, ini meeting soal Proyek X yg kemarin bapak bahas". |
| **4. Delivery Inference** | Kirim reminder ke channel asal (WA/Telegram). | Kalau bos perintah via WA, laporannya balik ke WA. Jangan ke Email. |

---

## 3. Phase 5: External API Skills
> **Analogi: "Smartphone dengan Browser"**

Bayangkan Kabot adalah **Cendekiawan** yang pintar tapi dikurung di kamar tanpa internet.
- **Masalah Sekarang:** Dia pintar ngomong, tapi ga tau harga saham detik ini, ga tau cuaca di luar, ga tau status baterai mobil listrik Anda.
- **Solusi Upgrade:** Kita kasih dia **Smartphone + Browser**.
- **Hasil:** Dia bisa cek apa saja di dunia luar (API) dan lapor ke Anda.

### Detail Task:
| Task | Fungsi Teknis | Analogi |
|------|---------------|---------|
| **16. WebFetchTool** | HTTP Client (GET/POST/PUT). | Browser Chrome/Safari buat Kabot. |
| **17. Skill Templates** | Template standard buat bikin skill baru. | Buku panduan "Cara Install Aplikasi Baru". |

---

## 4. Phase 6: Plugin System
> **Analogi: "Slot Cartridge Game Console"**

Bayangkan Kabot adalah **Game Console**.
- **Masalah Sekarang:** Gamenya (Skill) disolder mati di mesin. Kalau mau ganti game, harus bongkar mesin pakai obeng (coding ulang core system).
- **Solusi Upgrade:** Kita bikin **Slot Cartridge**.
- **Hasil:** Mau nambah skill baru? Tinggal colok kasetnya (drop folder di `plugins/`). Langsung main. Ga perlu bongkar mesin.

### Detail Task:
| Task | Fungsi Teknis | Analogi |
|------|---------------|---------|
| **18. Loader & Registry** | Scan folder `plugins/` & load `SKILL.md`. | Sistem yang baca kaset game pas dicolok. |
| **19. Discovery Command** | CLI `kabot plugins list`. | Menu di layar TV: "Game apa aja yang terinstall?". |

---

## 5. Phase 7: Vector Memory (Semantic Search)
> **Analogi: "Pustakawan dengan Ingatan Fotografis"**

Bayangkan Kabot adalah **Pustakawan**.
- **Masalah Sekarang:** Dia nyimpen catatan di tumpukan kertas (Markdown files). Kalau Anda tanya "Mana catatan soal **ikan**?", dia cuma cari kertas yang ada tulisan "ikan". Kalau tulisannya "lele" atau "paus", dia ga nemu karena beda kata.
- **Solusi Upgrade:** Kita kasih dia **Sistem Indeks Semantik**.
- **Hasil:** Anda tanya "Mana catatan soal **hewan air**?", dia langsung ambil kertas soal "ikan", "lele", "paus", "kolam renang", karena dia ngerti *maknanya*, bukan cuma *katanya*. Kabot jadi punya "Intuisi".

### Detail Task:
| Task | Fungsi Teknis | Analogi |
|------|---------------|---------|
| **20. Vector Store** | Integrasi ChromaDB / Embeddings. | Rak buku ajaib yang mengelompokkan buku berdasarkan isi cerita, bukan judul abjad. |
| **21. Semantic Search Tool** | Tool `memory_search` buat Agent. | Kacamata khusus buat Kabot nemuin info relevan di rak ajaib itu. |

---

## 6. Phase 2: Agent Loop Hardening
> **Analogi: "Ruang Kerja Kedap Suara & Cek Kesehatan Rutin"**

- **Isolation (Task 6):** Kalau Kabot lagi ngerjain tugas background (Cron), dia ngerjain di ruang kedap suara. Jadi Anda ga keganggu "suara berisik" (log process) di chat utama Anda.
- **Heartbeat (Task 7):** Tiap 5 menit Kabot cek nadi sendiri. "Gue masih hidup ga? Ada tugas nyangkut ga?". Biar ga mati suri.

---

## 7. Phase 3: Gateway REST API
> **Analogi: "Resepsionis 24 Jam"**

- **REST API (Task 9):** Kabot punya meja resepsionis standar. Jadi kalau nanti Anda mau bikin aplikasi HP atau Web Dashboard buat kontrol Kabot, aplikasinya tinggal ngomong sama resepsionis ini. Standar internasional.
