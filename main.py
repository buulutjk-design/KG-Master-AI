import requests
import time
import math
import random
from datetime import datetime, date, timezone, timedelta
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

BOT_TOKEN = "8727632778:AAEbNjZzXfS8GHLIoDtoJHAgKMxL4P6y_go"
ADMIN_ID = 8480843841
API_KEY = "7d7e4508cb4cfe8006ccc9422bb28b1d"
API_URL = "https://v3.football.api-sports.io"

HOME_NAME, AWAY_NAME = range(2)
analysis_cache = {}
CACHE_TIME = 43200
bot_active = True

COMBINE_THRESHOLD = 68
COMBINE_HOUR = 9

MAJOR_LEAGUES = {
    39: "Premier League", 40: "Championship", 41: "League One", 42: "League Two",
    45: "FA Cup", 48: "League Cup", 140: "La Liga", 141: "Segunda Division",
    142: "Copa del Rey", 135: "Serie A", 136: "Serie B", 137: "Coppa Italia",
    78: "Bundesliga", 79: "2. Bundesliga", 80: "3. Liga", 81: "DFB Pokal",
    61: "Ligue 1", 62: "Ligue 2", 66: "Coupe de France", 203: "Süper Lig",
    204: "1. Lig", 205: "2. Lig", 88: "Eredivisie", 89: "Eerste Divisie",
    94: "Primeira Liga", 95: "Segunda Liga", 144: "Jupiler Pro League",
    179: "Scottish Premiership", 180: "Scottish Championship", 181: "Scottish League One",
    235: "Premier League RU", 236: "FNL", 218: "Bundesliga AT", 219: "2. Liga AT",
    207: "Super League CH", 208: "Challenge League", 197: "Super League GR",
    198: "Super League 2 GR", 345: "Czech Liga", 346: "Czech FNL",
    106: "Ekstraklasa", 107: "I Liga PL", 283: "Liga 1 RO", 284: "Liga 2 RO",
    210: "HNL", 286: "Super Liga RS", 119: "Superliga DK", 120: "1. Division DK",
    103: "Eliteserien", 104: "1. Division NO", 113: "Allsvenskan", 114: "Superettan",
    244: "Veikkausliiga", 333: "Premier League UA", 271: "OTP Bank Liga",
    332: "Super Liga SK", 322: "PrvaLiga", 318: "Premier Liga BIH", 341: "Prva CFL",
    316: "Kategoria Superiore", 172: "First League BG", 164: "Úrvalsdeild",
    357: "League of Ireland", 374: "NIFL Premiership", 375: "Cymru Premier",
    377: "A Lyga", 378: "Virsliga", 379: "Meistriliiga", 380: "Vysshaya Liga",
    381: "Divizia Nationala", 307: "Saudi Pro League", 435: "UAE Pro League",
    350: "Stars League QAT", 290: "Persian Gulf Pro League", 384: "Ligat ha'Al",
    253: "MLS", 262: "Liga MX", 263: "Liga de Expansion MX", 321: "Canadian Premier League",
    71: "Serie A BR", 72: "Serie B BR", 73: "Serie C BR", 128: "Liga Profesional AR",
    129: "Primera Nacional AR", 265: "Primera Division CL", 239: "Liga BetPlay CO",
    268: "Primera Division UY", 267: "Division Profesional PY", 281: "Liga 1 PE",
    240: "LigaPro EC", 269: "Liga FUTVE", 98: "J1 League", 99: "J2 League",
    292: "K League 1", 293: "K League 2", 169: "Chinese Super League",
    170: "China League One", 188: "A-League", 323: "Indian Super League",
    296: "Thai League 1", 313: "Liga 1 ID", 288: "Premier Soccer League ZA",
    233: "Egyptian Premier League", 200: "Botola Pro MA", 201: "Ligue Pro TN",
    2: "Champions League", 3: "Europa League", 848: "Conference League",
    1: "World Cup", 9: "World Cup Qualification",
}

