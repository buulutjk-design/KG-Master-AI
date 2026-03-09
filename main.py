import requests
import time
import math
import random
from datetime import datetime, date, timezone, timedelta
from collections import defaultdict
import asyncio
import json
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

BOT_TOKEN = "8663391761:AAFw-hfUEWSrKs7St7JG4Bfbrr2hK2HNp0Q"
ADMIN_ID = 8480843841
API_KEY = "7d7e4508cb4cfe8006ccc9422bb28b1d"
API_URL = "https://v3.football.api-sports.io"

analysis_cache = {}
CACHE_TIME = 43200
shown_auto = set()

MAJOR_LEAGUES = {
    39: "Premier League", 40: "Championship", 41: "League One", 42: "League Two",
    43: "National League", 45: "FA Cup", 48: "League Cup",
    140: "La Liga", 141: "Segunda Division", 142: "Copa del Rey", 143: "Primera RFEF",
    135: "Serie A", 136: "Serie B", 137: "Coppa Italia", 138: "Serie C",
    78: "Bundesliga", 79: "2. Bundesliga", 80: "3. Liga", 81: "DFB Pokal",
    61: "Ligue 1", 62: "Ligue 2", 63: "National", 66: "Coupe de France",
    203: "Süper Lig", 204: "1. Lig", 205: "2. Lig", 206: "3. Lig",
    88: "Eredivisie", 89: "Eerste Divisie",
    94: "Primeira Liga", 95: "Segunda Liga",
    144: "Jupiler Pro League", 145: "Eerste Nationale",
    179: "Scottish Premiership", 180: "Scottish Championship",
    181: "Scottish League One", 182: "Scottish League Two",
    235: "Premier League RU", 236: "FNL", 237: "PFL",
    218: "Bundesliga AT", 219: "2. Liga AT",
    207: "Super League CH", 208: "Challenge League",
    197: "Super League GR", 198: "Super League 2 GR",
    345: "Czech Liga", 346: "Czech FNL",
    106: "Ekstraklasa", 107: "I Liga PL",
    283: "Liga 1 RO", 284: "Liga 2 RO",
    210: "HNL", 211: "HNL 2",
    286: "Super Liga RS", 287: "Liga 2 RS",
    119: "Superliga DK", 120: "1. Division DK",
    103: "Eliteserien", 104: "1. Division NO", 105: "2. Division NO",
    113: "Allsvenskan", 114: "Superettan", 115: "Division 1",
    244: "Veikkausliiga", 245: "Ykkönen",
    333: "Premier League UA", 334: "Persha Liga UA",
    271: "OTP Bank Liga", 272: "Merkur Liga",
    332: "Super Liga SK", 322: "PrvaLiga",
    318: "Premier Liga BIH", 341: "Prva CFL",
    316: "Kategoria Superiore",
    172: "First League BG", 173: "Second League BG",
    164: "Úrvalsdeild", 165: "1. deild",
    357: "League of Ireland", 374: "NIFL Premiership",
    375: "Cymru Premier", 377: "A Lyga", 378: "Virsliga",
    379: "Meistriliiga", 380: "Vysshaya Liga", 381: "Divizia Nationala",
    383: "Prva Liga MKD", 382: "Superleague Kosovo",
    117: "National Division LUX", 356: "Premier League MT",
    392: "Gibraltar Premier Division", 387: "Faroe Islands Premier League",
    371: "Armenian Premier League", 372: "Erovnuli Liga",
    373: "Premier League AZ", 376: "Premier League KZ",
    307: "Saudi Pro League", 308: "Division 1 SA",
    435: "UAE Pro League", 350: "Stars League QAT",
    290: "Persian Gulf Pro League", 291: "Azadegan League",
    384: "Ligat ha'Al", 385: "Liga Leumit",
    285: "Jordan Pro League", 403: "Lebanon Premier League",
    406: "Iraqi Premier League", 343: "Bahrain Premier League",
    344: "Kuwait Premier League", 430: "Oman Professional League",
    98: "J1 League", 99: "J2 League", 100: "J3 League",
    292: "K League 1", 293: "K League 2",
    169: "Chinese Super League", 170: "China League One", 171: "China League Two",
    323: "Indian Super League", 324: "I-League",
    296: "Thai League 1", 297: "Thai League 2",
    313: "Liga 1 ID", 314: "Liga 2 ID",
    301: "Malaysia Super League", 304: "Singapore Premier League",
    302: "Vietnam V.League 1", 336: "Philippines Football League",
    305: "Hong Kong Premier League",
    188: "A-League", 189: "NPL Australia",
    288: "Premier Soccer League ZA", 233: "Egyptian Premier League",
    200: "Botola Pro MA", 201: "Ligue Pro TN",
    299: "CAF Champions League",
    370: "Nigeria Professional Football League",
    366: "Ghana Premier League", 362: "Ethiopian Premier League",
    363: "Kenyan Premier League", 369: "Zambia Super League",
    368: "Zimbabwe Premier Soccer League", 367: "Ugandan Premier League",
    386: "Ivory Coast Ligue 1", 388: "Cameroon Elite One",
    390: "Algeria Ligue Pro 1",
    253: "MLS", 254: "USL Championship", 321: "Canadian Premier League",
    262: "Liga MX", 263: "Liga de Expansion MX",
    309: "Liga Nacional GT", 312: "Liga Nacional HN",
    320: "Costa Rica Primera Division",
    71: "Serie A BR", 72: "Serie B BR", 73: "Serie C BR",
    128: "Liga Profesional AR", 129: "Primera Nacional AR",
    265: "Primera Division CL", 239: "Liga BetPlay CO",
    268: "Primera Division UY", 267: "Division Profesional PY",
    281: "Liga 1 PE", 240: "LigaPro EC", 269: "Liga FUTVE",
    242: "Primera Division BO",
    11: "Copa Libertadores", 13: "Copa Sudamericana",
    2: "Champions League", 3: "Europa League", 848: "Conference League",
    1: "World Cup", 9: "WC Qualification Europe",
    29: "WC Qualification S.America", 30: "WC Qualification Asia",
    31: "WC Qualification Africa", 32: "WC Qualification CONCACAF",
    4: "Euro Championship", 6: "Africa Cup of Nations",
    7: "CONCACAF Gold Cup", 10: "Copa America", 16: "UEFA Nations League",
    17: "AFC Asian Cup",
}


