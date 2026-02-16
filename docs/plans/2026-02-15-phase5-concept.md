# Phase 5: External API Skills (Jendela Dunia) 🌍

### Apa Maksudnya?
Saat ini, **Kabot itu seperti "Ilmuwan di Ruang Bawah Tanah"**:
- Dia pintar (LLM), tapi **terisolasi**.
- Dia tidak tahu harga saham detik ini.
- Dia tidak tahu cuaca di luar.
- Dia tidak tahu status baterai mobil listrik Anda.

**Phase 5** bertujuan memberikan Kabot **Jendela ke Dunia Luar (Internet)**.

---

### Cara Kerjanya (2 Komponen Utama):

#### 1. `WebFetchTool` (Browser-nya Kabot) 🌐
Ini adalah "tangan" Kabot untuk mengambil data dari internet.
- **Dulu:** Kabot bingung kalau disuruh cek harga Bitcoin.
- **Sekarang:** Kabot bisa kirim surat (HTTP Request) ke server Bitcoin: *"Halo API, berapa harga BTC sekarang?"*, lalu baca balasannya (JSON).

#### 2. Skill Templates (Buku Panduan) 📖
Ini adalah "standar SOP" supaya Anda gampang bikin skill baru.
- Tanpa template: Setiap bikin skill harus ngoding Python rumit dari nol.
- **Dengan template:** Cukup copy-paste file Markdown, ganti URL API-nya, selesai.
- **Contoh Skill:**
  - **Cek Cuaca:** `GET https://api.weather.com/...`
  - **Cek Saham:** `GET https://api.stock.com/...`
  - **Cek Mobil EV:** `GET https://api.tesla.com/...`

### Kenapa Penting?
Tanpa Phase 5, Kabot cuma chatbot biasa.
Dengan Phase 5, Kabot jadi **Asisten Sakti** yang terhubung real-time.