TURKISH_TEAMS = {
    "galatasaray": "Galatasaray", "fenerbahce": "Fenerbahce", "fenerbahçe": "Fenerbahce",
    "besiktas": "Besiktas", "beşiktaş": "Besiktas", "trabzonspor": "Trabzonspor",
    "basaksehir": "Istanbul Basaksehir", "başakşehir": "Istanbul Basaksehir",
    "kasimpasa": "Kasimpasa", "kasımpaşa": "Kasimpasa", "konyaspor": "Konyaspor",
    "sivasspor": "Sivasspor", "antalyaspor": "Antalyaspor", "alanyaspor": "Alanyaspor",
    "kayserispor": "Kayserispor", "gaziantep": "Gaziantep FK", "gaziantep fk": "Gaziantep FK",
    "adana demirspor": "Adana Demirspor", "adana": "Adana Demirspor", "rizespor": "Rizespor",
    "hatayspor": "Hatayspor", "samsunspor": "Samsunspor", "ankaragücü": "Ankaragucu",
    "ankaragucu": "Ankaragucu", "eyupspor": "Eyupspor", "eyüpspor": "Eyupspor",
    "goztepe": "Goztepe", "göztepe": "Goztepe", "pendikspor": "Pendikspor",
    "istanbulspor": "Istanbulspor",
}


def normalize(text):
    tr = "çÇğĞıİöÖşŞüÜ"
    en = "cCgGiIoOsSuU"
    for t, e in zip(tr, en):
        text = text.replace(t, e)
    return text


def resolve_team_name(name):
    return TURKISH_TEAMS.get(name.lower().strip(), name)


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
    resolved = resolve_team_name(team_name)
    for name in [resolved, normalize(resolved)]:
        r = safe_request(f"{API_URL}/teams?search={name}")
        if r and r.get("response"):
            t = r["response"][0]["team"]
            return t["id"], t["name"]
    return None, None


def get_last5(team_id):
    """Son 5 maç — Python kodundaki gibi ham gol verisi"""
    r = safe_request(f"{API_URL}/fixtures?team={team_id}&last=5&status=FT")
    if not r:
        return []
    matches = []
    for m in r.get("response", []):
        gh = m["goals"]["home"]
        ga = m["goals"]["away"]
        if gh is None or ga is None:
            continue
        is_home = m["teams"]["home"]["id"] == team_id
        if is_home:
            matches.append({"scored": gh, "conceded": ga, "gh": gh, "ga": ga})
        else:
            matches.append({"scored": ga, "conceded": gh, "gh": gh, "ga": ga})
    return matches


def get_last10(team_id):
    """Son 10 maç KG için"""
    r = safe_request(f"{API_URL}/fixtures?team={team_id}&last=10&status=FT")
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


def get_h2h_smart(id1, id2):
    r = safe_request(f"{API_URL}/fixtures/headtohead?h2h={id1}-{id2}&last=10")
    if not r:
        return [], 0, 0
    cutoff_3y = datetime.now(timezone.utc) - timedelta(days=3 * 365)
    recent_matches = []
    total_found = 0
    for m in r.get("response", []):
        gh = m["goals"]["home"]
        ga = m["goals"]["away"]
        if gh is None or ga is None:
            continue
        total_found += 1
        try:
            match_date = datetime.fromisoformat(m["fixture"]["date"].replace("Z", "+00:00"))
            if match_date >= cutoff_3y:
                recent_matches.append((gh, ga))
        except:
            pass
    return recent_matches, len(recent_matches), total_found


def btts_prob(lh, la):
    """Python kodundaki tam formül"""
    p_home0 = math.exp(-lh)
    p_away0 = math.exp(-la)
    p_00    = math.exp(-(lh + la))
    return 1 - (p_home0 + p_away0 - p_00)


def monte_carlo_btts(lh, la, sims=5000):
    """Python kodundaki Monte Carlo — 5000 simülasyon"""
    yes = 0
    for _ in range(sims):
        # Poisson sample
        def sample(lam):
            L = math.exp(-lam)
            k, p = 0, 1.0
            while p > L:
                k += 1
                p *= random.random()
            return k - 1

        if sample(lh) > 0 and sample(la) > 0:
            yes += 1

    mc_prob = yes / sims
    z = 1.96
    margin = z * math.sqrt((mc_prob * (1 - mc_prob)) / sims)
    lower = max(0, mc_prob - margin)
    upper = min(1, mc_prob + margin)
    return mc_prob, lower, upper