# ── HELPERS ───────────────────────────────────────────────────
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
    if r and r.get("response"):
        t = r["response"][0]["team"]
        return t["id"], t["name"]
    return None, None

def poisson_prob(lam, k):
    if k > 15: return 0.0
    return (math.exp(-lam) * (lam ** k)) / math.factorial(k)

def weighted_avg(values, decay=0.88):
    if not values: return 0.0
    total_w, ws, w = 0.0, 0.0, 1.0
    for v in reversed(values):
        ws += v * w
        total_w += w
        w *= decay
    return ws / total_w if total_w > 0 else 0.0


# ── VERİ ÇEKİMİ ───────────────────────────────────────────────
def get_last_matches(team_id, count=10):
    r = safe_request(f"{API_URL}/fixtures?team={team_id}&last={count}&status=FT")
    if not r: return []
    matches = []
    for m in r.get("response", []):
        gh = m["goals"]["home"]
        ga = m["goals"]["away"]
        if gh is None or ga is None: continue
        is_home = m["teams"]["home"]["id"] == team_id
        ht_h = m.get("score", {}).get("halftime", {}).get("home")
        ht_a = m.get("score", {}).get("halftime", {}).get("away")
        matches.append({
            "scored":   gh if is_home else ga,
            "conceded": ga if is_home else gh,
            "gh": gh, "ga": ga,
            "is_home": is_home,
            "ht_home": ht_h,
            "ht_away": ht_a,
        })
    return matches

def get_venue_matches(team_id, venue="home", count=8):
    r = safe_request(f"{API_URL}/fixtures?team={team_id}&last=25&status=FT")
    if not r: return []
    matches = []
    for m in r.get("response", []):
        is_home = m["teams"]["home"]["id"] == team_id
        if venue == "home" and not is_home: continue
        if venue == "away" and is_home: continue
        gh = m["goals"]["home"]
        ga = m["goals"]["away"]
        if gh is None or ga is None: continue
        ht_h = m.get("score", {}).get("halftime", {}).get("home")
        ht_a = m.get("score", {}).get("halftime", {}).get("away")
        matches.append({
            "scored":   gh if is_home else ga,
            "conceded": ga if is_home else gh,
            "gh": gh, "ga": ga,
            "ht_home": ht_h, "ht_away": ht_a,
        })
        if len(matches) >= count: break
    return matches

