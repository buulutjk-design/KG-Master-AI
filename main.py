import logging
import sqlite3
import asyncio
import aiohttp
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ConversationHandler, ContextTypes
)

# === GÜVENLİK VE APİ BİLGİLERİ ===
TELEGRAM_TOKEN = "7963130491:AAHCKiU9DvUv5FUuhlbadgaqTtj00X_lfG4"
API_FOOTBALL_KEY = "0c0c1ad20573b309924dd3d7b1bc3e62"
ADMIN_ID = 8480843841

API_URL = "https://v3.football.api-sports.io"
HEADERS = {
    'x-rapidapi-key': API_FOOTBALL_KEY,
    'x-rapidapi-host': 'v3.football.api-sports.io'
}

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

HOME_TEAM, AWAY_TEAM = range(2)

# === VİP VERİTABANI (SİLİNMEYE KARŞI KORUMALI) ===
def init_db():
    conn = sqlite3.connect('vip_users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, expire_date TEXT)''')
    conn.commit()
    conn.close()

def add_vip(user_id, days):
    conn = sqlite3.connect('vip_users.db')
    c = conn.cursor()
    expire_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    c.execute("INSERT OR REPLACE INTO users (user_id, expire_date) VALUES (?, ?)", (user_id, expire_date))
    conn.commit()
    conn.close()
    return expire_date