def analyze_teams(id1, name1, id2, name2):
    key = f"{name1.lower()}_{name2.lower()}"
    now = datetime.now().timestamp()
    if key in analysis_cache:
        if now - analysis_cache[key]["time"] < CACHE_TIME:
            return analysis_cache[key]["data"]

    # Son 5 maç verisi — Python kodundaki gibi
    home5 = get_last5(id1)
    away5 = get_last5(id2)

    if not home5 or not away5:
        return None

    # Python kodundaki tam formül
    h_s = sum(m["scored"]   for m in home5) / len(home5)  # ev attığı ort
    h_c = sum(m["conceded"] for m in home5) / len(home5)  # ev yediği ort
    a_s = sum(m["scored"]   for m in away5) / len(away5)  # dep attığı ort
    a_c = sum(m["conceded"] for m in away5) / len(away5)  # dep yediği ort

    # Lambda — Python kodundaki formül
    lam_home = (h_s + a_c) / 2
    lam_away = (a_s + h_c) / 2

    # Ağırlıklı lambda — Python kodundaki gibi
    weight_factor = 1.2
    lam_home_w = ((h_s * weight_factor) + a_c) / (2 + weight_factor - 1)
    lam_away_w = ((a_s * weight_factor) + h_c) / (2 + weight_factor - 1)

    # BTTS olasılıkları — Python kodundaki formül
    p_yes         = btts_prob(lam_home, lam_away)
    p_yes_weighted = btts_prob(lam_home_w, lam_away_w)

    # Monte Carlo — Python kodundaki gibi 5000 sim
    mc_prob, mc_lower, mc_upper = monte_carlo_btts(lam_home, lam_away, 5000)

    # Final: Python kodundaki 3 yöntemin ortalaması
    final = (p_yes + p_yes_weighted + mc_prob) / 3
    final = max(0.05, min(0.95, final))

    # Son 5 maç KG sayısı
    home5_btts = sum(1 for m in home5 if m["gh"] > 0 and m["ga"] > 0)
    away5_btts = sum(1 for m in away5 if m["gh"] > 0 and m["ga"] > 0)

    # Son 10 maç KG sayısı
    home10 = get_last10(id1)
    away10 = get_last10(id2)
    home10_btts = sum(1 for gh, ga in home10 if gh > 0 and ga > 0)
    away10_btts = sum(1 for gh, ga in away10 if gh > 0 and ga > 0)

    # H2H
    h2h, h2h_recent_count, h2h_total = get_h2h_smart(id1, id2)
    h2h_note = ""
    if h2h and h2h_recent_count >= 2:
        h2h_btts = sum(1 for gh, ga in h2h if gh > 0 and ga > 0)
        h2h_note = f"{h2h_btts}/{len(h2h)}"
    elif h2h_total > 0 and h2h_recent_count == 0:
        h2h_note = "old"
    elif h2h_recent_count == 1:
        h2h_btts = sum(1 for gh, ga in h2h if gh > 0 and ga > 0)
        h2h_note = f"{h2h_btts}/{len(h2h)}"
    else:
        h2h_note = "none"

    # Güvenilirlik
    warnings = []
    if len(home5) < 3:
        warnings.append("⚠️ Insufficient home team data")
    if len(away5) < 3:
        warnings.append("⚠️ Insufficient away team data")
    if h2h_note == "none":
        warnings.append("⚠️ No H2H data found")
    elif h2h_note == "old":
        warnings.append("⚠️ H2H data older than 3 years — not used")
    if lam_home <= 0.2 and lam_away <= 0.2:
        warnings.append("⚠️ Very low xG — data may be unreliable")

    if len(warnings) == 0:
        reliability = "🟢 High"
    elif len(warnings) == 1:
        reliability = "🟡 Medium"
    else:
        reliability = "🔴 Low — treat with caution"

    result = {
        "h": name1, "a": name2,
        "p": int(final * 100),
        "lh": round(lam_home, 2),
        "la": round(lam_away, 2),
        "lh_w": round(lam_home_w, 2),
        "la_w": round(lam_away_w, 2),
        "p_yes":     int(p_yes * 100),
        "p_yes_w":   int(p_yes_weighted * 100),
        "mc":        int(mc_prob * 100),
        "mc_low":    int(mc_lower * 100),
        "mc_high":   int(mc_upper * 100),
        "home_btts_5":  f"{home5_btts}/5",
        "away_btts_5":  f"{away5_btts}/5",
        "home_btts_10": f"{home10_btts}/{len(home10)}",
        "away_btts_10": f"{away10_btts}/{len(away10)}",
        "h2h_note": h2h_note,
        "warnings": warnings,
        "reliability": reliability,
    }
    analysis_cache[key] = {"data": result, "time": now}
    return result


