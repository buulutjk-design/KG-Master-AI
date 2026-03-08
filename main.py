import requests
import time
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

BOT_TOKEN = "8727632778:AAEbNjZzXfS8GHLIoDtoJHAgKMxL4P6y_go"
ADMIN_ID = 8480843841
API_KEY = "7d7e4508cb4cfe8006ccc9422bb28b1d"
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


def normalize(text):
    # Türkçe karakterleri İngilizce'ye çevir
    tr = "çÇğĞıİöÖşŞüÜ"
    en = "cCgGiIoOsSupU"
    for t, e in zip(tr, en):
        text = text.replace(t, e)
    return text


def search_team_id(team_name):
    # Önce orijinal adla ara
    r = safe_request(f"{API_URL}/teams?search={team_name}")
    if r and r.get("response"):
        t = r["response"][0]["team"]
        return t["id"], t["name"]
    # Bulunamazsa normalize edip tekrar ara
    normalized = normalize(team_name)
    if normalized != team_name:
        r2 = safe_request(f"{API_URL}/teams?search={normalized}")
        if r2 and r2.get("response"):
            t = r2["response"][0]["team"]
            return t["id"], t["name"]
    return None, None


def calc_weighted_btts(matches):
    if not matches:
        return 0
    total_w, btts_w = 0, 0
    for i, (gh, ga) in enumerate(matches):
        w = i + 1
        total_w += w
        if gh > 0 and ga > 0:
            btts_w += w
    return btts_w / total_w


def get_fixtures_by_team(team_id, last=10, venue=None):
    r = safe_request(f"{API_URL}/fixtures?team={team_id}&last={last}&status=FT")
    if not r:
        return []
    matches = []
    for m in r.get("response", []):
        gh = m["goals"]["home"]
        ga = m["goals"]["away"]
        if gh is None or ga is None:
            continue
        if venue == "home" and m["teams"]["home"]["id"] != team_id:
            continue
        if venue == "away" and m["teams"]["away"]["id"] != team_id:
            continue
        matches.append((gh, ga))
    return matches


def get_h2h(id1, id2, last=6):
    r = safe_request(f"{API_URL}/fixtures/headtohead?h2h={id1}-{id2}&last={last}")
    if not r:
        return []
    matches = []
    for m in r.get("response", []):
        gh = m["goals"]["home"]
        ga = m["goals"]["away"]
        if gh is None or ga is None:
            continue
        matches.append((gh, ga))
    return matches


def get_match_analysis(team1, team2):
    key = f"{team1.lower()}_{team2.lower()}"
    now = datetime.now().timestamp()
    if key in analysis_cache:
        if now - analysis_cache[key]["time"] < CACHE_TIME:
            return analysis_cache[key]["data"]

    id1, name1 = search_team_id(team1)
    id2, name2 = search_team_id(team2)

    if not id1:
        return {"error": f"Team not found: '{team1}'"}
    if not id2:
        return {"error": f"Team not found: '{team2}'"}

    home_general = get_fixtures_by_team(id1, last=10)
    home_at_home = get_fixtures_by_team(id1, last=20, venue="home")[:10]
    away_general = get_fixtures_by_team(id2, last=10)
    away_at_away = get_fixtures_by_team(id2, last=20, venue="away")[:10]
    h2h          = get_h2h(id1, id2, last=6)

    if not home_general or not away_general:
        return {"error": "Match data not found"}

    s_hg = calc_weighted_btts(home_general)
    s_hh = calc_weighted_btts(home_at_home) if home_at_home else s_hg
    s_ag = calc_weighted_btts(away_general)
    s_aa = calc_weighted_btts(away_at_away) if away_at_away else s_ag
    s_h2 = calc_weighted_btts(h2h) if h2h else None

    weighted = s_hg * 1.0 + s_hh * 1.5 + s_ag * 1.0 + s_aa * 1.5
    total_w = 5.0
    if s_h2 is not None:
        weighted += s_h2 * 2.0
        total_w += 2.0

    prob = int((weighted / total_w) * 100)
    prob = max(0, min(100, prob))

    result = {"h": name1, "a": name2, "p": prob}
    analysis_cache[key] = {"data": result, "time": now}
    return result


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    context.user_data.clear()
    await update.message.reply_text("🏳 Home Team Name:")
    return HOME_NAME


async def get_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["t1"] = update.message.text
    await update.message.reply_text("🚩 Away Team Name:")
    return AWAY_NAME


async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t1 = context.user_data.get("t1", "")
    t2 = update.message.text

    wait = await update.message.reply_text("🛜 Analyzing...")
    result = get_match_analysis(t1, t2)

    if "error" in result:
        await wait.edit_text(f"❌ {result['error']}\n\nSend /start to try again.")
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
        f"{prob}%\n\n"
        "➡️ Send /start for new analysis."
    )

    await update.message.reply_text(report)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled. Send /start to begin.")
    return ConversationHandler.END


def run_bot():
    while True:
        try:
            app = Application.builder().token(BOT_TOKEN).build()

            conv = ConversationHandler(
                entry_points=[CommandHandler("start", start)],
                states={
                    HOME_NAME: [
                        CommandHandler("start", start),
                        MessageHandler(filters.TEXT & ~filters.COMMAND, get_home),
                    ],
                    AWAY_NAME: [
                        CommandHandler("start", start),
                        MessageHandler(filters.TEXT & ~filters.COMMAND, analyze),
                    ],
                },
                fallbacks=[
                    CommandHandler("cancel", cancel),
                    CommandHandler("start", start),
                ],
                allow_reentry=True,
            )

            app.add_handler(conv)
            # unknown handler KALDIRILDI - çakışmaya neden oluyordu

            print("BOT RUNNING")
            app.run_polling(drop_pending_updates=True)

        except Exception as e:
            print("BOT RESTARTING:", e)
            time.sleep(5)


run_bot()
