import requests
import math
import time
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# ===== CONFIG =====
BOT_TOKEN = "8727632778:AAEbNjZzXfS8GHLIoDtoJHAgKMxL4P6y_go"
ADMIN_ID = 8480843841
API_KEY = "2180b95ef16955595f12d9f9cdebcd74"
API_URL = "https://v3.football.api-sports.io"

HOME_NAME, AWAY_NAME = range(2)

# ===== CACHE =====
analysis_cache = {}
CACHE_TIME = 43200  # 12 saat

# ===== API REQUEST =====
def safe_request(url):

    headers = {
        "x-apisports-key": API_KEY
    }

    for _ in range(3):

        try:
            r = requests.get(url, headers=headers, timeout=10)

            if r.status_code == 200:
                return r.json()

        except:
            pass

        time.sleep(1)

    return None


# ===== TEAM ID =====
def get_team_id(name):

    r = safe_request(f"{API_URL}/teams?search={name}")

    if not r:
        return None

    data = r.get("response")

    if data:
        return data[0]["team"]["id"]

    return None


# ===== ANALYSIS =====
def get_match_analysis(team1, team2):

    key = f"{team1.lower()}_{team2.lower()}"

    now = datetime.now().timestamp()

    if key in analysis_cache:

        cached = analysis_cache[key]

        if now - cached["time"] < CACHE_TIME:
            return cached["data"]

    team_id = get_team_id(team1)

    if not team_id:
        return None

    r = safe_request(f"{API_URL}/fixtures?team={team_id}&last=10")

    if not r:
        return None

    matches = r.get("response", [])

    if not matches:
        return None

    btts = 0

    for m in matches:

        gh = m["goals"]["home"]
        ga = m["goals"]["away"]

        if gh and ga and gh > 0 and ga > 0:
            btts += 1

    prob = int((btts / len(matches)) * 100)

    result = {
        "h": team1,
        "a": team2,
        "p": prob
    }

    analysis_cache[key] = {
        "data": result,
        "time": now
    }

    return result


# ===== TELEGRAM =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    await update.message.reply_text("👋 Welcome to the BTTS Analysis Bot")
    await update.message.reply_text("🏳 Home Team Name.")

    return HOME_NAME


async def get_home(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["t1"] = update.message.text

    await update.message.reply_text("🚩 Away Team Name:")

    return AWAY_NAME


async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):

    t1 = context.user_data["t1"]
    t2 = update.message.text

    wait = await update.message.reply_text(
        "🛜 Analysis in progress...\nFetching match data..."
    )

    result = get_match_analysis(t1, t2)

    if not result:

        await wait.edit_text("❌ Data not found.")

        return ConversationHandler.END

    await wait.delete()

    prob = result["p"]

    status_icon = "✅" if prob >= 50 else "⛔️"
    status = "BTTS YES" if prob >= 50 else "BTTS NO"

    report = (
        "📊 MATCH ANALYSIS\n\n"
        f"🏳 {result['h']}\n"
        f"🚩 {result['a']}\n\n"
        f"{status_icon} {status}\n"
        f"{prob}%"
    )

    await update.message.reply_text(report)

    return ConversationHandler.END


# ===== RUN =====
def run_bot():

    while True:

        try:

            app = Application.builder().token(BOT_TOKEN).build()

            conv = ConversationHandler(

                entry_points=[CommandHandler("start", start)],

                states={

                    HOME_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_home)],

                    AWAY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, analyze)]

                },

                fallbacks=[]

            )

            app.add_handler(conv)

            print("BOT RUNNING")

            app.run_polling()

        except Exception as e:

            print("BOT RESTARTING", e)

            time.sleep(5)


run_bot()