def get_match_analysis(team1, team2):
    id1, name1 = search_team_id(team1)
    id2, name2 = search_team_id(team2)
    if not id1:
        return {"error": f"Team not found: '{team1}'"}
    if not id2:
        return {"error": f"Team not found: '{team2}'"}
    result = analyze_teams(id1, name1, id2, name2)
    if not result:
        return {"error": "Match data not found"}
    return result


def get_todays_fixtures():
    today = date.today().strftime("%Y-%m-%d")
    current_year = datetime.now().year
    now_utc = datetime.now(timezone.utc)
    all_fixtures = []
    for league_id, league_name in MAJOR_LEAGUES.items():
        for season in [current_year, current_year - 1]:
            r = safe_request(f"{API_URL}/fixtures?date={today}&league={league_id}&season={season}")
            if not r:
                continue
            matches = r.get("response", [])
            if not matches:
                continue
            for m in matches:
                if m["fixture"]["status"]["short"] not in ["NS", "TBD"]:
                    continue
                try:
                    ko = datetime.fromisoformat(m["fixture"]["date"].replace("Z", "+00:00"))
                    if ko - now_utc < timedelta(hours=2):
                        continue
                except:
                    pass
                all_fixtures.append({
                    "league":    league_name,
                    "home_id":   m["teams"]["home"]["id"],
                    "home_name": m["teams"]["home"]["name"],
                    "away_id":   m["teams"]["away"]["id"],
                    "away_name": m["teams"]["away"]["name"],
                    "kickoff":   m["fixture"]["date"],
                })
            break
        time.sleep(0.3)
    return all_fixtures


def build_daily_combine():
    fixtures = get_todays_fixtures()
    if not fixtures:
        return None
    qualified = []
    for fix in fixtures:
        try:
            result = analyze_teams(
                fix["home_id"], fix["home_name"],
                fix["away_id"], fix["away_name"],
            )
            if (result
                    and result["p"] >= COMBINE_THRESHOLD
                    and result["reliability"] != "🔴 Low — treat with caution"):
                qualified.append({**fix, **result})
            time.sleep(0.2)
        except:
            continue
    if not qualified:
        return None
    qualified.sort(key=lambda x: x["p"], reverse=True)
    return qualified[:3]


def format_combine(combine):
    combine_prob = 1.0
    for m in combine:
        combine_prob *= m["p"] / 100
    lines = ["🎯 DAILY BTTS COMBINE\n"]
    lines.append(f"📅 {date.today().strftime('%d.%m.%Y')}\n")
    for i, m in enumerate(combine, 1):
        try:
            ko = datetime.fromisoformat(m["kickoff"].replace("Z", "+00:00"))
            ko_str = ko.strftime("%H:%M")
        except:
            ko_str = "?"
        lines.append(
            f"{i}. {m['league']}\n"
            f"   🏳 {m['h']} vs 🚩 {m['a']}\n"
            f"   ⏰ {ko_str}  |  ✅ BTTS YES  |  🎯 {m['p']}%\n"
        )
    lines.append(f"\n📊 Combine Win Probability: {int(combine_prob * 100)}%")
    lines.append("⚠️ Always bet responsibly.")
    return "\n".join(lines)


async def send_daily_combine(app):
    while True:
        now = datetime.now()
        target = now.replace(hour=COMBINE_HOUR, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        if not bot_active:
            continue
        try:
            combine = build_daily_combine()
            if not combine:
                await app.bot.send_message(
                    chat_id=ADMIN_ID,
                    text="📋 Daily Combine\n\n❌ No matches found with %68+ confidence today."
                )
            else:
                await app.bot.send_message(chat_id=ADMIN_ID, text=format_combine(combine))
        except Exception as e:
            print("Combine error:", e)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "⛔️ Access Denied.\nThis bot is private and cannot be used by unauthorized users."
        )
        return
    await update.message.reply_text(
        "👋 BTTS Analysis Bot active!\n\n"
        "Use /analyze to analyze a match.\n"
        "Use /combine to get today's combine now.\n"
        "Use /stop to pause the bot.\n\n"
        "📅 Daily combine is sent automatically at 09:00."
    )


async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_active
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔️ Access Denied.")
        return
    bot_active = False
    await update.message.reply_text("🔴 Bot paused.\n\nUse /analyze to resume.")


