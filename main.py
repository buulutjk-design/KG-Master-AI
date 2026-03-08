Haklısın, her zaman geçerli. Full kod:

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
    39: "Premier League",
    40: "Championship",
    41: "League One",
    42: "League Two",
    45: "FA Cup",
    48: "League Cup",
    140: "La Liga",
    141: "Segunda Division",
    142: "Copa del Rey",
    135: "Serie A",
    136: "Serie B",
    137: "Coppa Italia",
    78: "Bundesliga",
    79: "2. Bundesliga",
    80: "3. Liga",
    81: "DFB Pokal",
    61: "Ligue 1",
    62: "Ligue 2",
    66: "Coupe de France",
    203: "Süper Lig",
    204: "1. Lig",
    205: "2. Lig",
    88: "Eredivisie",
    89: "Eerste Divisie",
    94: "Primeira Liga",
    95: "Segunda Liga",
    144: "Jupiler Pro League",
    179: "Scottish Premiership",
    180: "Scottish Championship",
    181: "Scottish League One",
    235: "Premier League RU",
    236: "FNL",
    218: "Bundesliga AT",
    219: "2. Liga AT",
    207: "Super League CH",
    208: "Challenge League",
    197: "Super League GR",
    198: "Super League 2 GR",
    345: "Czech Liga",
    346: "Czech FNL",
    106: "Ekstraklasa",
    107: "I Liga PL",
    283: "Liga 1 RO",
    284: "Liga 2 RO",
    210: "HNL",
    286: "Super Liga RS",
    119: "Superliga DK",
    120: "1. Division DK",
    103: "Eliteserien",
    104: "1. Division NO",
    113: "Allsvenskan",
    114: "Superettan",
    244: "Veikkausliiga",
    333: "Premier League UA",
    271: "OTP Bank Liga",
    332: "Super Liga SK",
    322: "PrvaLiga",
    318: "Premier Liga BIH",
    341: "Prva CFL",
    316: "Kategoria Superiore",
    172: "First League BG",
    164: "Úrvalsdeild",
    357: "League of Ireland",
    374: "NIFL Premiership",
    375: "Cymru Premier",
    377: "A Lyga",
    378: "Virsliga",
    379: "Meistriliiga",
    380: "Vysshaya Liga",
    381: "Divizia Nationala",
    307: "Saudi Pro League",
    435: "UAE Pro League",
    350: "Stars League QAT",
    290: "Persian Gulf Pro League",
    384: "Ligat ha'Al",
    253: "MLS",
    262: "Liga MX",
    263: "Liga de Expansion MX",
    321: "Canadian Premier League",
    71: "Serie A BR",
    72: "Serie B BR",
    73: "Serie C BR",
    128: "Liga Profesional AR",
    129: "Primera Nacional AR",
    265: "Primera Division CL",
    239: "Liga BetPlay CO",
    268: "Primera Division UY",
    267: "Division Profesional PY",
    281: "Liga 1 PE",
    240: "LigaPro EC",
    269: "Liga FUTVE",
    98: "J1 League",
    99: "J2 League",
    292: "K League 1",
    293: "K League 2",
    169: "Chinese Super League",
    170: "China League One",
    188: "A-League",
    323: "Indian Super League",
    296: "Thai League 1",
    313: "Liga 1 ID",
    288: "Premier Soccer League ZA",
    233: "Egyptian Premier League",
    200: "Botola Pro MA",
    201: "Ligue Pro TN",
    2: "Champions League",
    3: "Europa League",
    848: "Conference League",
    1: "World Cup",
    9: "World Cup Qualification",
}

