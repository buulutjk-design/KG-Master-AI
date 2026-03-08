# main.py
import requests, math, time, logging, re
from datetime import datetime
from requests.utils import requote_uri
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# === CONFIG ===
BOT_TOKEN = "8727632778:AAEbNjZzXfS8GHLIoDtoJHAgKMxL4P6y_go"
ADMIN_ID = 8480843841
API_KEY = "2180b95ef16955595f12d9f9cdebcd74"
API_URL = "https://v3.football.api-sports.io"

HOME_NAME, AWAY_NAME = range(2)
analysis_cache = {}
CACHE_TIME = 12 * 3600  # 12 saat

# === LOGGING ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# === UTILITIES ===
def poisson_zero(x):
    try:
        return math.exp(-x)
    except:
        return 0.0

def safe_request(url):
    headers = {'x-rapidapi-key': API_KEY or "", 'x-rapidapi-host': 'v3.football.api-sports.io'}
    for attempt in range(3):
        try:
            r = requests.get(url, headers=headers, timeout=10)
            logging.info("HTTP %s %s (status=%s)", "GET", url, getattr(r, "status_code", None))
            if r.status_code == 200:
                return r.json()
            else:
                logging.warning("API returned status %s for %s", r.status_code, url)
        except Exception as e:
            logging.warning("safe_request exception (attempt %s): %s", attempt+1, e)
        time.sleep(1 + attempt)
    logging.error("safe_request failed after retries for url=%s", url)
    return None

def normalize_name(name: str) -> str:
    s = name.strip()
    s = re.sub(r'\s+', ' ', s)
    return s

def generate_variants(name: str):
    """Return list of query strings to try for teams?search="""
    name = normalize_name(name)
    parts = name.split()
    variants = []
    # original forms
    variants.append(name)
    variants.append(name.title())
    variants.append(name.lower())
    variants.append(name.upper())
    # remove common prefixes/suffixes like 'fc', 'sc', 'cf', 'bsc', 'ath'
    cleaned = re.sub(r'\b(fc|sc|cf|bsc|ac|ck|club|team)\b', '', name, flags=re.IGNORECASE).strip()
    if cleaned and cleaned != name:
        variants.append(cleaned)
        variants.append(cleaned.title())
    # first / last word
    if parts:
        variants.append(parts[0])
        variants.append(parts[-1])
    # add "FC" or "BSC" prefixes/suffixes
    variants.append(f"FC {name}")
    variants.append(f"{name} FC")
    variants.append(f"BSC {name}")
    variants.append(f"{name} BSC")
    # join first two words if long
    if len(parts) > 2:
        variants.append(" ".join(parts[:2]))
        variants.append(" ".join(parts[-2:]))
    # unique preserve order
    seen = set()
    out = []
    for v in variants:
        v = v.strip()
        if not v: 
            continue
        if v.lower() in seen:
            continue
        seen.add(v.lower())
        out.append(v)
    return out

# === TEAM SEARCH ===
def get_team_id(name: str):
    """Try multiple variations to find team id via API."""
    if not API_KEY:
        logging.error("API_KEY missing; cannot search teams.")
        return None

    variants = generate_variants(name)
    logging.info("Searching team '%s' with %d variants", name, len(variants))
    for v in variants:
        q = requote_uri(v)
        url = f"{API_URL}/teams?search={q}"
        res = safe_request(url)
        if not res:
            # if API failed (None) then don't keep trying infinite; try next variant but log
            logging.debug("No response for variant '%s'", v)
            continue
        arr = res.get("response")
        if arr and len(arr) > 0:
            # pick the best match (first)
            team = arr[0].get("team")
            if team and team.get("id"):
                logging.info("Found team id %s for variant '%s' (name='%s')", team["id"], v, team.get("name"))
                return team["id"]
    logging.warning("No team id found for '%s' after variants: %s", name, variants)
    return None

# === TEAM STATS ===
def get_team_stats(team_id):
    if not API_KEY or not team_id:
        return None
    url = f"{API_URL}/fixtures?team={team_id}&last=12"
    res = safe_request(url)
    if not res:
        return None
    matches = res.get("response", [])
    if not matches:
        return None

    btts = 0
    goals_for = []
    goals_against = []
    form_points = 0
    valid = 0

    for m in matches:
        try:
            gh = m["goals"]["home"]
            ga = m["goals"]["away"]
            home_id = m["teams"]["home"]["id"]
        except:
            continue
        if gh is None or ga is None:
            continue
        valid += 1
        if gh > 0 and ga > 0:
            btts += 1
        # determine which side is our team
        if home_id == team_id:
            goals_for.append(gh)
            goals_against.append(ga)
            if gh > ga: form_points += 3
            elif gh == ga: form_points += 1
        else:
            goals_for.append(ga)
            goals_against.append(gh)
            if ga > gh: form_points += 3
            elif gh == ga: form_points += 1

    if valid == 0:
        return None

    return {
        "btts": btts / valid,
        "attack": sum(goals_for)/len(goals_for) if goals_for else 0,
        "defense": sum(goals_against)/len(goals_against) if goals_against else 0,
        "form": form_points / (3 * valid) if valid else 0
    }