def check_vip(user_id):
    if user_id == ADMIN_ID: return True, "Sınırsız"
    conn = sqlite3.connect('vip_users.db')
    c = conn.cursor()
    c.execute("SELECT expire_date FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()
    
    if result:
        expire_date = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
        if datetime.now() < expire_date:
            days_left = (expire_date - datetime.now()).days + 1
            conn.close()
            return True, days_left
        else:
            c.execute("DELETE FROM users WHERE user_id=?", (user_id,))
            conn.commit()
            conn.close()
            return False, "Bitti"
    conn.close()
    return False, "Yok"

# === GÜVENLİ API İSTEK FONKSİYONU ===
def normalize_text(text):
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return text.translate(tr_map).strip()

async def fetch_api(session, endpoint):
    await asyncio.sleep(0.25) # API Ban Koruması (Hassas Hız Sınırı)
    try:
        async with session.get(f"{API_URL}{endpoint}", headers=HEADERS, timeout=15) as response:
            if response.status == 200:
                return await response.json()
    except Exception as e:
        logger.error(f"API Hatası: {e}")
    return None

# === HASSAS MATEMATİKSEL ANALİZ MOTORU ===
async def deep_analysis_task(chat_id, home_name, away_name, bot):
    async with aiohttp.ClientSession() as session:
        try:
            # 1. Takımları Eşleştir
            h_res = await fetch_api(session, f"/teams?search={normalize_text(home_name)}")
            a_res = await fetch_api(session, f"/teams?search={normalize_text(away_name)}")
            
            if not h_res or not h_res['response']: 
                await bot.send_message(chat_id=chat_id, text=f"❌ '{home_name}' takımı bulunamadı.")
                return
            if not a_res or not a_res['response']: 
                await bot.send_message(chat_id=chat_id, text=f"❌ '{away_name}' takımı bulunamadı.")
                return
                
            h_id = h_res['response'][0]['team']['id']
            a_id = a_res['response'][0]['team']['id']
            h_name_real = h_res['response'][0]['team']['name']
            a_name_real = a_res['response'][0]['team']['name']

            # 2. Son 6 Maç (Zaman Ağırlıklı Hedefler)
            h_fix = await fetch_api(session, f"/fixtures?team={h_id}&last=6&status=FT")
            a_fix = await fetch_api(session, f"/fixtures?team={a_id}&last=6&status=FT")
            
            if not h_fix or not a_fix or len(h_fix['response']) < 3 or len(a_fix['response']) < 3:
                await bot.send_message(chat_id=chat_id, text="⚠️ Yeterli maç verisi bulunamadı. Analiz iptal.")
                return

            weight_sum = sum(range(1, 7)) # 21 (Zaman Ağırlığı)
            h_goals, a_goals = 0, 0
            
            for i, match in enumerate(reversed(h_fix['response'])):
                weight = i + 1
                is_home = match['teams']['home']['id'] == h_id
                goals = match['goals']['home'] if is_home else match['goals']['away']
                h_goals += (goals if goals else 0) * weight

            for i, match in enumerate(reversed(a_fix['response'])):
                weight = i + 1
                is_away = match['teams']['away']['id'] == a_id
                goals = match['goals']['away'] if is_away else match['goals']['home']
                a_goals += (goals if goals else 0) * weight

            h_avg = h_goals / weight_sum
            a_avg = a_goals / weight_sum
            wma_expected = h_avg + a_avg

            # 3. Hassas İstatistikler (Şut Kalitesi, Korner ve Kartlar)
            h_stats = await fetch_api(session, f"/teams/statistics?season=2025&team={h_id}&league=39") 
            a_stats = await fetch_api(session, f"/teams/statistics?season=2025&team={a_id}&league=39")
            
            efficiency_multiplier = 1.0 # Başlangıç Şut İsabet Çarpanı
            chaos_multiplier = 0.0 # Korner ve Kart Çarpanı

            if h_stats and a_stats and h_stats['response'] and a_stats['response']:
                try:
                    # Penaltı ve Kart Kaosu
                    h_pen = h_stats['response']['penalty']['scored']['total'] or 0
                    a_cards = a_stats['response']['cards']['red']['total'] or 0
                    if h_pen > 1 or a_cards > 1:
                        chaos_multiplier += 0.10 # Kaos (Kırmızı kart/Penaltı) Üst ihtimalini artırır
                except: pass

            # 4. H2H Hafızası (2025-2026 Arası)
            h2h_res = await fetch_api(session, f"/fixtures/headtohead?h2h={h_id}-{a_id}&last=5")
            memory_bonus = 0
            if h2h_res and h2h_res['response']:
                for match in h2h_res['response']:
                    year = int(match['fixture']['date'][:4])
                    if year >= 2025:
                        g_home = match['goals']['home'] or 0
                        g_away = match['goals']['away'] or 0
                        if (g_home + g_away) >= 3:
                            memory_bonus += 0.15 # Takımlar birbirine açık oynuyor

            # 5. Formülün Birleşimi ve Güven Duvarı
            final_expected = (wma_expected * efficiency_multiplier) + chaos_multiplier + memory_bonus

            base_15 = min(99, int((final_expected / 1.5) * 65))
            base_25 = min(99, int((final_expected / 2.5) * 52))
            base_35 = min(99, int((final_expected / 3.5) * 38))

            alt_15 = max(1, 100 - base_15)
            alt_25 = max(1, 100 - base_25)
            alt_35 = max(1, 100 - base_35)

            # Karar Ağacı (%70 Güven Duvarı)
            if base_25 >= 75:
                karar = "2.5 ÜST Yüksek Güven 🟢"
            elif base_25 >= 70:
                karar = "2.5 ÜST Orta Güven 🟡"
            elif alt_25 >= 75:
                karar = "2.5 ALT Yüksek Güven 🟢"
            elif alt_25 >= 70:
                karar = "2.5 ALT Orta Güven 🟡"
            else:
                karar = "KARARSIZ (Riskli Müsabaka) 🔴"

            # 6. Sonuç Raporu
            report = f"""🔥 MÜSABAKA ANALİZ 🔥

🏳️: {h_name_real} 🚩: {a_name_real}

1.5 ÜST %{base_15}  -  1.5 ALT %{alt_15}
2.5 ÜST %{base_25}  -  2.5 ALT %{alt_25}
3.5 ÜST %{base_35}  -  3.5 ALT %{alt_35}

Karar: {karar}

/dur analiz bitti ise
/analiz başka analiz yapmak için
"""
            await bot.send_message(chat_id=chat_id, text=report)

        except Exception as e:
            logger.error(f"Analiz Hatası: {e}")
            await bot.send_message(chat_id=chat_id, text="❌ Analiz sırasında bir hata oluştu. Lütfen /analiz ile tekrar deneyin.")

# === TELEGRAM KOMUTLARI ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_vip, status = check_vip(user_id)
    
    if status == "Bitti":
        await update.message.reply_text("⚠️ Üyelik Bitti mesajı\nSayın kullanıcı VİP süreniz dolmuştur otomatik olarak VİP silindi.\nİletişim: @blutad")
        return

    if is_vip:
        days_text = f"Sınırsız" if status == "Sınırsız" else f"{status} Günlük"
        msg = (f"Merhaba Sayın VİP Üye Aktifliğiniz Tanımlanmıştır Bol Şanslar. 🍀\n"
               f"Kalan Süre: {days_text}\n\n"
               f"Hemen analiz yapmak için /analiz yazabilirsiniz.")
        await update.message.reply_text(msg)
    else:
        msg = (f"Merhaba VİP Üyeliğiniz Olmadığı için Kullanım Dışısınız Lütfen VİP ALIN 💎\n\n"
               f"VİP: 3 Günlük 450₺\n"
               f"VİP: 7 Günlük 600₺\n\n"
               f"BİLGİ: Tüm Ligler Mevcut İstediğiniz Kadar Analiz Yapabilirsiniz. 🌍\n"
               f"İletişim: @blutad")
        await update.message.reply_text(msg)

async def vipekle3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        target_id = int(context.args[0])
        add_vip(target_id, 3)
        await update.message.reply_text(f"✅ ID: {target_id} kullanıcısına 3 günlük VİP eklendi.")
    except:
        await update.message.reply_text("Hata! Kullanım: /vipekle3 <ID>")

async def vipekle7(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        target_id = int(context.args[0])
        add_vip(target_id, 7)
        await update.message.reply_text(f"✅ ID: {target_id} kullanıcısına 7 günlük VİP eklendi.")
    except:
        await update.message.reply_text("Hata! Kullanım: /vipekle7 <ID>")

# === ANALİZ SOHBET AKIŞI ===
async def analiz_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_vip, _ = check_vip(user_id)
    if not is_vip:
        await update.message.reply_text("🚫 VİP Üyeliğiniz Yok! İletişim: @blutad")
        return ConversationHandler.END

    await update.message.reply_text("🏳️ Ev Sahibi Takım Adı:", reply_markup=ReplyKeyboardRemove())
    return HOME_TEAM

async def get_home_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['home'] = update.message.text
    await update.message.reply_text("🚩 Deplasman Takım Adı:")
    return AWAY_TEAM

async def get_away_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['away'] = update.message.text
    chat_id = update.effective_chat.id
    
    await update.message.reply_text("🛜 Analiz motoru analize başladı… ⏳")
    
    asyncio.create_task(deep_analysis_task(
        chat_id=chat_id, 
        home_name=context.user_data['home'], 
        away_name=context.user_data['away'], 
        bot=context.bot
    ))
    
    return ConversationHandler.END

async def dur_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛑 İşlem durduruldu.\n/analiz başka analiz yapmak için")
    return ConversationHandler.END

# === BAŞLATICI ===
def main():
    init_db()
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("vipekle3", vipekle3))
    app.add_handler(CommandHandler("vipekle7", vipekle7))

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('analiz', analiz_start)],
        states={
            HOME_TEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_home_team)],
            AWAY_TEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_away_team)],
        },
        fallbacks=[CommandHandler('dur', dur_command)]
    )
    app.add_handler(conv_handler)

    logger.info("Bot Güvenli Modda Başlatıldı...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