TURKISH_TEAMS = {
    "galatasaray": "Galatasaray",
    "fenerbahce": "Fenerbahce",
    "fenerbahçe": "Fenerbahce",
    "besiktas": "Besiktas",
    "beşiktaş": "Besiktas",
    "trabzonspor": "Trabzonspor",
    "basaksehir": "Istanbul Basaksehir",
    "başakşehir": "Istanbul Basaksehir",
    "kasimpasa": "Kasimpasa",
    "kasımpaşa": "Kasimpasa",
    "konyaspor": "Konyaspor",
    "sivasspor": "Sivasspor",
    "antalyaspor": "Antalyaspor",
    "alanyaspor": "Alanyaspor",
    "kayserispor": "Kayserispor",
    "gaziantep": "Gaziantep FK",
    "gaziantep fk": "Gaziantep FK",
    "adana demirspor": "Adana Demirspor",
    "adana": "Adana Demirspor",
    "rizespor": "Rizespor",
    "hatayspor": "Hatayspor",
    "samsunspor": "Samsunspor",
    "ankaragücü": "Ankaragucu",
    "ankaragucu": "Ankaragucu",
    "eyupspor": "Eyupspor",
    "eyüpspor": "Eyupspor",
    "goztepe": "Goztepe",
    "göztepe": "Goztepe",
    "pendikspor": "Pendikspor",
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


def get_fixtures_by_team(team_id, last=15, venue=None):
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
            match_date = datetime.fromisoformat(
                m["fixture"]["date"].replace("Z", "+00:00")
            )
            if match_date >= cutoff_3y:
                recent_matches.append((gh, ga))
        except:
            pass

    return recent_matches, len(recent_matches), total_found


def get_team_league(team_id):
    current_year = datetime.now().year
    for season in [current_year, current_year - 1]:
        r = safe_request(
            f"{API_URL}/leagues?team={team_id}&season={season}&current=true"
        )
        if r and r.get("response"):
            for league in r["response"]:
                if league["league"]["type"] == "League":
                    return league["league"]["id"], season
    return None, None


def get_team_statistics(team_id, league_id, season):
    r = safe_request(
        f"{API_URL}/teams/statistics?team={team_id}&league={league_id}&season={season}"
    )
    if not r or not r.get("response"):
        return None
    return r["response"]


def get_standings_form(team_id, league_id, season):
    r = safe_request(f"{API_URL}/standings?league={league_id}&season={season}")
    if not r or not r.get("response"):
        return None, None
    for group in r["response"]:
        for standings in group.get("league", {}).get("standings", []):
            for team in standings:
                if team["team"]["id"] == team_id:
                    return team["rank"], team.get("form", "")
    return None, None


def get_season_btts(team_id, league_id, season):
    """
    Her sezon durumuna göre akıllı veri karıştırma:
    8+ maç  → sadece bu sezon
    4-7 maç → bu sezon %60 + önceki %40
    1-3 maç → bu sezon %25 + önceki %75
    0 maç   → tamamen önceki sezon
    Sezon ortası/sonu da önceki sezon ağırlığı azalır, bu sezon artar — otomatik.
    """
    if not league_id or not season:
        return None, 0, 0, ""

    def fetch(s):
        r = safe_request(
            f"{API_URL}/fixtures?team={team_id}&league={league_id}&season={s}&status=FT"
        )
        if not r:
            return 0, 0
        btts, total = 0, 0
        for m in r.get("response", []):
            gh = m["goals"]["home"]
            ga = m["goals"]["away"]
            if gh is None or ga is None:
                continue
            total += 1
            if gh > 0 and ga > 0:
                btts += 1
        return btts, total

    curr_btts, curr_total = fetch(season)
    prev_btts, prev_total = fetch(season - 1)

    curr_rate = curr_btts / curr_total if curr_total > 0 else None
    prev_rate = prev_btts / prev_total if prev_total >= 5 else None

    if curr_total >= 8:
        # Yeterli veri — sadece bu sezon
        rate = curr_rate
        label = f"{curr_btts}/{curr_total}"
    elif curr_total >= 4 and prev_rate is not None:
        # Az veri — ikisini karıştır
        rate = curr_rate * 0.60 + prev_rate * 0.40
        label = f"{curr_btts}/{curr_total}+prev"
    elif curr_total >= 1 and prev_rate is not None:
        # Çok az veri — önceki sezon ağırlıklı
        rate = curr_rate * 0.25 + prev_rate * 0.75
        label = f"{curr_btts}/{curr_total}+prev"
    elif prev_rate is not None:
        # Hiç veri yok — tamamen önceki sezon
        rate = prev_rate
        label = f"prev({prev_btts}/{prev_total})"
    elif curr_rate is not None and curr_total >= 3:
        rate = curr_rate
        label = f"{curr_btts}/{curr_total}"
    else:
        return None, 0, 0, ""

    return rate, curr_btts, curr_total, label


def poisson_prob(lam, k):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (math.exp(-lam) * (lam ** k)) / math.factorial(k)


def dixon_coles_correction(hg, ag, lh, la, rho=-0.13):
    if hg == 0 and ag == 0:
        return 1 - lh * la * rho
    elif hg == 0 and ag == 1:
        return 1 + lh * rho
    elif hg == 1 and ag == 0:
        return 1 + la * rho
    elif hg == 1 and ag == 1:
        return 1 - rho
    return 1.0


def dixon_coles_btts(lh, la, max_goals=8):
    btts = 0.0
    for h in range(1, max_goals + 1):
        for a in range(1, max_goals + 1):
            btts += (
                poisson_prob(lh, h)
                * poisson_prob(la, a)
                * dixon_coles_correction(h, a, lh, la)
            )
    return btts


def poisson_random(lam):
    if lam <= 0:
        return 0
    L = math.exp(-lam)
    k, p = 0, 1.0
    while p > L:
        k += 1
        p *= random.random()
    return k - 1


def monte_carlo_btts(lh, la, simulations=10000):
    return sum(
        1
        for _ in range(simulations)
        if poisson_random(lh) > 0 and poisson_random(la) > 0
    ) / simulations


def calc_weighted_avg(values, decay=0.85):
    if not values:
        return 0
    total_w, weighted_sum, weight = 0, 0, 1.0
    for v in reversed(values):
        weighted_sum += v * weight
        total_w += weight
        weight *= decay
    return weighted_sum / total_w if total_w > 0 else 0


def calc_btts_stats(matches):
    if not matches:
        return 0.5, 0, 0
    total_w, btts_w, btts_count = 0, 0, 0
    for i, (gh, ga) in enumerate(matches):
        w = i + 1
        total_w += w
        if gh > 0 and ga > 0:
            btts_w += w
            btts_count += 1
    return btts_w / total_w, btts_count, len(matches)


def get_league_avg(stats):
    if not stats:
        return 1.35, 1.35
    try:
        return (
            float(stats["goals"]["for"]["average"]["total"]),
            float(stats["goals"]["against"]["average"]["total"]),
        )
    except:
        return 1.35, 1.35


def analyze_teams(id1, name1, id2, name2):
    key = f"{name1.lower()}_{name2.lower()}"
    now = datetime.now().timestamp()
    if key in analysis_cache:
        if now - analysis_cache[key]["time"] < CACHE_TIME:
            return analysis_cache[key]["data"]

    home_general = get_fixtures_by_team(id1, last=10)
    home_at_home = get_fixtures_by_team(id1, last=20, venue="home")[:10]
    away_general = get_fixtures_by_team(id2, last=10)
    away_at_away = get_fixtures_by_team(id2, last=20, venue="away")[:10]

    if not home_general or not away_general:
        return None

    h2h, h2h_recent_count, h2h_total = get_h2h_smart(id1, id2)

    league_id1, season1 = get_team_league(id1)
    league_id2, season2 = get_team_league(id2)
    stats1 = get_team_statistics(id1, league_id1, season1) if league_id1 else None
    stats2 = get_team_statistics(id2, league_id2, season2) if league_id2 else None
    rank1, form1 = (
        get_standings_form(id1, league_id1, season1) if league_id1 else (None, None)
    )
    rank2, form2 = (
        get_standings_form(id2, league_id2, season2) if league_id2 else (None, None)
    )

    season_rate1, s1_btts, s1_total, s1_label = get_season_btts(
        id1, league_id1, season1
    )
    season_rate2, s2_btts, s2_total, s2_label = get_season_btts(
        id2, league_id2, season2
    )

    avg1, _ = get_league_avg(stats1)
    avg2, _ = get_league_avg(stats2)
    league_avg = (avg1 + avg2) / 2

    home_fixtures = home_at_home or home_general
    away_fixtures = away_at_away or away_general

    home_scored   = [gh for gh, ga in home_fixtures]
    home_conceded = [ga for gh, ga in home_fixtures]
    away_scored   = [ga for gh, ga in away_fixtures]
    away_conceded = [gh for gh, ga in away_fixtures]

    home_attack  = calc_weighted_avg(home_scored)   / league_avg if league_avg > 0 else 1.0
    home_defense = calc_weighted_avg(home_conceded) / league_avg if league_avg > 0 else 1.0
    away_attack  = calc_weighted_avg(away_scored)   / league_avg if league_avg > 0 else 1.0
    away_defense = calc_weighted_avg(away_conceded) / league_avg if league_avg > 0 else 1.0

    lambda_home = max(0.2, min(home_attack * away_defense * league_avg * 1.08, 5.0))
    lambda_away = max(0.2, min(away_attack * home_defense * league_avg, 5.0))

    home_btts_rate, home_btts_count, home_total = calc_btts_stats(home_general)
    away_btts_rate, away_btts_count, away_total = calc_btts_stats(away_general)
    home_home_rate, _, _ = calc_btts_stats(home_at_home)
    away_away_rate, _, _ = calc_btts_stats(away_at_away)

    historical_btts = (
        home_home_rate * 1.5
        + away_away_rate * 1.5
        + home_btts_rate * 1.0
        + away_btts_rate * 1.0
    ) / 5.0

    # H2H — sadece son 3 yıl
    h2h_note = ""
    if h2h and h2h_recent_count >= 2:
        h2h_rate, h2h_btts_count, h2h_len = calc_btts_stats(h2h)
        historical_btts = historical_btts * 0.60 + h2h_rate * 0.40
        h2h_note = f"{h2h_btts_count}/{h2h_len}"
    elif h2h_total > 0 and h2h_recent_count == 0:
        h2h_note = "old"
    elif h2h_recent_count == 1:
        h2h_rate, h2h_btts_count, h2h_len = calc_btts_stats(h2h)
        historical_btts = historical_btts * 0.80 + h2h_rate * 0.20
        h2h_note = f"{h2h_btts_count}/{h2h_len}"
    else:
        h2h_note = "none"

    # Sezon KG entegrasyonu
    if season_rate1 is not None and season_rate2 is not None:
        season_avg = (season_rate1 + season_rate2) / 2
        historical_btts = historical_btts * 0.50 + season_avg * 0.50
    elif season_rate1 is not None:
        historical_btts = historical_btts * 0.70 + season_rate1 * 0.30
    elif season_rate2 is not None:
        historical_btts = historical_btts * 0.70 + season_rate2 * 0.30

    poisson_btts = dixon_coles_btts(lambda_home, lambda_away)
    mc_btts = monte_carlo_btts(lambda_home, lambda_away, 10000)

    form_bonus = 0.0
    for form in [form1, form2]:
        if form:
            last5 = form[-5:]
            scored = sum(1 for f in last5 if f in ["W", "D"])
            form_bonus += (scored / len(last5) - 0.5) * 0.05

    rank_bonus = 0.0
    if rank1 and rank2:
        avg_rank = (rank1 + rank2) / 2
        rank_bonus = 0.03 if avg_rank <= 5 else (-0.03 if avg_rank > 15 else 0.0)

    final = (
        historical_btts * 0.30
        + poisson_btts * 0.35
        + mc_btts * 0.35
    ) + form_bonus + rank_bonus
    final = max(0.05, min(0.95, final))

    # Güvenilirlik
    warnings = []
    if len(home_general) < 5:
        warnings.append("⚠️ Insufficient home team data")
    if len(away_general) < 5:
        warnings.append("⚠️ Insufficient away team data")
    if h2h_note == "none":
        warnings.append("⚠️ No H2H data found")
    elif h2h_note == "old":
        warnings.append("⚠️ H2H data older than 3 years — not used")
    elif h2h_recent_count < 2:
        warnings.append("⚠️ Limited recent H2H data")
    if lambda_home <= 0.3 and lambda_away <= 0.3:
        warnings.append("⚠️ Very low xG — data may be unreliable")
    if season_rate1 is None or season_rate2 is None:
        warnings.append("⚠️ Season statistics incomplete")
    if s1_total < 8 and s1_label and "prev" in s1_label:
        warnings.append(f"⚠️ {name1.split()[0]} season start — mixed data used")
    if s2_total < 8 and s2_label and "prev" in s2_label:
        warnings.append(f"⚠️ {name2.split()[0]} season start — mixed data used")

    if len(warnings) == 0:
        reliability = "🟢 High"
    elif len(warnings) == 1:
        reliability = "🟡 Medium"
    else:
        reliability = "🔴 Low — treat with caution"

    result = {
        "h": name1, "a": name2,
        "p": int(final * 100),
        "lh": round(lambda_home, 2),
        "la": round(lambda_away, 2),
        "hist":    int(historical_btts * 100),
        "poisson": int(poisson_btts * 100),
        "mc":      int(mc_btts * 100),
        "home_btts": f"{home_btts_count}/{home_total}",
        "away_btts": f"{away_btts_count}/{away_total}",
        "s1": int(season_rate1 * 100) if season_rate1 is not None else None,
        "s2": int(season_rate2 * 100) if season_rate2 is not None else None,
        "s1_label": s1_label,
        "s2_label": s2_label,
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
            r = safe_request(
                f"{API_URL}/fixtures?date={today}&league={league_id}&season={season}"
            )
            if not r:
                continue
            matches = r.get("response", [])
            if not matches:
                continue
            for m in matches:
                if m["fixture"]["status"]["short"] not in ["NS", "TBD"]:
                    continue
                try:
                    ko = datetime.fromisoformat(
                        m["fixture"]["date"].replace("Z", "+00:00")
                    )
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
            if (
                result
                and result["p"] >= COMBINE_THRESHOLD
                and result["reliability"] != "🔴 Low — treat with caution"
            ):
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
                    text="📋 Daily Combine\n\n❌ No matches found with %68+ confidence today.",
                )
            else:
                await app.bot.send_message(
                    chat_id=ADMIN_ID, text=format_combine(combine)
                )
        except Exception as e:
            print("Combine error:", e)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "⛔️ Access Denied.\n"
            "This bot is private and cannot be used by unauthorized users."
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
    await update.message.reply_text(
        "🔴 Bot paused. API requests stopped.\n\nUse /analyze to resume."
    )


async def combine_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔️ Access Denied.")
        return
    wait = await update.message.reply_text(
        "🛜 Scanning today's matches... This may take a minute."
    )
    try:
        combine = build_daily_combine()
        if not combine:
            await wait.edit_text(
                "❌ No matches found with %68+ confidence today."
            )
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
        await update.message.reply_text(
            "🔴 Bot is paused. Use /analyze to resume."
        )
        return ConversationHandler.END
    context.user_data["t1"] = update.message.text
    await update.message.reply_text("🚩 Away Team Name:")
    return AWAY_NAME


async def get_away(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_active:
        await update.message.reply_text(
            "🔴 Bot is paused. Use /analyze to resume."
        )
        return ConversationHandler.END

    t1 = context.user_data.get("t1", "")
    t2 = update.message.text

    wait = await update.message.reply_text("🛜 Analyzing...")
    result = get_match_analysis(t1, t2)

    if "error" in result:
        await wait.edit_text(
            f"❌ {result['error']}\n\n➡️ /analyze to try again."
        )
        return ConversationHandler.END

    await wait.delete()

    prob   = result["p"]
    icon   = "✅" if prob >= 50 else "⛔️"
    status = "BTTS YES" if prob >= 50 else "BTTS NO"

    # Sezon KG satırı
    h_name = result["h"].split()[0]
    a_name = result["a"].split()[0]
    if result.get("s1") is not None and result.get("s2") is not None:
        season_line = (
            f"📅 Season KG: {h_name} {result['s1']}% ({result['s1_label']})"
            f"  |  {a_name} {result['s2']}% ({result['s2_label']})\n"
        )
    elif result.get("s1") is not None:
        season_line = f"📅 Season KG: {h_name} {result['s1']}% ({result['s1_label']})\n"
    elif result.get("s2") is not None:
        season_line = f"📅 Season KG: {a_name} {result['s2']}% ({result['s2_label']})\n"
    else:
        season_line = ""

    # H2H satırı
    if result["h2h_note"] == "old":
        h2h_line = "🕐 H2H: Only old data (3+ years) — not used\n"
    elif result["h2h_note"] == "none":
        h2h_line = "🕐 H2H: No data\n"
    else:
        h2h_line = f"🤝 H2H (last 3y): {result['h2h_note']} BTTS\n"

    # Uyarılar
    warning_lines = ""
    if result.get("warnings"):
        warning_lines = "\n" + "\n".join(result["warnings"]) + "\n"

    report = (
        "📊 MATCH ANALYSIS\n\n"
        f"🏳 {result['h']}\n"
        f"🚩 {result['a']}\n\n"
        f"⚽ xG Home: {result['lh']}  |  Away: {result['la']}\n\n"
        f"📈 Historical:  {result['hist']}%\n"
        f"📐 Poisson/DC:  {result['poisson']}%\n"
        f"🎲 Monte Carlo: {result['mc']}%\n\n"
        f"⚽ Last 10 BTTS: 🏳 {result['home_btts']}  |  🚩 {result['away_btts']}\n"
        f"{season_line}"
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
            app = (
                Application.builder()
                .token(BOT_TOKEN)
                .post_init(post_init)
                .build()
            )

            conv = ConversationHandler(
                entry_points=[CommandHandler("analyze", analyze_cmd)],
                states={
                    HOME_NAME: [
                        CommandHandler("analyze", analyze_cmd),
                        CommandHandler("stop", stop_cmd),
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND, get_home
                        ),
                    ],
                    AWAY_NAME: [
                        CommandHandler("analyze", analyze_cmd),
                        CommandHandler("stop", stop_cmd),
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND, get_away
                        ),
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


Örnek çıktı:

📊 MATCH ANALYSIS

🏳 Arsenal
🚩 Chelsea

⚽ xG Home: 1.84  |  Away: 1.52

📈 Historical:  63%
📐 Poisson/DC:  71%
🎲 Monte Carlo: 69%

⚽ Last 10 BTTS: 🏳 7/10  |  🚩 6/10
📅 Season KG: Arsenal 61% (14/23)  |  Chelsea 57% (3/4+prev)
🤝 H2H (last 3y): 3/4 BTTS

📶 Reliability: 🟡 Medium

✅ BTTS YES
🎯 Final: 68%
