"""Translation catalog for deterministic system and tool responses."""

from __future__ import annotations

from typing import Any

from kabot.i18n.locale import detect_locale

_KEY_ALIASES: dict[str, str] = {
    # Legacy keys kept for backward compatibility.
    "weather_need_location": "weather.need_location",
    "cron_remove_need_selector": "cron.remove.need_selector",
    "cron_update_need_selector": "cron.update.need_selector",
    "cron_update_incomplete": "cron.update.incomplete",
    "cron_time_unclear": "cron.time_unclear",
    "cycle_created": "cron.cycle_created",
}

_CATALOG: dict[str, dict[str, str]] = {
    "en": {
        "weather.need_location": "I need a location to check the weather. Example: check weather in Cilacap.",
        "cron.remove.need_selector": "To remove a schedule, provide `group_id` or schedule title. First run: `list reminder` to see groups.",
        "cron.update.need_selector": "To edit a schedule, provide `group_id` or schedule title. First run: `list reminder` to see groups.",
        "cron.update.incomplete": "Edit format is incomplete. Example: `update schedule grp_shift_a every 12 hours` or `rename grp_shift_a to Shift Team A`.",
        "cron.time_unclear": "I could not determine the reminder time. Example: remind me in 2 minutes, every day at 09:00 standup, or every 4 hours drink water.",
        "cron.cycle_created": "Created cycle '{title}' (group_id: {group_id}) with {job_count} jobs; repeats every {period_days} days.",
        "cron.add.error_message_required": "Error: message is required to create a schedule.",
        "cron.add.error_no_session_context": "Error: no session context available (channel/chat_id).",
        "cron.add.error_schedule_invalid": "Error: invalid schedule ({error}).",
        "cron.add.error_schedule_required": "Error: either at_time, every_seconds, or cron_expr is required.",
        "cron.add.error_policy_violation": "Error: schedule policy rejected this request ({error}).",
        "cron.add.created": "Created job '{name}' (id: {job_id})",
        "cron.add.created_group": "Created job '{name}' (id: {job_id}, group: {group_id}, title: {title})",
        "cron.list.empty": "No scheduled jobs.",
        "cron.list.header": "Scheduled jobs:",
        "cron.list_groups.empty": "No grouped schedules.",
        "cron.list_groups.header": "Schedule groups:",
        "cron.remove.error_job_id_required": "Error: job_id is required for remove.",
        "cron.remove.ok": "Removed job {job_id}",
        "cron.remove.not_found": "Job {job_id} not found",
        "cron.remove_group.error_not_found": "Error: group not found. Provide a valid group_id or title.",
        "cron.remove_group.ok": "Removed group '{title}' ({group_id}) with {removed} jobs",
        "cron.update.error_job_id_required": "Error: job_id is required for update.",
        "cron.update.ok": "Updated job '{name}' ({job_id})",
        "cron.update.not_found": "Job {job_id} not found",
        "cron.update_group.error_not_found": "Error: group not found. Provide a valid group_id or title.",
        "cron.update_group.error_schedule_invalid": "Error: invalid schedule ({error}).",
        "cron.update_group.error_nothing_to_update": "Error: nothing to update. Provide message, schedule, or new_title.",
        "cron.update_group.ok": "Updated group '{title}' ({group_id}) with {updated} jobs",
        "cron.run.error_job_id_required": "Error: job_id is required for run.",
        "cron.run.ok": "Executed job {job_id}",
        "cron.run.not_found": "Job {job_id} not found or disabled",
        "cron.runs.error_job_id_required": "Error: job_id is required for runs.",
        "cron.runs.empty": "No run history for job {job_id}",
        "cron.runs.header": "Run history for {job_id}:",
        "cron.status.running": "Running",
        "cron.status.stopped": "Stopped",
        "cron.status.summary": "Cron Service: {service_state}\nJobs: {jobs}\nNext wake: {next_wake}",
    },
    "id": {
        "weather.need_location": "Saya butuh lokasi untuk cek cuaca. Contoh: cek suhu Cilacap.",
        "cron.remove.need_selector": "Untuk hapus jadwal, sebutkan `group_id` atau judul jadwal. Gunakan dulu: `list reminder` untuk melihat daftar grup.",
        "cron.update.need_selector": "Untuk edit jadwal, sebutkan `group_id` atau judul jadwal. Gunakan dulu: `list reminder` untuk melihat daftar grup.",
        "cron.update.incomplete": "Format edit belum lengkap. Contoh: `ubah jadwal grp_shift_a tiap 12 jam` atau `ubah judul grp_shift_a jadi Shift Team A`.",
        "cron.time_unclear": "Saya belum bisa memastikan waktu pengingat. Contoh: ingatkan 2 menit lagi makan, setiap hari jam 09:00 standup, atau tiap 4 jam minum air.",
        "cron.cycle_created": "Siklus '{title}' berhasil dibuat (group_id: {group_id}) dengan {job_count} job; berulang tiap {period_days} hari.",
        "cron.add.error_message_required": "Error: pesan wajib diisi untuk membuat jadwal.",
        "cron.add.error_no_session_context": "Error: konteks sesi tidak tersedia (channel/chat_id).",
        "cron.add.error_schedule_invalid": "Error: jadwal tidak valid ({error}).",
        "cron.add.error_schedule_required": "Error: isi salah satu at_time, every_seconds, atau cron_expr.",
        "cron.add.error_policy_violation": "Error: kebijakan scheduler menolak permintaan ini ({error}).",
        "cron.add.created": "Berhasil membuat job '{name}' (id: {job_id})",
        "cron.add.created_group": "Berhasil membuat job '{name}' (id: {job_id}, grup: {group_id}, judul: {title})",
        "cron.list.empty": "Tidak ada job terjadwal.",
        "cron.list.header": "Daftar job:",
        "cron.list_groups.empty": "Tidak ada grup jadwal.",
        "cron.list_groups.header": "Grup jadwal:",
        "cron.remove.error_job_id_required": "Error: job_id wajib untuk hapus.",
        "cron.remove.ok": "Berhasil menghapus job {job_id}",
        "cron.remove.not_found": "Job {job_id} tidak ditemukan",
        "cron.remove_group.error_not_found": "Error: grup tidak ditemukan. Berikan group_id atau judul yang valid.",
        "cron.remove_group.ok": "Berhasil menghapus grup '{title}' ({group_id}) dengan {removed} job",
        "cron.update.error_job_id_required": "Error: job_id wajib untuk edit.",
        "cron.update.ok": "Berhasil mengubah job '{name}' ({job_id})",
        "cron.update.not_found": "Job {job_id} tidak ditemukan",
        "cron.update_group.error_not_found": "Error: grup tidak ditemukan. Berikan group_id atau judul yang valid.",
        "cron.update_group.error_schedule_invalid": "Error: jadwal tidak valid ({error}).",
        "cron.update_group.error_nothing_to_update": "Error: tidak ada perubahan. Berikan message, schedule, atau new_title.",
        "cron.update_group.ok": "Berhasil mengubah grup '{title}' ({group_id}) dengan {updated} job",
        "cron.run.error_job_id_required": "Error: job_id wajib untuk run.",
        "cron.run.ok": "Berhasil menjalankan job {job_id}",
        "cron.run.not_found": "Job {job_id} tidak ditemukan atau nonaktif",
        "cron.runs.error_job_id_required": "Error: job_id wajib untuk melihat riwayat run.",
        "cron.runs.empty": "Belum ada riwayat run untuk job {job_id}",
        "cron.runs.header": "Riwayat run untuk {job_id}:",
        "cron.status.running": "Aktif",
        "cron.status.stopped": "Berhenti",
        "cron.status.summary": "Layanan Cron: {service_state}\nJob: {jobs}\nBangun berikutnya: {next_wake}",
    },
    "ms": {
        "weather.need_location": "Saya perlukan lokasi untuk semak cuaca. Contoh: semak suhu di Kuala Lumpur.",
        "cron.remove.need_selector": "Untuk padam jadual, berikan `group_id` atau tajuk jadual. Jalankan dulu: `list reminder` untuk lihat senarai kumpulan.",
        "cron.update.need_selector": "Untuk kemas kini jadual, berikan `group_id` atau tajuk jadual. Jalankan dulu: `list reminder` untuk lihat senarai kumpulan.",
        "cron.update.incomplete": "Format kemas kini belum lengkap. Contoh: `update schedule grp_shift_a every 12 hours` atau `rename grp_shift_a to Shift Team A`.",
        "cron.time_unclear": "Saya tidak dapat memastikan masa peringatan. Contoh: ingatkan saya dalam 2 minit, setiap hari jam 09:00, atau setiap 4 jam minum air.",
        "cron.cycle_created": "Kitaran '{title}' berjaya dibuat (group_id: {group_id}) dengan {job_count} kerja; berulang setiap {period_days} hari.",
        "cron.add.error_message_required": "Ralat: mesej diperlukan untuk membuat jadual.",
        "cron.add.error_no_session_context": "Ralat: konteks sesi tiada (channel/chat_id).",
        "cron.add.error_schedule_invalid": "Ralat: jadual tidak sah ({error}).",
        "cron.add.error_schedule_required": "Ralat: isi salah satu at_time, every_seconds, atau cron_expr.",
        "cron.add.error_policy_violation": "Ralat: polisi scheduler menolak permintaan ini ({error}).",
        "cron.add.created": "Berjaya cipta job '{name}' (id: {job_id})",
        "cron.add.created_group": "Berjaya cipta job '{name}' (id: {job_id}, kumpulan: {group_id}, tajuk: {title})",
        "cron.list.empty": "Tiada job berjadual.",
        "cron.list.header": "Senarai job:",
        "cron.list_groups.empty": "Tiada kumpulan jadual.",
        "cron.list_groups.header": "Kumpulan jadual:",
        "cron.status.running": "Berjalan",
        "cron.status.stopped": "Berhenti",
        "cron.status.summary": "Servis Cron: {service_state}\nJob: {jobs}\nBangun seterusnya: {next_wake}",
    },
    "th": {
        "weather.need_location": "ฉันต้องการตำแหน่งเพื่อเช็กสภาพอากาศ ตัวอย่าง: เช็กอุณหภูมิที่กรุงเทพฯ",
        "cron.remove.need_selector": "หากต้องการลบตาราง โปรดระบุ `group_id` หรือชื่อตาราง ใช้ `list reminder` เพื่อดูรายการกลุ่มก่อน",
        "cron.update.need_selector": "หากต้องการแก้ไขตาราง โปรดระบุ `group_id` หรือชื่อตาราง ใช้ `list reminder` เพื่อดูรายการกลุ่มก่อน",
        "cron.update.incomplete": "รูปแบบคำสั่งแก้ไขยังไม่ครบ ตัวอย่าง: `update schedule grp_shift_a every 12 hours` หรือ `rename grp_shift_a to Shift Team A`",
        "cron.time_unclear": "ฉันยังระบุเวลาการเตือนไม่ได้ ตัวอย่าง: เตือนฉันอีก 2 นาที, ทุกวันเวลา 09:00 หรือทุก 4 ชั่วโมงดื่มน้ำ",
        "cron.cycle_created": "สร้างรอบ '{title}' แล้ว (group_id: {group_id}) จำนวน {job_count} งาน; ทำซ้ำทุก {period_days} วัน",
    },
    "zh": {
        "weather.need_location": "我需要一个地点来查询天气。例如：查询北京天气。",
        "cron.remove.need_selector": "要删除日程，请提供 `group_id` 或日程标题。请先运行：`list reminder` 查看分组列表。",
        "cron.update.need_selector": "要编辑日程，请提供 `group_id` 或日程标题。请先运行：`list reminder` 查看分组列表。",
        "cron.update.incomplete": "编辑格式不完整。示例：`update schedule grp_shift_a every 12 hours` 或 `rename grp_shift_a to Shift Team A`。",
        "cron.time_unclear": "我还无法确定提醒时间。示例：2分钟后提醒我、每天09:00提醒站会、或每4小时喝水。",
        "cron.cycle_created": "已创建循环“{title}”（group_id: {group_id}），共 {job_count} 个任务；每 {period_days} 天重复。",
    },
}


def _normalize_key(key: str) -> str:
    if key in _KEY_ALIASES:
        return _KEY_ALIASES[key]
    dotted = key.replace("_", ".")
    if dotted in _CATALOG["en"]:
        return dotted
    return key


def tr(
    key: str,
    *,
    locale: str | None = None,
    text: str | None = None,
    **kwargs: Any,
) -> str:
    """Translate key to locale, falling back to English."""
    lang = locale or detect_locale(text)
    normalized_key = _normalize_key(key)
    template = _CATALOG.get(lang, {}).get(normalized_key) or _CATALOG["en"].get(normalized_key) or key
    if not kwargs:
        return template
    try:
        return template.format(**kwargs)
    except Exception:
        # Never fail user response because of i18n formatting mismatch.
        return template