# === ANALYSIS ===
def get_match_analysis(t1, t2):
    key = f"{t1.lower().strip()}__{t2.lower().strip()}"
    now = datetime.now().timestamp()
    cached = analysis_cache.get(key)
    if cached and now - cached["time"] < CACHE_TIME:
        logging.info("Cache hit for %s", key)
        return cached["data"]

    id1 = get_team_id(t1)
    id2 = get_team_id(t2)
    if not id1 or not id2:
        logging.warning("get_match_analysis: missing id1 or id2 (id1=%s id2=%s)", id1, id2)
        return None

    s1 = get_team_stats(id1)
    s2 = get_team_stats(id2)
    if not s1 or not s2:
        logging.warning("get_match_analysis: insufficient stats s1=%s s2=%s", bool(s1), bool(s2))
        return None

    # expected goals (simple normalization)
    home_xg = (s1["attack"] + s2["defense"]) / 2
    away_xg = (s2["attack"] + s1["defense"]) / 2

    p_home0 = poisson_zero(home_xg)
    p_away0 = poisson_zero(away_xg)
    poisson = 1 - p_home0 - p_away0 + (p_home0 * p_away0)

    stat = (s1["btts"] + s2["btts"]) / 2
    form = (s1["form"] + s2["form"]) / 2

    final = poisson * 0.5 + stat * 0.3 + form * 0.2
    prob = max(0, min(100, int(final * 100)))

    result = {"h": t1, "a": t2, "p": prob}
    analysis_cache[key] = {"data": result, "time": now}
    return result

# === TELEGRAM HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_ID and update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("You are not authorized.")
        return ConversationHandler.END
    await update.message.reply_text("👋 Welcome to the BTTS Analysis Bot")
    await update.message.reply_text("🏳 Home Team Name.")
    return HOME_NAME

async def get_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['t1'] = update.message.text
    await update.message.reply_text("🚩 Away Team Name:")
    return AWAY_NAME

async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t1 = context.user_data.get('t1')
    t2 = update.message.text if update.message else None
    if not t1 or not t2:
        await update.message.reply_text("Invalid input. /start and enter Home then Away.")
        return ConversationHandler.END

    key = f"{t1.lower().strip()}__{t2.lower().strip()}"
    cached = analysis_cache.get(key)
    now = datetime.now().timestamp()
    if cached and now - cached["time"] < CACHE_TIME:
        result = cached["data"]
    else:
        wait_msg = await update.message.reply_text("🛜 Analysis in progress...\nFetching match data...")
        result = get_match_analysis(t1, t2)
        if not result:
            # helpful error to user
            msg = ("❌ Data not found.\n\n"
                   "Possible reasons:\n"
                   "- Team name not recognized (try: 'BSC Young Boys' or 'Thun')\n"
                   "- API key invalid / limit reached\n\n"
                   "If you believe names are correct, send me the exact text you typed and I will check logs.")
            await wait_msg.edit_text(msg)
            return ConversationHandler.END
        analysis_cache[key] = {"data": result, "time": now}
        await wait_msg.delete()

    prob = result["p"]
    status_icon = "✅" if prob >= 50 else "⛔️"
    status_text = "BTTS YES" if prob >= 50 else "BTTS NO"
    report = (f"📊 MATCH ANALYSIS\n\n🏳 {result['h']}\n🚩 {result['a']}\n\n{status_icon} {status_text}\n{prob}%")
    await update.message.reply_text(report)
    return ConversationHandler.END

# === APP BUILD & RUN ===
def build_app():
    app = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            HOME_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_home)],
            AWAY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, analyze)],
        },
        fallbacks=[]
    )
    app.add_handler(conv)
    return app

def run_forever():
    backoff = 1
    while True:
        try:
            logging.info("Starting bot (run_polling)...")
            app = build_app()
            app.run_polling()
            logging.info("run_polling stopped normally.")
            break
        except KeyboardInterrupt:
            logging.info("KeyboardInterrupt, exiting.")
            break
        except Exception as e:
            logging.error("Unhandled exception: %s", e, exc_info=True)
            logging.info("Restarting in %s seconds...", backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)

if __name__ == "__main__":
    run_forever()