async def combine_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔️ Access Denied.")
        return
    wait = await update.message.reply_text("🛜 Scanning today's matches... This may take a minute.")
    try:
        combine = build_daily_combine()
        if not combine:
            await wait.edit_text("❌ No matches found with %68+ confidence today.")
            return
        await wait.edit_text(format_combine(combine))
    except Exception as e:
        await wait.edit_text(f"❌ Error: {e}")


async def analyze_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_active
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔️ Access Denied.")
        return ConversationHandler.END
    bot_active = True
    context.user_data.clear()
    await update.message.reply_text("🏳 Home Team Name:")
    return HOME_NAME


async def get_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_active:
        await update.message.reply_text("🔴 Bot is paused. Use /analyze to resume.")
        return ConversationHandler.END
    context.user_data["t1"] = update.message.text
    await update.message.reply_text("🚩 Away Team Name:")
    return AWAY_NAME


async def get_away(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_active:
        await update.message.reply_text("🔴 Bot is paused. Use /analyze to resume.")
        return ConversationHandler.END

    t1 = context.user_data.get("t1", "")
    t2 = update.message.text

    wait = await update.message.reply_text("🛜 Analyzing...")
    result = get_match_analysis(t1, t2)

    if "error" in result:
        await wait.edit_text(f"❌ {result['error']}\n\n➡️ /analyze to try again.")
        return ConversationHandler.END

    await wait.delete()

    prob   = result["p"]
    icon   = "✅" if prob >= 50 else "⛔️"
    status = "BTTS YES" if prob >= 50 else "BTTS NO"

    if result["h2h_note"] == "old":
        h2h_line = "🕐 H2H: Only old data (3+ years) — not used\n"
    elif result["h2h_note"] == "none":
        h2h_line = "🕐 H2H: No data\n"
    else:
        h2h_line = f"🤝 H2H (last 3y): {result['h2h_note']} BTTS\n"

    warning_lines = ""
    if result.get("warnings"):
        warning_lines = "\n" + "\n".join(result["warnings"]) + "\n"

    report = (
        "📊 MATCH ANALYSIS\n\n"
        f"🏳 {result['h']}\n"
        f"🚩 {result['a']}\n\n"
        f"⚽ xG Home: {result['lh']}  |  Away: {result['la']}\n"
        f"⚽ xG Weighted: {result['lh_w']}  |  {result['la_w']}\n\n"
        f"📈 BTTS Probability:          {result['p_yes']}%\n"
        f"📐 BTTS Weighted:             {result['p_yes_w']}%\n"
        f"🎲 Monte Carlo (5k):          {result['mc']}% ({result['mc_low']}-{result['mc_high']}%)\n\n"
        f"⚽ Last 5 BTTS:  🏳 {result['home_btts_5']}  |  🚩 {result['away_btts_5']}\n"
        f"⚽ Last 10 BTTS: 🏳 {result['home_btts_10']}  |  🚩 {result['away_btts_10']}\n"
        f"{h2h_line}"
        f"{warning_lines}\n"
        f"📶 Reliability: {result['reliability']}\n\n"
        f"{icon} {status}\n"
        f"🎯 Final: {prob}%\n\n"
        "➡️ /analyze for new analysis\n"
        "🔴 /stop to pause the bot"
    )

    await update.message.reply_text(report)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled. Use /analyze to start.")
    return ConversationHandler.END


async def post_init(app):
    asyncio.create_task(send_daily_combine(app))


def run_bot():
    while True:
        try:
            app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
            conv = ConversationHandler(
                entry_points=[CommandHandler("analyze", analyze_cmd)],
                states={
                    HOME_NAME: [
                        CommandHandler("analyze", analyze_cmd),
                        CommandHandler("stop", stop_cmd),
                        MessageHandler(filters.TEXT & ~filters.COMMAND, get_home),
                    ],
                    AWAY_NAME: [
                        CommandHandler("analyze", analyze_cmd),
                        CommandHandler("stop", stop_cmd),
                        MessageHandler(filters.TEXT & ~filters.COMMAND, get_away),
                    ],
                },
                fallbacks=[
                    CommandHandler("cancel", cancel),
                    CommandHandler("analyze", analyze_cmd),
                    CommandHandler("stop", stop_cmd),
                ],
                allow_reentry=True,
            )
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("stop", stop_cmd))
            app.add_handler(CommandHandler("combine", combine_cmd))
            app.add_handler(conv)
            print("BOT RUNNING")
            app.run_polling(drop_pending_updates=True)
        except Exception as e:
            print("BOT RESTARTING:", e)
            time.sleep(5)


run_bot()
