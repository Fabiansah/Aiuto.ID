import logging
import asyncio
from datetime import datetime
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)
from telegram.helpers import escape_markdown
from telegram.constants import ParseMode
import os
from dotenv import load_dotenv 

load_dotenv()

# Ambil token dari .env
BOT_TOKEN = os.environ.get('BOT_TOKEN') 
# Ambil ID Admin dari .env
ID_CHAT_ADMIN = os.environ.get('ID_CHAT_ADMIN')

# Hentikan bot jika variabel penting tidak ditemukan
if not BOT_TOKEN:
    raise ValueError("Error: BOT_TOKEN tidak ditemukan di .env")
if not ID_CHAT_ADMIN:
    raise ValueError("Error: ID_CHAT_ADMIN tidak ditemukan di .env")

# --- Konfigurasi Logging (Pindahkan ke bawah variabel) ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
bot_logger = logging.getLogger(__name__)

PILIH_LAYANAN, TERIMA_DATA_TEKS, KIRIM_FILE = range(3)


# --- FUNGSI UNTUK JAM KERJA (TIDAK BERUBAH) ---
def cek_jam_kerja() -> bool:
    """
    Mengecek apakah waktu saat ini berada dalam jam kerja.
    Senin - Sabtu, jam 08:00 - 17:00 WIB. Minggu libur.
    [--- DINONAKTIFKAN SEMENTARA UNTUK TESTING ---]
    """
    return True  # <-- UBAH DI SINI. Selalu dianggap jam kerja
    
    # Baris di bawah ini adalah kode jam kerja yang sebenarnya
    # tz = pytz.timezone('Asia/Jakarta')
    # now = datetime.now(tz)
    
    # if now.weekday() == 6:  # 6 adalah Minggu
    #     return False
    
    # jam_buka = now.replace(hour=8, minute=0, second=0, microsecond=0)
    # jam_tutup = now.replace(hour=17, minute=0, second=0, microsecond=0)

    # return jam_buka <= now < jam_tutup

