---
name: download-manager
description: Mengunduh file dari URL ke direktori workspace lokal kabot dengan verifikasi hash dan indexing memory.
---

Deskripsi:
- Download file dari URL ke direktori workspace lokal Kabot.
- Opsi verifikasi hash, penentuan nama file/destinasi, dan indexing metadata ke memory.

Perintah contoh:
- download-manager download "<url>" "<dest_filename>" --hash
- download-manager download "<url>" --dest docs
- download-manager status  (opsional: cek status latest download)

Output yang diharapkan:
- path file yang terdownload
- ukuran file (bytes)
- hash SHA-256 (jika opsi --hash dipakai)
- ringkasan singkat yang bisa dicatat ke MEMORY.md

Format eksekusi di Kabot:
- download-manager download <url> [dest_subfolder/filename] [--hash] [--dest dest_dir]

Catatan keamanan:
- Batasi domain sumber jika perlu
- Batasi ukuran file dan type (Content-Type, Content-Length)

---
