import requests
import time
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# ===== SETTINGS =====
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
        return None
    teams = r.get("response", [])
    return teams[0]["team"]["id"] if teams else None


def calc_btts_weighted(matches):
    """
    Son maçlara daha fazla ağırlık ver.
    En yeni maç = en yüksek ağırlık.
    """
    if not matches:
        return None

    total_weight = 0
    btts_weight = 0

    n = len(matches)
    for i, (gh, ga) in enumerate(matches):
        # i=0 en eski, i=n-1 en yeni → yeni maça daha fazla ağırlık
        weight = i + 1
        total_weight += weight
        if gh > 0 and ga > 0:
            btts_weight += weight

    return btts_weight / total_weight


def get_fixtures(team_id, last=10, venue=None):
    """
    Takımın son maçlarını çek.
    venue: 'home' veya 'away' filtresi için kullanılır (manuel filtre).
    """
    r = safe_request(f"{API_URL}/fixtures?team={team_id}&last={last}&status=FT")
    if not r:
        return []

    matches = []
    for m in r.get("response", []):
        gh = m["goals"]["home"]
        ga = m["goals"]["away"]
        if gh is None or ga is None:
            continue

        if venue == "home":
            # Sadece bu takımın ev maçları
            if m["teams"]["home"]["id"] != team_id:
                continue
        elif venue == "away":
            # Sadece bu takımın deplasman maçları
            if m["teams"]["away"]["id"] != team_id:
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
        cached = analysis_cache[key]
        if now - cached["time"] < CACHE_TIME:
            return cached["data"]

    # Takım ID'leri
    id1 = search_team_id(team1)
    id2 = search_team_id(team2)
    if not id1 or not id2:
        return None

    # === VERİ ÇEK ===

    # Ev takımının son 10 genel maçı
    home_general = get_fixtures(id1, last=10)

    # Ev takımının son 10 EV maçı
    home_at_home = get_fixtures(id1, last=20, venue="home")[:10]

    # Deplasman takımının son 10 genel maçı
    away_general = get_fixtures(id2, last=10)

    # Deplasman takımının son 10 DEPLASMAN maçı
    away_at_away = get_fixtures(id2, last=20, venue="away")[:10]

    # H2H son 6 maç
    h2h = get_h2h(id1, id2, last=6)

    # Yeterli veri kontrolü
    if not home_general or not away_general:
        return None

    # === AĞIRLIKLI HESAPLAMA ===
    # Her faktörün BTTS oranı (ağırlıklı)
    scores = {}

    scores["home_general"] = calc_btts_weighted(home_general)
    scores["home_at_home"] = calc_btts_weighted(home_at_home) if home_at_home else scores["home_general"]
    scores["away_general"] = calc_btts_weighted(away_general)
    scores["away_at_away"] = calc_btts_weighted(away_at_away) if away_at_away else scores["away_general"]
    scores["h2h"] = calc_btts_weighted(h2h) if h2h else None

    # === AĞIRLIK ORANLARI ===
    # Ev/dep spesifik verisi daha değerli → daha yüksek ağırlık
    weighted_sum = (
        scores["home_general"] * 1.0 +
        scores["home_at_home"] * 1.5 +
        scores["away_general"] * 1.0 +
        scores["away_at_away"] * 1.5
    )
    total_w = 5.0

    if scores["h2h"] is not None:
        weighted_sum += scores["h2h"] * 2.0  # H2H en değerli faktör
        total_w += 2.0

    final_prob = int((weighted_sum / total_w) * 100)
    final_prob = max(0, min(100, final_prob))  # 0-100 sınırla

    result = {
        "h": team1.title(),
        "a": team2.title(),
        "p": final_prob,
    }

    analysis_cache[key] = {"data": result, "time": now}
    return result


# ===== TELEGRAM =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    await update.message.reply_text("👋 Welcome to the BTTS Analysis Bot")
    await update.message.reply_text("🏳 Home Team Name:")
    return HOME_NAME


async def get_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["t1"] = update.message.text
    await update.message.reply_text("🚩 Away Team Name:")
    return AWAY_NAME


async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t1 = context.user_data["t1"]
    t2 = update.message.text

    wait = await update.message.reply_text("🛜 Analysis in progress...\nFetching match data...")

    result = get_match_analysis(t1, t2)

    if not result:
        await wait.edit_text("❌ Data not found. Check team names and try again.")
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