async def kirim_pesan_libur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mengirim pesan standar saat bot di luar jam kerja. (TIDAK BERUBAH)"""
    pesan = (
        "Mohon maaf, _Saat ini kami sedang di luar jam kerja_\\. \nSilahkan hubungi kami kembali pada jam kerja\\. \n\n"
        "*Jam Kerja:*\n"
        "```\n"
        "Senin   : 08.00 - 17.00 WIB\n"
        "Selasa  : 08.00 - 17.00 WIB\n"
        "Rabu    : 08.00 - 17.00 WIB\n"
        "Kamis   : 08.00 - 17.00 WIB\n"
        "Jum'at  : 08.00 - 17.00 WIB\n"
        "Sabtu   : 08.00 - 17.00 WIB\n"
        "Minggu  : Libur\n"
        "```\n"
        "Terima kasih atas pengertiannya\\."
    )
    if update.message:
        await update.message.reply_text(pesan, parse_mode=ParseMode.MARKDOWN_V2)
    elif update.callback_query:
        # Menjawab callback query dulu agar tidak timeout
        await update.callback_query.answer("Maaf, kami sedang di luar jam kerja.", show_alert=True)
        # Kirim pesan baru karena edit_message_text mungkin gagal jika pesannya sama
        # await update.callback_query.message.reply_text(pesan, parse_mode=ParseMode.MARKDOWN_V2)

# --- FUNGSI UTAMA SAAT /start (TIDAK BERUBAH) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Menampilkan menu utama."""
    if not cek_jam_kerja():
        await kirim_pesan_libur(update, context)
        return

    keyboard = [
        [InlineKeyboardButton("Pendaftaran", callback_data='daftar_joki')],
        [InlineKeyboardButton("Detail Layanan dan Harga", callback_data='tanya')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = (
        "Hai, Selamat datang di *Aiuto\\.ID*\\!\\.\n"
        "Butuh bantuan untuk mengerjakan Makalah atau PowerPoint\\? "
        "Tenang, semuanya bisa di\\-_handle_ langsung oleh Tim *Aiuto\\.ID*\\.\n\n"
        "Pilih layanan di bawah ini\\:"
    )
    
    if update.message:
        # Jika dipanggil via /start
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=reply_markup
        )
    elif update.callback_query:
        # Jika dipanggil dari callback (misal: 'batal' atau setelah 'tanya_admin')
        try:
            # await update.callback_query.answer() <-- [DIHAPUS] Ini penyebab bug
            await update.callback_query.edit_message_text(
                text,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=reply_markup
            )
        except Exception as e:
            # Ini bisa gagal jika pesan tidak berubah (misal: kembali ke menu 2x)
            bot_logger.info(f"Gagal mengedit pesan kembali ke menu utama (mungkin teks sama): {e}")


# --- [PERUBAHAN] ALUR PERCAKAPAN PENDAFTARAN BARU (RINGKAS) ---

async def mulai_pendaftaran(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    [PERUBAHAN] Memulai alur pendaftaran, langsung meminta PILIH LAYANAN.
    Menggantikan fungsi lama yang meminta NAMA.
    """
    if not cek_jam_kerja():
        await kirim_pesan_libur(update, context)
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("Makalah", callback_data='Layanan_Makalah')],
        [InlineKeyboardButton("PowerPoint", callback_data='Layanan_PowerPoint')],
        [InlineKeyboardButton("Batalkan", callback_data='batal')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text="Silakan pilih jenis layanan yang Anda butuhkan:",
        reply_markup=reply_markup
    )
    # Mengarahkan ke state pertama: PILIH_LAYANAN
    return PILIH_LAYANAN

async def pilih_layanan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    [FUNGSI BARU] Menangkap pilihan layanan dan meminta semua data teks sekaligus.
    Menggantikan fungsi 'nama' dan 'no_hp' lama.
    """
    query = update.callback_query
    await query.answer()

    # Inisialisasi data di awal
    context.user_data.clear() # Bersihkan data sesi sebelumnya
    context.user_data['files'] = [] 
    
    pilihan_layanan = query.data.replace('Layanan_', '').replace('_', ' ')
    context.user_data["layanan"] = pilihan_layanan
    bot_logger.info("Layanan dari %s: %s", query.from_user.first_name, pilihan_layanan)

    # Pesan instruksi untuk mengirim data teks dalam satu pesan
    teks_instruksi = (
        f"Anda memilih layanan *{escape_markdown(pilihan_layanan, version=2)}*\\.\n\n"
        "Isi data Anda dengan format sebagai berikut:\n\n"
            "```\n"
            "Nama Lengkap   : [Nama Lengkap]\n"
            "No. Telepon    : [No. Telepon]\n"
            "Catatan        : [Catatan]\n"
            "```\n"
    )

    await query.edit_message_text(
        text=teks_instruksi,
        parse_mode=ParseMode.MARKDOWN_V2
    )
    # Lanjut ke state menunggu data teks
    return TERIMA_DATA_TEKS

async def terima_data_teks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    [FUNGSI BARU] Menerima satu pesan berisi Nama, No. HP, dan Catatan.
    Memvalidasi data tersebut.
    """
    user_data = context.user_data
    pesan_teks = update.message.text
    baris_data = pesan_teks.split('\n')

    # Validasi jumlah baris (minimal 3: Nama, No. HP, Catatan)
    if len(baris_data) < 3:
        await update.message.reply_text(
            "*Format salah\\.*\n"
            "Harap kirim *3 baris* lengkap \\(Nama Lengkap, No\\. Telepon, dan Catatan\\)\\. "
            "Silahkan kirim ulang *Data Anda*\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return TERIMA_DATA_TEKS # Tetap di state ini

    # [PERUBAHAN PARSING] Ekstrak data dari format "Label: Data"
    try:
        nama_line = baris_data[0]
        no_hp_line = baris_data[1]
        catatan_lines = baris_data[2:] # Catatan bisa jadi multi-baris

        # Pastikan format label ada
        if not (":" in nama_line and ":" in no_hp_line and ":" in catatan_lines[0]):
             raise ValueError("Format label : tidak ditemukan")

        nama = nama_line.split(':', 1)[1].strip()
        nomor_telepon = no_hp_line.split(':', 1)[1].strip()
        
        # Gabungkan catatan jika lebih dari satu baris
        # Ambil bagian setelah ':' untuk baris pertama catatan
        catatan = catatan_lines[0].split(':', 1)[1].strip()
        if len(catatan_lines) > 1:
             # Jika catatan ada di beberapa baris, tambahkan sisanya
             catatan += "\n" + "\n".join(catatan_lines[1:])
        
        # Pastikan data tidak kosong
        if not nama or not nomor_telepon or not catatan:
             raise ValueError("Data tidak boleh kosong setelah :")

    except Exception as e:
        bot_logger.warning(f"Gagal parsing data teks: {e}. Data: {pesan_teks}")
        await update.message.reply_text(
            "*Format salah\\.*\n"
            "Pastikan anda mengisi sesuai dengan format berikut:\n"
            "```\n"
            "Nama Lengkap   : [Nama Lengkap]\n"
            "No. Telepon    : [No. Telepon]\n"
            "Catatan        : [Catatan]\n"
            "```\n"
            "Silahkan kirim ulang *Data Anda*\\!\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return TERIMA_DATA_TEKS

    
    # Validasi No. HP (diubah ke format 08)
    if not (nomor_telepon.startswith('08') and nomor_telepon.isdigit() and 10 <= len(nomor_telepon) <= 15):
        await update.message.reply_text(
            "*Format No\\. Telepon Anda salah*\\.\n"
            "Harus diawali dengan `08` dan hanya berisi angka\\. ",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return TERIMA_DATA_TEKS # Tetap di state ini

    # [PERUBAHAN] Hapus pengambilan catatan di sini, sudah diambil di atas
    # if len(baris_data) > 2:
    #     catatan = '\n'.join(baris_data[2:]).strip()
    # else:
    #     catatan = "Tidak ada catatan tambahan."

    # Simpan semua data teks
    user_data["nama"] = nama
    user_data["no_hp"] = nomor_telepon
    user_data["catatan"] = catatan
    bot_logger.info("Data teks diterima dari %s: Nama: %s, HP: %s", update.effective_user.first_name, nama, nomor_telepon)

    # Minta file (menggantikan fungsi 'layanan' lama)
    keyboard = [[InlineKeyboardButton("Kirim Data", callback_data='selesai_kirim_file')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "*Data Anda telah tersimpan di sistem kami*\\.\n\n"
        "Lampirkan *Dokumen File* yang diperlukan\\. "
        "Jika tidak ada file yang di lampirkan, tekan tombol di bawah ini:\n",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=reply_markup
    )
    
    # Lanjut ke state kirim file
    return KIRIM_FILE

async def terima_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Menangkap file/foto dan menyimpannya di user_data.
    """
    file_id = None
    file_type = None
    if update.message.document:
        file_id = update.message.document.file_id
        file_type = 'document'
    elif update.message.photo:
        # Ambil foto kualitas terbaik (terakhir di list)
        file_id = update.message.photo[-1].file_id
        file_type = 'photo'

    if file_id and file_type:
        # Pastikan 'files' ada di user_data
        if 'files' not in context.user_data:
            context.user_data['files'] = []
            
        context.user_data['files'].append({'id': file_id, 'type': file_type})
        bot_logger.info("Menerima file (tipe: %s) dari %s", file_type, update.effective_user.first_name)
        
        # --- [PERBAIKAN UTAMA] ---
        # Baris di bawah ini dikomentari (dinonaktifkan)
        # agar bot tidak membalas "File diterima" setiap kali user mengirim file.
        
        # await update.message.reply_text("*File diterima*\\.\nKirim file lain atau tekan tombol 'Kirim Data'\\.", parse_mode=ParseMode.MARKDOWN_V2)

    return KIRIM_FILE # Tetap di state KIRIM_FILE

async def selesai_pendaftaran(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    [FUNGSI BARU] Mengakhiri pendaftaran.
    Dipanggil saat tombol 'Selesai (Tidak Ada File)' ditekan.
    Menggantikan fungsi 'minta_catatan' dan 'terima_catatan'.
    Logika notifikasi admin dari 'terima_catatan' lama dipindahkan ke sini.
    """
    query = update.callback_query
    await query.answer()
    
    user_data = context.user_data
    chat_id = update.effective_chat.id

    # Edit pesan untuk konfirmasi proses
    if user_data.get('files'):
        pesan_awal = "*Semua file telah diterima*\\.\n"
    else:
        pesan_awal = "*Anda tidak melampirkan file*\\.\n"
        
    await query.edit_message_text(
        text=f"{pesan_awal}Pendaftaran Anda sedang diproses\\.\\.\\.", 
        parse_mode=ParseMode.MARKDOWN_V2
    )

    # --- [LOGIKA NOTIFIKASI ADMIN DIMULAI] ---
    # Logika ini diambil langsung dari fungsi 'terima_catatan' lama Anda
    try:
        # Mengumpulkan data untuk dikirim ke admin
        nama_pendaftar = escape_markdown(user_data.get("nama", "N/A"), version=2)
        no_hp_pendaftar = escape_markdown(user_data.get("no_hp", "N/A"), version=2)
        layanan_pendaftar = escape_markdown(user_data.get("layanan", "N/A"), version=2)
        catatan_pendaftar = escape_markdown(user_data.get("catatan", "N/A"), version=2)
        user = update.effective_user
        username = user.username if user.username else 'Tidak ada'
        file_objects = user_data.get('files', [])

        if file_objects:
            keterangan_lampiran = "*Dokumen terlampir di bawah ini:*"
        else:
            keterangan_lampiran = "*Tidak ada dokumen yang dilampirkan\\.*"

        # Pesan utama untuk Admin
        caption_admin = (
            f"🔔 *PENDAFTAR BARU DITERIMA\\!* 🔔\n\n"
            f"*Nama Lengkap:* {nama_pendaftar}\n"
            f"*No\\. Telepon:* {no_hp_pendaftar}\n"
            f"*Jenis Layanan:* {layanan_pendaftar}\n"
            f"*Username Telegram:* @{username}\n\n"
            f"*Catatan Tambahan:*\n{catatan_pendaftar}\n\n"
            f"{keterangan_lampiran}"
        )
        await context.bot.send_message(chat_id=ID_CHAT_ADMIN, text=caption_admin, parse_mode=ParseMode.MARKDOWN_V2)

        # Mengirim file ke Admin
        if file_objects:
            for file_obj in file_objects:
                try:
                    if file_obj['type'] == 'document':
                        await context.bot.send_document(chat_id=ID_CHAT_ADMIN, document=file_obj['id'])
                    elif file_obj['type'] == 'photo':
                        await context.bot.send_photo(chat_id=ID_CHAT_ADMIN, photo=file_obj['id'])
                except Exception as e:
                    bot_logger.error("Gagal mengirim file ke admin: %s", e)
                    await context.bot.send_message(chat_id=ID_CHAT_ADMIN, text=f"Gagal mengirim 1 file (ID: {file_obj['id']})")
        
        # Pesan konfirmasi untuk User
        if file_objects:
            pesan_konfirmasi_user = (
                "*Terima kasih atas pendaftaran Anda*\\.\n\n"
                "Seluruh lampiran file telah kami terima dengan Sukses\\. "
                "Admin kami akan segera menghubungi Anda untuk melanjutkan _proses_ pembayaran\\."
            )
        else:
            pesan_konfirmasi_user = (
                "*Terima kasih atas pendaftaran Anda*\\.\n\n"
                "Data Anda telah kami terima\\. "
                "Admin kami akan segera menghubungi Anda untuk melanjutkan _proses_ pembayaran\\."
            )
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=pesan_konfirmasi_user, 
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=ReplyKeyboardRemove() # Hapus keyboard custom jika ada
        )

    except Exception as e:
        bot_logger.error("Gagal mengirim data ke admin atau konfirmasi ke user: %s", e)
        await context.bot.send_message(
            chat_id=chat_id,
            text="Maaf, terjadi kesalahan saat mengirim data Anda\\. Silahkan coba lagi nanti atau hubungi admin secara langsung\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    # --- [LOGIKA NOTIFIKASI ADMIN SELESAI] ---

    user_data.clear() # Bersihkan data setelah selesai
    return ConversationHandler.END


async def batal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Membatalkan conversation pendaftaran.
    (FUNGSI INI DIAMBIL DARI KODE ASLI ANDA, TIDAK BERUBAH)
    """
    bot_logger.info("Pengguna %s membatalkan pendaftaran.", update.effective_user.first_name)
    context.user_data.clear()
    
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("Pendaftaran dibatalkan\\.", parse_mode=ParseMode.MARKDOWN_V2)
    else:
        # Jika user ketik /batal
        await update.message.reply_text("Pendaftaran dibatalkan\\.", parse_mode=ParseMode.MARKDOWN_V2)
    
    await asyncio.sleep(1) # Jeda singkat
    
    # Panggil 'start' untuk menampilkan menu utama lagi
    await start(update, context) # Memanggil start untuk menampilkan menu utama
        
    return ConversationHandler.END

async def salah_input_layanan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Memberi tahu pengguna untuk menggunakan tombol saat memilih layanan.
    (HAMPIR SAMA, HANYA MENGGANTI STATE KEMBALIAN)
    """
    await update.message.reply_text("Harap pilih layanan dengan menekan salah satu tombol di atas\\.", parse_mode=ParseMode.MARKDOWN_V2)
    # [PERUBAHAN] Kembali ke state PILIH_LAYANAN
    return PILIH_LAYANAN 

# --- FUNGSI UNTUK TOMBOL "DETAIL LAYANAN DAN HARGA" (TIDAK BERUBAH) ---

async def tanya_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Menangani permintaan 'Detail Layanan dan Harga' dengan hitung mundur."""
    if not cek_jam_kerja():
        await kirim_pesan_libur(update, context)
        return

    query = update.callback_query
    await query.answer()
    user = query.from_user
    nama_pengguna = escape_markdown(user.first_name, version=2)
    username = user.username if user.username else 'Tidak ada'
    
    # --- KIRIM PESAN KE ADMIN ---
    pesan_untuk_admin = (
        f"*PERMINTAAN DETAIL LAYANAN DAN HARGA*\n\n"
        f"Pengguna: *{nama_pengguna}*\\. \nUsername: @{username}\\.\n\n"
        f"Silakan hubungi pengguna ini secepatnya\\!\\."
    )
    await context.bot.send_message(
        chat_id=ID_CHAT_ADMIN, text=pesan_untuk_admin, parse_mode=ParseMode.MARKDOWN_V2
    )
    
    # --- [KODE BARU] LOGIKA HITUNG MUNDUR UNTUK PENGGGUNA ---
    base_text = (
        "Permintaan *Detail Layanan dan Harga* telah kami teruskan ke Admin\\.\n\n"
    )

    # Loop untuk hitung mundur dari 5 ke 1
    for i in range(5, 0, -1):
        countdown_text = f"*Kembali ke menu utama dalam {i} Detik*\\."
        full_text = base_text + countdown_text
        
        try:
            # Edit pesan dengan sisa waktu terbaru
            await query.edit_message_text(
                text=full_text,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception as e:
            # Error bisa terjadi jika teks yang dikirim sama persis
            # (Telegram API menolak). Kita bisa abaikan.
            bot_logger.info(f"Info: Gagal edit pesan countdown (mungkin teks sama): {e}")
        
        # Tunggu 1 detik
        await asyncio.sleep(1)

    # --- [KODE BARU] HITUNG MUNDUR SELESAI ---
    try:
        # (Opsional) Beri pesan terakhir sebelum kembali ke menu
        await query.edit_message_text(
            text="Kembali ke menu utama\\.",
            parse_mode=ParseMode.MARKDOWN_V2 
        )
        await asyncio.sleep(0.5) # Beri jeda singkat agar pengguna sempat membaca
    except Exception as e:
        bot_logger.info(f"Info: Gagal edit pesan terakhir countdown: {e}")

    # Memanggil fungsi start untuk menampilkan kembali menu utama
    if not hasattr(update, 'callback_query'):
        update.callback_query = query
        
    await start(update, context)
    # --- [AKHIR DARI KODE BARU] ---


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Memberikan balasan untuk perintah atau teks yang tidak dikenali di luar conversation.
    (TIDAK BERUBAH)
    """
    if not cek_jam_kerja():
        await kirim_pesan_libur(update, context)
        return
        
    await update.message.reply_text(
        "Kami tidak dapat memproses pesan Anda saat ini\\.\nPilih opsi yang tersedia atau tekan /start untuk memulai ulang\\.",
        parse_mode=ParseMode.MARKDOWN_V2
    )

# --- FUNGSI UTAMA UNTUK MENJALANKAN BOT ---
def main() -> None:
    """Fungsi utama untuk setup dan menjalankan bot."""
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(30.0) # Waktu tunggu koneksi
        .read_timeout(30.0)    # Waktu tunggu membaca data
        .build()
    )

    # --- [PERUBAHAN] Handler untuk alur percakapan (pendaftaran) BARU ---
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(mulai_pendaftaran, pattern='^daftar_joki$')],
        states={
            PILIH_LAYANAN: [
                CallbackQueryHandler(pilih_layanan, pattern='^Layanan_'),
                # Menangani jika user mengetik teks, bukan menekan tombol
                MessageHandler(filters.TEXT & ~filters.COMMAND, salah_input_layanan)
            ],
            TERIMA_DATA_TEKS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, terima_data_teks),
            ],
            KIRIM_FILE: [
                MessageHandler(filters.Document.ALL | filters.PHOTO, terima_file),
                # Tombol 'Selesai' akan memanggil 'selesai_pendaftaran'
                CallbackQueryHandler(selesai_pendaftaran, pattern='^selesai_kirim_file$')
            ],
        },
        fallbacks=[
            # Fallback ini diambil dari kode asli Anda (TIDAK BERUBAH)
            CallbackQueryHandler(batal, pattern='^batal$'), 
            CommandHandler("batal", batal),
        ],
        # Izinkan re-entry ke conversation handler jika diperlukan
        allow_reentry=True
    )
    # --- [AKHIR PERUBAHAN HANDLER] ---

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    
    # Handler untuk tombol "Detail Layanan dan Harga" (di luar conversation)
    application.add_handler(CallbackQueryHandler(tanya_admin, pattern='^tanya$'))
    
    # Handler untuk teks/perintah tidak dikenal (harus diletakkan terakhir)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))
    
    print("Bot Aiuto.ID telah berhasil dijalankan!")
    bot_logger.info("Bot Aiuto.ID telah berhasil dijalankan!")
    
    # Menjalankan bot
    application.run_polling()

if __name__ == "__main__":
    main()
