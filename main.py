import logging
import sqlite3
import requests
import os
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    Defaults
)
from telegram.constants import ParseMode

# --- AYARLAR ---
BOT_TOKEN = "8624704713:AAFUq5ycoEDf_3Ms_fnGBBoBqcV7Tvb4mqw"
ADMIN_ID = 8480843841
API_KEY = "2180b95ef16955595f12d9f9cdebcd74"
API_URL = "https://v3.football.api-sports.io"

# --- MESAJ TASLAKLARI ---
VIP_YOK_MSG = "ℹ️: Bot Kullanmak için VİP Olmalısınız.\n💰: 7 Günlük Üyelik 700₺\n📞: İletişim @blutad"
VIP_HOSGELDIN = "⚽️: 7 Günlük VİP ÜYELİĞİNİZ Tanımlanmıştır. Bol Şanslar Dileriz ☘️\nkomut: /start"
VIP_BITTI_MSG = "ℹ️: Sayın Kullanıcı VİP Üyeliğinizin Süresi Dolmuştur.\n📞: İletişim @blutad"
ANALIZ_BASLADI = "🌎 Bugün Bültendeki Dünya Geneli Maçlar Analiz Ediliyor..datalar…."

# Analiz Adımları
COUNT, CONFIDENCE = range(2)

# --- VERİTABANI YÖNETİMİ ---
def init_db():
    conn = sqlite3.connect('vip_system.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, expire_date TEXT)''')
    conn.commit()
    conn.close()

def is_vip(user_id):
    if user_id == ADMIN_ID: return True
    conn = sqlite3.connect('vip_system.db')
    c = conn.cursor()
    c.execute("SELECT expire_date FROM users WHERE user_id=?", (user_id,))
    res = c.fetchone()
    conn.close()
    if res:
        expire_date = datetime.fromisoformat(res[0])
        return expire_date > datetime.now()
    return False

# --- GELİŞMİŞ KG ANALİZ MOTORU ---
def get_real_kg_analysis(match_limit, min_confidence):
    headers = {'x-rapidapi-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}
    today = datetime.now().strftime('%Y-%m-%d')
    
    try:
        # 1. Bugünün tüm maçlarını getir
        f_res = requests.get(f"{API_URL}/fixtures?date={today}", headers=headers).json()
    except: return []

    analyzed = []
    # Bültendeki başlamamış ilk 50 maçı tara (Limitleri korumak için)
    fixtures = [f for f in f_res.get('response', []) if f['fixture']['status']['short'] == 'NS'][:50]

    for f in fixtures:
        fid = f['fixture']['id']
        try:
            # 2. Her maç için derin tahmin verilerini çek (xG, Form, Sakatlık, Lig faktörü dahil)
            p_res = requests.get(f"{API_URL}/predictions?fixture={fid}", headers=headers).json()
            if p_res.get('response'):
                data = p_res['response'][0]
                # API'nin hesapladığı KG Var (BTTS) yüzdesi
                prob_str = data['predictions']['percent']['btts']
                prob = int(prob_str.replace('%', '')) if prob_str else 0
                
                if prob >= int(min_confidence):
                    home = f['teams']['home']['name']
                    away = f['teams']['away']['name']
                    analyzed.append((f"🏳️ {home} - {away}", prob))
        except: continue

    # Yüzdeye göre sırala
    analyzed.sort(key=lambda x: x[1], reverse=True)
    return analyzed[:match_limit]

# --- BOT KOMUTLARI ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_vip(user_id):
        await update.message.reply_text(VIP_YOK_MSG)
        return ConversationHandler.END
    
    await update.message.reply_text("ℹ️: KG Analizi Yapılacak Maç Sayısı.")
    return COUNT

async def get_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['m_count'] = int(update.message.text)
        await update.message.reply_text("ℹ️: Güven Aralığı Giriniz [ % ]")
        return CONFIDENCE
    except:
        await update.message.reply_text("Lütfen sadece sayı giriniz.")
        return COUNT

async def get_confidence_and_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        conf = int(update.message.text.replace('%', ''))
        count = context.user_data['m_count']
        await update.message.reply_text(ANALIZ_BASLADI)
        
        matches = get_real_kg_analysis(count, conf)
        
        if not matches:
            await update.message.reply_text("❌ Kriterlere uygun maç bulunamadı.")
            return ConversationHandler.END

        # Mesaj İnşası
        res_text = f"Günün Maçları 🔥\n({len(matches)})\n\n"
        avg_conf = 0
        for m_name, m_prob in matches:
            res_text += f"{m_name}\n"
            avg_conf += m_prob
        
        real_avg = avg_conf // len(matches)
        res_text += f"\nℹ️: Güven Durumu [ % {real_avg} ]"
        
        await update.message.reply_text(res_text)
        return ConversationHandler.END
    except:
        await update.message.reply_text("Hata! Lütfen güven oranını sayı olarak giriniz.")
        return CONFIDENCE

# --- ADMİN PANELİ ---
async def vipekle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        uid = int(context.args[0])
        exp = datetime.now() + timedelta(days=7)
        conn = sqlite3.connect('vip_system.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO users VALUES (?, ?)", (uid, exp.isoformat()))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ {uid} başarıyla 7 günlük VIP yapıldı.")
        await context.bot.send_message(chat_id=uid, text=VIP_HOSGELDIN)
    except:
        await update.message.reply_text("Kullanım: /vipekle id")

# --- SÜRE KONTROLÜ ---
async def check_expiry(context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('vip_system.db')
    c = conn.cursor()
    c.execute("SELECT user_id, expire_date FROM users")
    for uid, exp in c.fetchall():
        if datetime.fromisoformat(exp) < datetime.now():
            c.execute("DELETE FROM users WHERE user_id=?", (uid,))
            try: await context.bot.send_message(chat_id=uid, text=VIP_BITTI_MSG)
            except: pass
    conn.commit()
    conn.close()

# --- ANA MOTOR ---
if __name__ == '__main__':
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_count)],
            CONFIDENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_confidence_and_analyze)],
        },
        fallbacks=[],
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler('vipekle', vipekle))
    
    if app.job_queue:
        app.job_queue.run_repeating(check_expiry, interval=3600, first=10)

    print("--- KG MASTER AI AKTİF ---")
    app.run_polling()
