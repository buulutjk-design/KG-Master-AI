import requests
import time
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

BOT_TOKEN = "8727632778:AAEbNjZzXfS8GHLIoDtoJHAgKMxL4P6y_go"
ADMIN_ID = 8480843841
API_KEY = "2180b95ef16955595f12d9f9cdebcd74"
API_URL = "https://v3.football.api-sports.io"

HOME_NAME, AWAY_NAME = range(2)
analysis_cache = {}
CACHE_TIME = 43200

def safe_request(url):
    headers = {"x-apisports-key": API_KEY}
    for _ in range(3):
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                return r.json()
        except:
            pass
        time.sleep(1)
    return None

def search_team_id(team_name):
    r = safe_request(f"{API_URL}/teams?search={team_name}")
    if not r:
        return None, None
    teams = r.get("response", [])
    if not teams:
        return None, None
    t = teams[0]["team"]
    return t["id"], t["name"]

def get_match_analysis(team1, team2):
    key = f"{team1.lower()}_{team2.lower()}"
    now = datetime.now().timestamp()

    if key in analysis_cache:
        if now - analysis_cache[key]["time"] < CACHE_TIME:
            return analysis_cache[key]["data"]

    id1, name1 = search_team_id(team1)
    id2, name2 = search_team_id(team2)

    if not id1:
        return {"error": f"Team not found: {team1}"}
    if not id2:
        return {"error": f"Team not found: {team2}"}

    # Free planda çalışan tek endpoint: son maçlar (genel liste)
    r = safe_request(f"{API_URL}/fixtures?last=50&status=FT")
    if not r:
        return {"error": "API connection failed"}

    all_matches = r.get("response", [])

    team1_matches = []
    team2_matches = []

    for m in all_matches:
        home_id = m["teams"]["home"]["id"]
        away_id = m["teams"]["away"]["id"]
        gh = m["goals"]["home"]
        ga = m["goals"]["away"]
        if gh is None or ga is None:
            continue

        if home_id == id1 or away_id == id1:
            team1_matches.append((gh, ga))
        if home_id == id2 or away_id == id2:
            team2_matches.append((gh, ga))

    # Eğer son 50'de yoksa daha fazla çek
    if len(team1_matches) < 3 or len(team2_matches) < 3:
        r2 = safe_request(f"{API_URL}/fixtures?last=200&status=FT")
        if r2:
            for m in r2.get("response", []):
                home_id = m["teams"]["home"]["id"]
                away_id = m["teams"]["away"]["id"]
                gh = m["goals"]["home"]
                ga = m["goals"]["away"]
                if gh is None or ga is None:
                    continue
                if home_id == id1 or away_id == id1:
                    team1_matches.append((gh, ga))
                if home_id == id2 or away_id == id2:
                    team2_matches.append((gh, ga))

    # Tekrar eden maçları temizle
    team1_matches = list(dict.fromkeys(team1_matches))[:10]
    team2_matches = list(dict.fromkeys(team2_matches))[:10]

    if not team1_matches or not team2_matches:
        return {"error": f"No match data found.\nFound: {name1}({len(team1_matches)}) {name2}({len(team2_matches)})"}

    def btts_rate(matches):
        if not matches:
            return 0
        return sum(1 for gh, ga in matches if gh > 0 and ga > 0) / len(matches)

    rate1 = btts_rate(team1_matches)
    rate2 = btts_rate(team2_matches)
    prob = int(((rate1 + rate2) / 2) * 100)

    result = {
        "h": name1,
        "a": name2,
        "p": prob,
        "m1": len(team1_matches),
        "m2": len(team2_matches)
    }

    analysis_cache[key] = {"data": result, "time": now}
    return result


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    await update.message.reply_text("👋 BTTS Analysis Bot")
    await update.message.reply_text("🏳 Home Team Name:")
    return HOME_NAME

async def get_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["t1"] = update.message.text
    await update.message.reply_text("🚩 Away Team Name:")
    return AWAY_NAME

async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t1 = context.user_data["t1"]
    t2 = update.message.text

    wait = await update.message.reply_text("🛜 Analyzing...")
    result = get_match_analysis(t1, t2)

    if "error" in result:
        await wait.edit_text(f"❌ {result['error']}")
        return ConversationHandler.END

    await wait.delete()

    prob = result["p"]
    icon = "✅" if prob >= 50 else "⛔️"
    status = "BTTS YES" if prob >= 50 else "BTTS NO"

    report = (
        "📊 MATCH ANALYSIS\n\n"
        f"🏳 {result['h']}\n"
        f"🚩 {result['a']}\n\n"
        f"{icon} {status}\n"
        f"{prob}%"
    )

    await update.message.reply_text(report)
    return ConversationHandler.END


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
