import requests
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, 
    ContextTypes, ConversationHandler
)

# --- GÜNCEL AYARLAR ---
BOT_TOKEN = "8727632778:AAEbNjZzXfS8GHLIoDtoJHAgKMxL4P6y_go"
ADMIN_ID = 8480843841
API_KEY = "2180b95ef16955595f12d9f9cdebcd74"
API_URL = "https://v3.football.api-sports.io"

# Diyalog Durumları
HOME_NAME, AWAY_NAME = range(2)

# --- GELİŞMİŞ ANALİZ MOTORU ---
def get_match_analysis(team1_query, team2_query):
    headers = {'x-rapidapi-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}
    
    # Bugün dahil önümüzdeki 3 günü tara (Maçı kaçırmamak için)
    found_fixture = None
    for i in range(3):
        date = (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d')
        try:
            res = requests.get(f"{API_URL}/fixtures?date={date}", headers=headers).json()
            for f in res.get('response', []):
                h_name = f['teams']['home']['name'].lower()
                a_name = f['teams']['away']['name'].lower()
                t1, t2 = team1_query.lower().strip(), team2_query.lower().strip()
                
                # SIRA BAĞIMSIZ EŞLEŞME: İki takım ismi de maçta geçiyorsa maçı bulduk demektir.
                if (t1 in h_name or t1 in a_name) and (t2 in h_name or t2 in a_name):
                    found_fixture = f
                    break
            if found_fixture: break
        except: continue

    if not found_fixture: return None

    # Eşleşen maç için derin analiz (KG Var/Yok olasılığı)
    try:
        f_id = found_fixture['fixture']['id']
        p_res = requests.get(f"{API_URL}/predictions?fixture={f_id}", headers=headers).json()
        if p_res.get('response'):
            data = p_res['response'][0]
            prob_str = data['predictions']['percent']['btts']
            prob = int(prob_str.replace('%', '')) if prob_str else 0
            return {
                "home": found_fixture['teams']['home']['name'],
                "away": found_fixture['teams']['away']['name'],
                "prob": prob
            }
    except: return None
    return None

# --- BOT AKIŞI ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Sadece senin ID'n için çalışır
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    
    await update.message.reply_text("👋 Welcome to the BTTS Analysis Bot")
    await update.message.reply_text("🏳 Home Team Name.")
    return HOME_NAME

async def get_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['t1'] = update.message.text
    await update.message.reply_text("🚩 Away Team Name:")
    return AWAY_NAME

async def get_away_and_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t2 = update.message.text
    t1 = context.user_data['t1']
    
    wait_msg = await update.message.reply_text("⏳ Analysing...")
    result = get_match_analysis(t1, t2)
    
    if not result:
        await wait_msg.edit_text("❌ Match not found. Try shorter names (e.g., 'Young Boys', 'Thun').")
        return ConversationHandler.END

    prob = result['prob']
    # %50 üzerindeyse YES, altındaysa NO
    status_icon = "✅" if prob >= 50 else "⛔️"
    status_text = "BTTS YES" if prob >= 50 else "BTTS NO"

    final_report = (
        "📊 MATCH ANALYSIS\n\n"
        f"🏳 {result['home']}\n"
        f"🚩 {result['away']}\n\n"
        f"{status_icon} {status_text}\n"
        f"{prob}%"
    )
    
    await wait_msg.delete()
    await update.message.reply_text(final_report)
    
    # OTURUM SONU: API isteği burada durur, bot uykuya geçer.
    return ConversationHandler.END

if __name__ == '__main__':
    # JobQueue'yu tamamen devreden çıkardık (Crashed hatasını önler)
    app = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            HOME_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_home)],
            AWAY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_away_and_analyze)],
        },
        fallbacks=[],
    )
    
    app.add_handler(conv_handler)
    print("Bot is ACTIVE. Sniper mode enabled.")
    app.run_polling()