def get_h2h(id1, id2):
    r = safe_request(f"{API_URL}/fixtures/headtohead?h2h={id1}-{id2}&last=10")
    if not r: return [], 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=3*365)
    recent, total = [], 0
    for m in r.get("response", []):
        gh = m["goals"]["home"]
        ga = m["goals"]["away"]
        if gh is None or ga is None: continue
        total += 1
        try:
            md = datetime.fromisoformat(m["fixture"]["date"].replace("Z", "+00:00"))
            if md >= cutoff:
                ht_h = m.get("score", {}).get("halftime", {}).get("home")
                ht_a = m.get("score", {}).get("halftime", {}).get("away")
                recent.append({"gh": gh, "ga": ga, "ht_home": ht_h, "ht_away": ht_a})
        except:
            pass
    return recent, total


# ── GERÇEK İY/MS VERİSİ ───────────────────────────────────────
def get_real_htft_stats(matches, team_id_check=None, venue=None):
    """
    Gerçek maçlardan İY/MS istatistikleri çıkar
    Returns: {
        "2/1": count, "1/2": count, "1/1": count, "2/2": count,
        "X/1": count, "X/2": count, "X/X": count, "1/X": count, "2/X": count,
        "total": count,
        "comeback_home": (geride iken kazanma oranı),
        "comeback_away": (geride iken kazanma oranı),
        "ht_lead_lost_home": (önde iken kaybetme oranı),
        "ht_lead_lost_away": (önde iken kaybetme oranı),
        "second_half_scored_avg": ort,
        "second_half_conceded_avg": ort,
    }
    """
    stats = defaultdict(int)
    second_half_scored = []
    second_half_conceded = []

    for m in matches:
        gh = m.get("gh")
        ga = m.get("ga")
        ht_h = m.get("ht_home")
        ht_a = m.get("ht_away")
        is_home = m.get("is_home", True)

        if gh is None or ga is None: continue
        if ht_h is None or ht_a is None: continue

        # İY durumu
        if ht_h > ht_a:   ht = "1"
        elif ht_h < ht_a: ht = "2"
        else:              ht = "X"

        # MS durumu
        if gh > ga:   ft = "1"
        elif gh < ga: ft = "2"
        else:         ft = "X"

        stats[f"{ht}/{ft}"] += 1
        stats["total"] += 1

        # 2. yarı gol
        sh_home = gh - ht_h
        sh_away = ga - ht_a
        if is_home:
            second_half_scored.append(sh_home)
            second_half_conceded.append(sh_away)
        else:
            second_half_scored.append(sh_away)
            second_half_conceded.append(sh_home)

    total = stats["total"] if stats["total"] > 0 else 1

    return {
        "2/1": stats["2/1"] / total,
        "1/2": stats["1/2"] / total,
        "1/1": stats["1/1"] / total,
        "2/2": stats["2/2"] / total,
        "X/1": stats["X/1"] / total,
        "X/2": stats["X/2"] / total,
        "X/X": stats["X/X"] / total,
        "1/X": stats["1/X"] / total,
        "2/X": stats["2/X"] / total,
        "total_matches": stats["total"],
        "sh_scored_avg":   weighted_avg(second_half_scored)   if second_half_scored   else 0.0,
        "sh_conceded_avg": weighted_avg(second_half_conceded) if second_half_conceded else 0.0,
    }


# ── POISSON İY/MS ─────────────────────────────────────────────
def poisson_htft(lh, la):
    lh_ht = lh * 0.45
    la_ht = la * 0.45
    lh_2h = lh * 0.55
    la_2h = la * 0.55

    probs = defaultdict(float)
    for h_ht in range(6):
        for a_ht in range(6):
            p_ht = poisson_prob(lh_ht, h_ht) * poisson_prob(la_ht, a_ht)
            if p_ht < 0.0003: continue
            ht = "1" if h_ht > a_ht else ("2" if h_ht < a_ht else "X")
            for h_2h in range(6):
                for a_2h in range(6):
                    p_2h = poisson_prob(lh_2h, h_2h) * poisson_prob(la_2h, a_2h)
                    if p_2h < 0.0003: continue
                    h_ft = h_ht + h_2h
                    a_ft = a_ht + a_2h
                    ft = "1" if h_ft > a_ft else ("2" if h_ft < a_ft else "X")
                    probs[f"{ht}/{ft}"] += p_ht * p_2h
    return probs


