import requests
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, 
    ContextTypes, ConversationHandler
)

# --- AYARLAR ---
BOT_TOKEN = "8540157840:AAEU16aFsx1opTfESiGyx0WQN18EjUj75BU"
ADMIN_ID = 8480843841
API_KEY = "2180b95ef16955595f12d9f9cdebcd74"
API_URL = "https://v3.football.api-sports.io"

# Durumlar
HOME_NAME, AWAY_NAME = range(2)

# --- NOKTA ATIŞI ANALİZ MOTORU ---
def get_match_analysis(home_query, away_query):
    headers = {'x-rapidapi-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}
    today = datetime.now().strftime('%Y-%m-%d')
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    found_fixture = None
    
    # Sadece bugün ve yarınki maçlar taranır
    for date in [today, tomorrow]:
        try:
            # API'den o günkü maç listesini tek seferde çeker
            res = requests.get(f"{API_URL}/fixtures?date={date}", headers=headers).json()
            for f in res.get('response', []):
                h_name = f['teams']['home']['name'].lower()
                a_name = f['teams']['away']['name'].lower()
                
                # İsim eşleşmesi (Takımları bulursa döngüden çıkar)
                if home_query.lower() in h_name and away_query.lower() in a_name:
                    found_fixture = f
                    break
            if found_fixture: break
        except: continue

    if not found_fixture: return None

    # Eşleşen maç için TEK bir analiz isteği atar
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
    # SADECE ADMİN KULLANABİLİR
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    
    await update.message.reply_text("👋 Welcome to the BTTS Analysis Bot")
    await update.message.reply_text("🏳 Home Team Name.")
    return HOME_NAME

async def get_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['home_team'] = update.message.text
    await update.message.reply_text("🚩 Away Team Name:")
    return AWAY_NAME

async def get_away_and_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    away_team = update.message.text
    home_team = context.user_data['home_team']
    
    wait_msg = await update.message.reply_text("⏳ Analysing...")
    
    # Analiz yapılır
    result = get_match_analysis(home_team, away_team)
    
    if not result:
        await wait_msg.edit_text("❌ Match not found. Check team names.")
        return ConversationHandler.END

    prob = result['prob']
    # İstediğin Emoji ve Şablon Düzeni
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
    
    # ANALİZ BİTTİ, OTURUM KAPANDI (API isteği burada kesilir)
    return ConversationHandler.END

# --- ANA MOTOR ---
if __name__ == '__main__':
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
    
    print("Sistem Hazır. API istekleri sadece analiz sırasında yapılacak.")
    app.run_polling()