# ── ANA ANALİZ ────────────────────────────────────────────────
def calc_lambda(home_gen, away_gen, home_venue, away_venue):
    hsg = weighted_avg([m["scored"]   for m in home_gen])
    hcg = weighted_avg([m["conceded"] for m in home_gen])
    asg = weighted_avg([m["scored"]   for m in away_gen])
    acg = weighted_avg([m["conceded"] for m in away_gen])

    hsv = weighted_avg([m["scored"]   for m in home_venue]) if home_venue else hsg
    hcv = weighted_avg([m["conceded"] for m in home_venue]) if home_venue else hcg
    asv = weighted_avg([m["scored"]   for m in away_venue]) if away_venue else asg
    acv = weighted_avg([m["conceded"] for m in away_venue]) if away_venue else acg

    hs = hsv * 0.6 + hsg * 0.4
    hc = hcv * 0.6 + hcg * 0.4
    as_ = asv * 0.6 + asg * 0.4
    ac = acv * 0.6 + acg * 0.4

    lh = ((hs + ac) / 2) * 1.08
    la = (as_ + hc) / 2
    return max(0.15, min(lh, 5.0)), max(0.15, min(la, 5.0))

def analyze_htft(id1, name1, id2, name2):
    key = f"htft_{name1.lower()}_{name2.lower()}"
    now = datetime.now().timestamp()
    if key in analysis_cache:
        if now - analysis_cache[key]["time"] < CACHE_TIME:
            return analysis_cache[key]["data"]

    # Veri çek
    home_gen   = get_last_matches(id1, 10)
    away_gen   = get_last_matches(id2, 10)
    home_venue = get_venue_matches(id1, "home", 8)
    away_venue = get_venue_matches(id2, "away", 8)

    if not home_gen or not away_gen:
        return None

    # Lambda
    lh, la = calc_lambda(home_gen, away_gen, home_venue, away_venue)

    # Poisson İY/MS
    poisson_probs = poisson_htft(lh, la)

    # Gerçek İY/MS istatistikleri
    home_stats = get_real_htft_stats(home_gen)
    away_stats = get_real_htft_stats(away_gen)
    home_venue_stats = get_real_htft_stats(home_venue) if home_venue else home_stats
    away_venue_stats = get_real_htft_stats(away_venue) if away_venue else away_stats

    # H2H
    h2h, h2h_total = get_h2h(id1, id2)
    h2h_stats = get_real_htft_stats(h2h) if len(h2h) >= 3 else None

    # Her kombinasyon için final olasılık hesapla
    # Ağırlıklar: Poisson %35 + Ev venue %25 + Dep venue %25 + H2H %15
    all_combos = ["1/1", "1/X", "1/2", "X/1", "X/X", "X/2", "2/1", "2/X", "2/2"]
    final_probs = {}

    for combo in all_combos:
        p_poisson = poisson_probs.get(combo, 0.0)

        # Ev venue (ev sahibinin bu maçtaki home istatistiği)
        p_home_v = home_venue_stats.get(combo, 0.0)
        # Dep venue
        p_away_v = away_venue_stats.get(combo, 0.0)
        # Genel
        p_home_g = home_stats.get(combo, 0.0)
        p_away_g = away_stats.get(combo, 0.0)
        p_real = (p_home_v * 0.35 + p_away_v * 0.35 + p_home_g * 0.15 + p_away_g * 0.15)

        if h2h_stats:
            p_h2h = h2h_stats.get(combo, 0.0)
            final = p_poisson * 0.35 + p_real * 0.50 + p_h2h * 0.15
        else:
            final = p_poisson * 0.40 + p_real * 0.60

        final_probs[combo] = final

    # Normalize
    total_p = sum(final_probs.values())
    if total_p > 0:
        final_probs = {k: v / total_p for k, v in final_probs.items()}

    # Sıralı liste
    sorted_probs = sorted(final_probs.items(), key=lambda x: x[1], reverse=True)

    # 2/1 ve 1/2 özel skor
    comeback_21 = (
        home_venue_stats.get("2/1", 0) * 0.4 +
        away_venue_stats.get("2/1", 0) * 0.4 +
        (h2h_stats.get("2/1", 0) if h2h_stats else 0) * 0.2
    )
    comeback_12 = (
        home_venue_stats.get("1/2", 0) * 0.4 +
        away_venue_stats.get("1/2", 0) * 0.4 +
        (h2h_stats.get("1/2", 0) if h2h_stats else 0) * 0.2
    )

    # 2. yarı gol avantajı
    home_sh_advantage = home_venue_stats["sh_scored_avg"] - home_venue_stats["sh_conceded_avg"]
    away_sh_advantage = away_venue_stats["sh_scored_avg"] - away_venue_stats["sh_conceded_avg"]

    # 2/1 güven skoru: dep 2y zayıf + ev 2y güçlü
    score_21 = final_probs.get("2/1", 0) * 0.5 + comeback_21 * 0.3 + max(0, home_sh_advantage) * 0.1 + max(0, -away_sh_advantage) * 0.1
    score_12 = final_probs.get("1/2", 0) * 0.5 + comeback_12 * 0.3 + max(0, away_sh_advantage) * 0.1 + max(0, -home_sh_advantage) * 0.1

    # Güvenilirlik
    warns = []
    if home_stats["total_matches"] < 5: warns.append("⚠️ Insufficient home data")
    if away_stats["total_matches"] < 5: warns.append("⚠️ Insufficient away data")
    if h2h_total < 3: warns.append("⚠️ Limited H2H data")

    reliability = "🟢 High" if len(warns) == 0 else ("🟡 Medium" if len(warns) == 1 else "🔴 Low")

    result = {
        "h": name1, "a": name2,
        "lh": round(lh, 2), "la": round(la, 2),
        "sorted_probs": sorted_probs,
        "final_probs": final_probs,
        "score_21": round(score_21 * 100, 1),
        "score_12": round(score_12 * 100, 1),
        "prob_21": round(final_probs.get("2/1", 0) * 100, 1),
        "prob_12": round(final_probs.get("1/2", 0) * 100, 1),
        "home_sh_adv": round(home_sh_advantage, 2),
        "away_sh_adv": round(away_sh_advantage, 2),
        "home_real_21": round(home_venue_stats.get("2/1", 0) * 100, 1),
        "away_real_21": round(away_venue_stats.get("2/1", 0) * 100, 1),
        "home_real_12": round(home_venue_stats.get("1/2", 0) * 100, 1),
        "away_real_12": round(away_venue_stats.get("1/2", 0) * 100, 1),
        "h2h_count": h2h_total,
        "warns": warns,
        "reliability": reliability,
    }
    analysis_cache[key] = {"data": result, "time": now}
    return result

def htft_desc(code):
    return {
        "1/1": "Home Lead → Home Win",
        "X/1": "Draw HT → Home Win",
        "X/2": "Draw HT → Away Win",
        "2/2": "Away Lead → Away Win",
        "X/X": "Draw → Draw",
        "2/1": "Away Lead → Home Win ⚡",
        "1/X": "Home Lead → Draw",
        "1/2": "Home Lead → Away Win ⚡",
        "2/X": "Away Lead → Draw",
    }.get(code, code)

def format_htft_analysis(result, league="", kickoff=""):
    top5 = result["sorted_probs"][:5]

    top_lines = ""
    for i, (code, prob) in enumerate(top5, 1):
        star = " 🔥" if code in ["2/1", "1/2"] else ""
        top_lines += f"   {i}. {code} — {prob*100:.1f}%  ({htft_desc(code)}){star}\n"

    p21 = result["prob_21"]
    p12 = result["prob_12"]
    s21 = result["score_21"]
    s12 = result["score_12"]

    # 2/1 değerlendirme
    if s21 >= 12:
        verdict_21 = "✅ STRONG PICK"
    elif s21 >= 8:
        verdict_21 = "⚠️ POSSIBLE"
    else:
        verdict_21 = "❌ LOW CHANCE"

    # 1/2 değerlendirme
    if s12 >= 12:
        verdict_12 = "✅ STRONG PICK"
    elif s12 >= 8:
        verdict_12 = "⚠️ POSSIBLE"
    else:
        verdict_12 = "❌ LOW CHANCE"

    warn_lines = ("\n" + "\n".join(result["warns"]) + "\n") if result["warns"] else ""
    league_line = f"🏆 {league}\n" if league else ""
    ko_line = f"⏰ {kickoff}\n" if kickoff else ""

    return (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "    ⚽ HT/FT ANALYSIS\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{league_line}"
        f"🏳 {result['h']}\n"
        f"🚩 {result['a']}\n"
        f"{ko_line}\n"
        f"⚡ xG: Home {result['lh']}  |  Away {result['la']}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "    📊 TOP 5 HT/FT\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{top_lines}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "    🔀 SURPRISE RESULTS\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ 2/1 (Away→Home)\n"
        f"   Model Prob:    {p21}%\n"
        f"   Confidence:   {s21}%\n"
        f"   Home real 2/1: {result['home_real_21']}%\n"
        f"   Away real 2/1: {result['away_real_21']}%\n"
        f"   Home 2H adv:   {result['home_sh_adv']:+.2f}\n"
        f"   👉 {verdict_21}\n\n"
        f"⚡ 1/2 (Home→Away)\n"
        f"   Model Prob:    {p12}%\n"
        f"   Confidence:   {s12}%\n"
        f"   Home real 1/2: {result['home_real_12']}%\n"
        f"   Away real 1/2: {result['away_real_12']}%\n"
        f"   Away 2H adv:   {result['away_sh_adv']:+.2f}\n"
        f"   👉 {verdict_12}\n\n"
        f"{warn_lines}"
        f"📶 Reliability: {result['reliability']}\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )


# ── BÜLTEN ────────────────────────────────────────────────────
def get_todays_fixtures():
    today = date.today().strftime("%Y-%m-%d")
    current_year = datetime.now().year
    all_fixtures = []
    seen_ids = set()
    for league_id, league_name in MAJOR_LEAGUES.items():
        for season in [current_year, current_year - 1]:
            r = safe_request(f"{API_URL}/fixtures?date={today}&league={league_id}&season={season}")
            if not r: continue
            matches = r.get("response", [])
            if not matches: continue
            for m in matches:
                fid = m["fixture"]["id"]
                if fid in seen_ids: continue
                if m["fixture"]["status"]["short"] not in ["NS", "TBD"]: continue
                seen_ids.add(fid)
                all_fixtures.append({
                    "league":    league_name,
                    "home_id":   m["teams"]["home"]["id"],
                    "home_name": m["teams"]["home"]["name"],
                    "away_id":   m["teams"]["away"]["id"],
                    "away_name": m["teams"]["away"]["name"],
                    "kickoff":   m["fixture"]["date"],
                })
            break
        time.sleep(0.25)
    return all_fixtures

def find_best_surprise_picks(fixtures, min_score=8.0):
    """Bültendeki tüm maçları tara, en iyi 2/1 ve 1/2 maçları bul"""
    picks_21 = []
    picks_12 = []

    for fix in fixtures:
        result = analyze_htft(
            fix["home_id"], fix["home_name"],
            fix["away_id"], fix["away_name"],
        )
        if not result: continue
        if result["reliability"] == "🔴 Low": continue

        if result["score_21"] >= min_score:
            picks_21.append((fix, result, result["score_21"]))
        if result["score_12"] >= min_score:
            picks_12.append((fix, result, result["score_12"]))
        time.sleep(0.15)

    picks_21.sort(key=lambda x: x[2], reverse=True)
    picks_12.sort(key=lambda x: x[2], reverse=True)
    return picks_21[:3], picks_12[:3]


# ── TELEGRAM KOMUTLARI ────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔️ Access Denied.")
        return
    await update.message.reply_text(
        "👋 Welcome to HT/FT Analysis Bot!\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 Commands:\n\n"
        "⚽ /analyze — Manual HT/FT analysis\n"
        "   Enter home & away team names\n"
        "   Get full HT/FT breakdown\n"
        "   Including 2/1 & 1/2 confidence\n\n"
        "🤖 /autoanaliz — Auto scan today's bulletin\n"
        "   Scans all world leagues\n"
        "   Finds best 2/1 & 1/2 picks\n"
        "   Shows top matches with highest\n"
        "   surprise result probability\n\n"
        "🔴 /stop — Pause the bot\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 Focus: 2/1 & 1/2 Results\n"
        "📊 Real data + Poisson model\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )

HOME_NAME, AWAY_NAME = range(2)
bot_active = True

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
        await update.message.reply_text("🔴 Bot paused. Use /analyze to resume.")
        return ConversationHandler.END
    context.user_data["t1"] = update.message.text
    await update.message.reply_text("🚩 Away Team Name:")
    return AWAY_NAME

async def get_away(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_active:
        await update.message.reply_text("🔴 Bot paused.")
        return ConversationHandler.END

    t1 = context.user_data.get("t1", "")
    t2 = update.message.text
    wait = await update.message.reply_text("⏳ Analyzing...")

    id1, name1 = search_team_id(t1)
    id2, name2 = search_team_id(t2)

    if not id1:
        await wait.edit_text(f"❌ Team not found: '{t1}'\n\n➡️ /analyze to try again.")
        return ConversationHandler.END
    if not id2:
        await wait.edit_text(f"❌ Team not found: '{t2}'\n\n➡️ /analyze to try again.")
        return ConversationHandler.END

    result = analyze_htft(id1, name1, id2, name2)
    if not result:
        await wait.edit_text("❌ No data found.\n\n➡️ /analyze to try again.")
        return ConversationHandler.END

    await wait.delete()
    await update.message.reply_text(format_htft_analysis(result))
    return ConversationHandler.END

async def autoanaliz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔️ Access Denied.")
        return

    wait = await update.message.reply_text(
        "🛜 Scanning today's bulletin...\n"
        "Looking for best 2/1 & 1/2 picks.\n"
        "This may take a few minutes."
    )

    try:
        fixtures = get_todays_fixtures()
        if not fixtures:
            await wait.edit_text("❌ No matches found in today's bulletin.")
            return

        total = len(fixtures)
        await wait.edit_text(f"🛜 Scanning {total} matches...\nAnalyzing for 2/1 & 1/2 picks.")

        picks_21, picks_12 = find_best_surprise_picks(fixtures, min_score=6.0)

        if not picks_21 and not picks_12:
            await wait.edit_text(
                "❌ No strong 2/1 or 1/2 picks found today.\n\n"
                "➡️ Try /autoanaliz again later or use /analyze for manual."
            )
            return

        msg = (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "  🤖 AUTO ANALYSIS RESULTS\n"
            f"  📅 {date.today().strftime('%d.%m.%Y')}\n"
            f"  📊 Scanned: {total} matches\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        if picks_21:
            msg += "⚡ BEST 2/1 PICKS (Away Lead → Home Win)\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            for fix, result, score in picks_21:
                try:
                    ko = datetime.fromisoformat(fix["kickoff"].replace("Z", "+00:00"))
                    ko_str = ko.strftime("%H:%M")
                except:
                    ko_str = "?"
                verdict = "✅ STRONG" if score >= 12 else "⚠️ POSSIBLE"
                msg += (
                    f"🏆 {fix['league']}\n"
                    f"🏳 {result['h']} vs 🚩 {result['a']}\n"
                    f"⏰ {ko_str}\n"
                    f"📊 2/1 Prob: {result['prob_21']}%  |  Confidence: {score}%\n"
                    f"👉 {verdict}\n\n"
                )

        if picks_12:
            msg += "⚡ BEST 1/2 PICKS (Home Lead → Away Win)\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            for fix, result, score in picks_12:
                try:
                    ko = datetime.fromisoformat(fix["kickoff"].replace("Z", "+00:00"))
                    ko_str = ko.strftime("%H:%M")
                except:
                    ko_str = "?"
                verdict = "✅ STRONG" if score >= 12 else "⚠️ POSSIBLE"
                msg += (
                    f"🏆 {fix['league']}\n"
                    f"🏳 {result['h']} vs 🚩 {result['a']}\n"
                    f"⏰ {ko_str}\n"
                    f"📊 1/2 Prob: {result['prob_12']}%  |  Confidence: {score}%\n"
                    f"👉 {verdict}\n\n"
                )

        msg += "⚠️ Always bet responsibly."
        await wait.edit_text(msg)

    except Exception as e:
        await wait.edit_text(f"❌ Error: {e}")

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_active
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔️ Access Denied.")
        return
    bot_active = False
    await update.message.reply_text("🔴 Bot paused.\n\nUse /analyze to resume.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

def run_bot():
    while True:
        try:
            app = Application.builder().token(BOT_TOKEN).build()

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
            app.add_handler(CommandHandler("autoanaliz", autoanaliz_cmd))
            app.add_handler(conv)

            print("HT/FT BOT RUNNING")
            app.run_polling(drop_pending_updates=True)

        except Exception as e:
            print("BOT RESTARTING:", e)
            time.sleep(5)

run_bot()
