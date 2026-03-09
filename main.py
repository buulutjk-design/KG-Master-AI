import requests
import time
import math
import random
from datetime import datetime, date, timezone, timedelta
from collections import defaultdict
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

BOT_TOKEN = "7963130491:AAHCKiU9DvUv5FUuhlbadgaqTtj00X_lfG4"
ADMIN_ID = 8480843841
API_KEY = "0c0c1ad20573b309924dd3d7b1bc3e62"
API_URL = "https://v3.football.api-sports.io"

HOME_NAME, AWAY_NAME = range(2)
analysis_cache = {}
CACHE_TIME = 43200
bot_active = True
shown_auto = set()
CONFIDENCE_THRESHOLD = 70

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
    210: "HNL", 286: "Super Liga RS",
    119: "Superliga DK", 120: "1. Division DK",
    103: "Eliteserien", 104: "1. Division NO",
    113: "Allsvenskan", 114: "Superettan",
    244: "Veikkausliiga", 333: "Premier League UA",
    271: "OTP Bank Liga", 332: "Super Liga SK",
    322: "PrvaLiga", 318: "Premier Liga BIH",
    316: "Kategoria Superiore", 172: "First League BG",
    164: "Úrvalsdeild", 357: "League of Ireland",
    374: "NIFL Premiership", 375: "Cymru Premier",
    377: "A Lyga", 378: "Virsliga", 379: "Meistriliiga",
    380: "Vysshaya Liga", 381: "Divizia Nationala",
    383: "Prva Liga MKD", 382: "Superleague Kosovo",
    117: "National Division LUX", 356: "Premier League MT",
    372: "Erovnuli Liga", 373: "Premier League AZ",
    376: "Premier League KZ", 371: "Armenian Premier League",
    307: "Saudi Pro League", 435: "UAE Pro League",
    350: "Stars League QAT", 290: "Persian Gulf Pro League",
    384: "Ligat ha'Al", 285: "Jordan Pro League",
    406: "Iraqi Premier League", 343: "Bahrain Premier League",
    344: "Kuwait Premier League", 430: "Oman Professional League",
    98: "J1 League", 99: "J2 League", 100: "J3 League",
    292: "K League 1", 293: "K League 2",
    169: "Chinese Super League", 170: "China League One",
    323: "Indian Super League", 296: "Thai League 1",
    313: "Liga 1 ID", 301: "Malaysia Super League",
    304: "Singapore Premier League", 302: "Vietnam V.League 1",
    188: "A-League",
    288: "Premier Soccer League ZA", 233: "Egyptian Premier League",
    200: "Botola Pro MA", 201: "Ligue Pro TN",
    370: "Nigeria Professional Football League",
    366: "Ghana Premier League", 386: "Ivory Coast Ligue 1",
    390: "Algeria Ligue Pro 1",
    253: "MLS", 254: "USL Championship", 321: "Canadian Premier League",
    262: "Liga MX", 263: "Liga de Expansion MX",
    71: "Serie A BR", 72: "Serie B BR", 73: "Serie C BR",
    128: "Liga Profesional AR", 129: "Primera Nacional AR",
    265: "Primera Division CL", 239: "Liga BetPlay CO",
    268: "Primera Division UY", 281: "Liga 1 PE",
    240: "LigaPro EC", 269: "Liga FUTVE",
    11: "Copa Libertadores", 13: "Copa Sudamericana",
    2: "Champions League", 3: "Europa League", 848: "Conference League",
    1: "World Cup", 9: "WC Qualification Europe",
    4: "Euro Championship", 10: "Copa America",
    16: "UEFA Nations League",
}

TURKISH_TEAMS = {
    "galatasaray": "Galatasaray", "fenerbahce": "Fenerbahce", "fenerbahçe": "Fenerbahce",
    "besiktas": "Besiktas", "beşiktaş": "Besiktas", "trabzonspor": "Trabzonspor",
    "basaksehir": "Istanbul Basaksehir", "başakşehir": "Istanbul Basaksehir",
    "kasimpasa": "Kasimpasa", "kasımpaşa": "Kasimpasa", "konyaspor": "Konyaspor",
    "sivasspor": "Sivasspor", "antalyaspor": "Antalyaspor", "alanyaspor": "Alanyaspor",
    "kayserispor": "Kayserispor", "gaziantep": "Gaziantep FK",
    "adana demirspor": "Adana Demirspor", "rizespor": "Rizespor",
    "samsunspor": "Samsunspor", "ankaragucu": "Ankaragucu",
    "eyupspor": "Eyupspor", "goztepe": "Goztepe",
}


# ── HELPERS ───────────────────────────────────────────────────
def normalize(text):
    tr = "çÇğĞıİöÖşŞüÜ"
    en = "cCgGiIoOsSuU"
    for t, e in zip(tr, en):
        text = text.replace(t, e)
    return text

def resolve_team(name):
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
    resolved = resolve_team(team_name)
    for name in [resolved, normalize(resolved)]:
        r = safe_request(f"{API_URL}/teams?search={name}")
        if r and r.get("response"):
            t = r["response"][0]["team"]
            return t["id"], t["name"]
    return None, None


# ── VERİ ÇEKİMİ ───────────────────────────────────────────────
def get_last6(team_id):
    """Son 6 maç — genel"""
    r = safe_request(f"{API_URL}/fixtures?team={team_id}&last=6&status=FT")
    if not r:
        return []
    matches = []
    for m in r.get("response", []):
        gh = m["goals"]["home"]
        ga = m["goals"]["away"]
        if gh is None or ga is None:
            continue
        is_home = m["teams"]["home"]["id"] == team_id
        ht_h = m.get("score", {}).get("halftime", {}).get("home") or 0
        ht_a = m.get("score", {}).get("halftime", {}).get("away") or 0
        matches.append({
            "scored":   gh if is_home else ga,
            "conceded": ga if is_home else gh,
            "gh": gh, "ga": ga,
            "is_home": is_home,
            "ht_home": ht_h, "ht_away": ht_a,
            "ht_scored":   ht_h if is_home else ht_a,
            "ht_conceded": ht_a if is_home else ht_h,
            "sh_scored":   (gh - ht_h) if is_home else (ga - ht_a),
            "sh_conceded": (ga - ht_a) if is_home else (gh - ht_h),
        })
    return matches

def get_venue6(team_id, venue="home"):
    """Son 6 iç/dış saha maçı"""
    r = safe_request(f"{API_URL}/fixtures?team={team_id}&last=20&status=FT")
    if not r:
        return []
    matches = []
    for m in r.get("response", []):
        is_home = m["teams"]["home"]["id"] == team_id
        if venue == "home" and not is_home:
            continue
        if venue == "away" and is_home:
            continue
        gh = m["goals"]["home"]
        ga = m["goals"]["away"]
        if gh is None or ga is None:
            continue
        ht_h = m.get("score", {}).get("halftime", {}).get("home") or 0
        ht_a = m.get("score", {}).get("halftime", {}).get("away") or 0
        matches.append({
            "scored":    gh if is_home else ga,
            "conceded":  ga if is_home else gh,
            "gh": gh, "ga": ga,
            "ht_scored":   ht_h if is_home else ht_a,
            "ht_conceded": ht_a if is_home else ht_h,
            "sh_scored":   (gh - ht_h) if is_home else (ga - ht_a),
            "sh_conceded": (ga - ht_a) if is_home else (gh - ht_h),
        })
        if len(matches) >= 6:
            break
    return matches

def get_fixtures_with_stats(team_id, last=6):
    """Fixture istatistikleri — şutlar, kornerler, xG"""
    r = safe_request(f"{API_URL}/fixtures?team={team_id}&last={last}&status=FT")
    if not r:
        return []
    fixture_ids = [m["fixture"]["id"] for m in r.get("response", [])]

    stats_list = []
    for fid in fixture_ids:
        rs = safe_request(f"{API_URL}/fixtures/statistics?fixture={fid}&team={team_id}")
        if not rs or not rs.get("response"):
            continue
        for team_stat in rs["response"]:
            if team_stat["team"]["id"] != team_id:
                continue
            st = {s["type"]: s["value"] for s in team_stat.get("statistics", [])}
            shots_on  = _parse_stat(st.get("Shots on Goal"))
            shots_off = _parse_stat(st.get("Shots off Goal"))
            shots_tot = _parse_stat(st.get("Total Shots"))
            corners   = _parse_stat(st.get("Corner Kicks"))
            xg        = _parse_stat(st.get("expected_goals") or st.get("xG") or st.get("Expected Goals"))
            stats_list.append({
                "shots_on":  shots_on,
                "shots_off": shots_off,
                "shots_tot": shots_tot,
                "corners":   corners,
                "xg":        xg,
            })
        time.sleep(0.1)
    return stats_list

def _parse_stat(val):
    if val is None:
        return 0.0
    try:
        return float(str(val).replace("%", ""))
    except:
        return 0.0

def get_h2h_2025(id1, id2):
    """H2H sadece 2025 sonrası"""
    r = safe_request(f"{API_URL}/fixtures/headtohead?h2h={id1}-{id2}&last=10")
    if not r:
        return []
    cutoff = datetime(2025, 1, 1, tzinfo=timezone.utc)
    matches = []
    for m in r.get("response", []):
        gh = m["goals"]["home"]
        ga = m["goals"]["away"]
        if gh is None or ga is None:
            continue
        try:
            md = datetime.fromisoformat(m["fixture"]["date"].replace("Z", "+00:00"))
            if md >= cutoff:
                ht_h = m.get("score", {}).get("halftime", {}).get("home") or 0
                ht_a = m.get("score", {}).get("halftime", {}).get("away") or 0
                matches.append({
                    "gh": gh, "ga": ga,
                    "total": gh + ga,
                    "ht_total": ht_h + ht_a,
                    "sh_total": (gh + ga) - (ht_h + ht_a),
                })
        except:
            pass
    return matches


# ── MATEMATİKSEL MODEL ────────────────────────────────────────
def poisson_prob(lam, k):
    if k > 15:
        return 0.0
    return (math.exp(-lam) * (lam ** k)) / math.factorial(k)

def weighted_avg(values, decay=0.88):
    if not values:
        return 0.0
    total_w, ws, w = 0.0, 0.0, 1.0
    for v in reversed(values):
        ws += v * w
        total_w += w
        w *= decay
    return ws / total_w if total_w > 0 else 0.0

def over_prob_poisson(lam_total, threshold):
    k_max = math.floor(threshold)
    p_under = sum(poisson_prob(lam_total, k) for k in range(k_max + 1))
    return max(0.0, min(1.0, 1 - p_under))

def dixon_coles_tau(h, a, lh, la, rho=-0.1):
    if h == 0 and a == 0: return 1 - lh * la * rho
    elif h == 0 and a == 1: return 1 + lh * rho
    elif h == 1 and a == 0: return 1 + la * rho
    elif h == 1 and a == 1: return 1 - rho
    return 1.0

def over_prob_dixon_coles(lh, la, threshold=2.5):
    """Dixon-Coles düzeltmeli üst olasılığı"""
    p_under = 0.0
    k_max = math.floor(threshold)
    for h in range(k_max + 2):
        for a in range(k_max + 2):
            if h + a > k_max:
                continue
            p = poisson_prob(lh, h) * poisson_prob(la, a) * dixon_coles_tau(h, a, lh, la)
            p_under += p
    return max(0.0, min(1.0, 1 - p_under))

def monte_carlo_ou(lh, la, sims=10000):
    """Monte Carlo — 1.5 ve 2.5 üst"""
    def sample(lam):
        L = math.exp(-lam)
        k, p = 0, 1.0
        while p > L:
            k += 1
            p *= random.random()
        return k - 1

    o15 = o25 = 0
    for _ in range(sims):
        h = sample(lh)
        a = sample(la)
        t = h + a
        if t > 1: o15 += 1
        if t > 2: o25 += 1
    return o15 / sims, o25 / sims

def calc_lambda_advanced(gen6, venue6, stats):
    """
    Gelişmiş lambda:
    - Son 6 maç genel ağırlıklı
    - İç/dış saha spesifik
    - xG düzeltmesi
    - İY/2Y gol dağılımı
    """
    # Genel ağırlıklı
    gen_scored   = weighted_avg([m["scored"]   for m in gen6])
    gen_conceded = weighted_avg([m["conceded"] for m in gen6])

    # Venue spesifik
    ven_scored   = weighted_avg([m["scored"]   for m in venue6]) if venue6 else gen_scored
    ven_conceded = weighted_avg([m["conceded"] for m in venue6]) if venue6 else gen_conceded

    # Karışım %65 venue + %35 genel
    scored   = ven_scored   * 0.65 + gen_scored   * 0.35
    conceded = ven_conceded * 0.65 + gen_conceded * 0.35

    # xG düzeltmesi
    if stats:
        xg_avg = weighted_avg([s["xg"] for s in stats if s["xg"] > 0])
        if xg_avg > 0:
            # xG ile gerçek gol arasındaki farkı hafifçe dahil et
            scored = scored * 0.75 + xg_avg * 0.25

    # İY/2Y gol dağılımı
    ht_scored_avg = weighted_avg([m["ht_scored"]   for m in gen6]) if gen6 else 0
    sh_scored_avg = weighted_avg([m["sh_scored"]   for m in gen6]) if gen6 else 0

    return scored, conceded, ht_scored_avg, sh_scored_avg


# ── ANA ANALİZ ────────────────────────────────────────────────
def analyze_teams(id1, name1, id2, name2):
    key = f"ou_{name1.lower()}_{name2.lower()}"
    now = datetime.now().timestamp()
    if key in analysis_cache:
        if now - analysis_cache[key]["time"] < CACHE_TIME:
            return analysis_cache[key]["data"]

    # Veri çek
    home_gen6   = get_last6(id1)
    away_gen6   = get_last6(id2)
    home_venue6 = get_venue6(id1, "home")
    away_venue6 = get_venue6(id2, "away")

    if not home_gen6 or not away_gen6:
        return None

    # İstatistikler
    home_stats = get_fixtures_with_stats(id1, 6)
    away_stats = get_fixtures_with_stats(id2, 6)

    # H2H 2025+
    h2h = get_h2h_2025(id1, id2)

    # Lambda hesapla
    h_scored, h_conceded, h_ht_s, h_sh_s = calc_lambda_advanced(home_gen6, home_venue6, home_stats)
    a_scored, a_conceded, a_ht_s, a_sh_s = calc_lambda_advanced(away_gen6, away_venue6, away_stats)

    # Karşılıklı lambda
    lh = ((h_scored + a_conceded) / 2) * 1.06  # ev avantajı
    la = (a_scored + h_conceded) / 2
    lh = max(0.2, min(lh, 5.0))
    la = max(0.2, min(la, 5.0))
    lam_total = lh + la

    # İY lambda
    lh_ht = lh * 0.44
    la_ht = la * 0.44
    lam_ht = lh_ht + la_ht
    lam_sh = lam_total - lam_ht

    # ── 1.5 ÜST ──
    o15_poisson = over_prob_poisson(lam_total, 1.5)
    o15_dc      = over_prob_dixon_coles(lh, la, 1.5)
    o15_mc, o25_mc = monte_carlo_ou(lh, la, 10000)
    o15_raw = o15_poisson * 0.35 + o15_dc * 0.35 + o15_mc * 0.30

    # ── 2.5 ÜST ──
    o25_poisson = over_prob_poisson(lam_total, 2.5)
    o25_dc      = over_prob_dixon_coles(lh, la, 2.5)
    o25_raw = o25_poisson * 0.35 + o25_dc * 0.35 + o25_mc * 0.30

    # ── H2H düzeltmesi ──
    if h2h:
        h2h_avg = sum(m["total"] for m in h2h) / len(h2h)
        h2h_o15 = sum(1 for m in h2h if m["total"] > 1) / len(h2h)
        h2h_o25 = sum(1 for m in h2h if m["total"] > 2) / len(h2h)
        o15_final = o15_raw * 0.70 + h2h_o15 * 0.30
        o25_final = o25_raw * 0.70 + h2h_o25 * 0.30
        h2h_note = f"{len(h2h)} matches (2025+), avg {h2h_avg:.1f} goals"
    else:
        o15_final = o15_raw
        o25_final = o25_raw
        h2h_note = "No 2025+ H2H data"

    o15_final = max(0.05, min(0.95, o15_final))
    o25_final = max(0.05, min(0.95, o25_final))

    # ── Şut / Köşe / xG ortalamaları ──
    def avg_stat(stats_list, key):
        vals = [s[key] for s in stats_list if s[key] > 0]
        return round(sum(vals) / len(vals), 1) if vals else 0.0

    home_shots  = avg_stat(home_stats, "shots_on")
    away_shots  = avg_stat(away_stats, "shots_on")
    home_corners = avg_stat(home_stats, "corners")
    away_corners = avg_stat(away_stats, "corners")
    home_xg     = avg_stat(home_stats, "xg")
    away_xg     = avg_stat(away_stats, "xg")

    # ── İY/2Y gol ortalamaları ──
    home_ht_avg = weighted_avg([m["ht_scored"]   for m in home_gen6])
    home_sh_avg = weighted_avg([m["sh_scored"]   for m in home_gen6])
    away_ht_avg = weighted_avg([m["ht_scored"]   for m in away_gen6])
    away_sh_avg = weighted_avg([m["sh_scored"]   for m in away_gen6])

    home_ht_conc = weighted_avg([m["ht_conceded"] for m in home_gen6])
    away_ht_conc = weighted_avg([m["ht_conceded"] for m in away_gen6])
    home_sh_conc = weighted_avg([m["sh_conceded"] for m in home_gen6])
    away_sh_conc = weighted_avg([m["sh_conceded"] for m in away_gen6])

    # ── Son 6 maç 1.5/2.5 üst sayısı ──
    home_o15_6 = sum(1 for m in home_gen6 if m["gh"] + m["ga"] > 1)
    away_o15_6 = sum(1 for m in away_gen6 if m["gh"] + m["ga"] > 1)
    home_o25_6 = sum(1 for m in home_gen6 if m["gh"] + m["ga"] > 2)
    away_o25_6 = sum(1 for m in away_gen6 if m["gh"] + m["ga"] > 2)

    # ── Güvenilirlik ──
    warns = []
    if len(home_gen6) < 4: warns.append("⚠️ Insufficient home data")
    if len(away_gen6) < 4: warns.append("⚠️ Insufficient away data")
    if not h2h: warns.append("⚠️ No 2025+ H2H data")
    if lh <= 0.3 and la <= 0.3: warns.append("⚠️ Very low xG")

    if len(warns) == 0:   reliability = "🟢 High"
    elif len(warns) == 1: reliability = "🟡 Medium"
    else:                 reliability = "🔴 Low"

    result = {
        "h": name1, "a": name2,
        "lh": round(lh, 2), "la": round(la, 2),
        "lam_total": round(lam_total, 2),
        # Alt/Üst
        "o15": int(o15_final * 100), "u15": int((1-o15_final) * 100),
        "o25": int(o25_final * 100), "u25": int((1-o25_final) * 100),
        # İY/2Y lambda
        "lam_ht": round(lam_ht, 2), "lam_sh": round(lam_sh, 2),
        # İY/2Y gol ort
        "home_ht_avg": round(home_ht_avg, 2), "home_sh_avg": round(home_sh_avg, 2),
        "away_ht_avg": round(away_ht_avg, 2), "away_sh_avg": round(away_sh_avg, 2),
        "home_ht_conc": round(home_ht_conc, 2), "away_ht_conc": round(away_ht_conc, 2),
        "home_sh_conc": round(home_sh_conc, 2), "away_sh_conc": round(away_sh_conc, 2),
        # Son 6 maç
        "home_o15_6": f"{home_o15_6}/6", "away_o15_6": f"{away_o15_6}/6",
        "home_o25_6": f"{home_o25_6}/6", "away_o25_6": f"{away_o25_6}/6",
        # İstatistik
        "home_shots": home_shots, "away_shots": away_shots,
        "home_corners": home_corners, "away_corners": away_corners,
        "home_xg": home_xg, "away_xg": away_xg,
        # H2H
        "h2h_note": h2h_note,
        # Güvenilirlik
        "warns": warns, "reliability": reliability,
    }
    analysis_cache[key] = {"data": result, "time": now}
    return result


# ── FORMAT ────────────────────────────────────────────────────
def format_analysis(result, league="", kickoff=""):
    o15 = result["o15"]
    o25 = result["o25"]

    # Kararlar
    def verdict(prob, threshold=70):
        if prob >= 75: return "✅ STRONG OVER"
        if prob >= threshold: return "✅ OVER"
        if prob <= 30: return "✅ STRONG UNDER"
        if prob <= 40: return "⚠️ UNDER"
        return "⚠️ UNCERTAIN"

    v15 = verdict(o15)
    v25 = verdict(o25)

    league_line  = f"🏆 {league}\n" if league else ""
    ko_line      = f"⏰ {kickoff}\n" if kickoff else ""
    warn_lines   = ("\n" + "\n".join(result["warns"]) + "\n") if result["warns"] else ""

    xg_line = ""
    if result["home_xg"] > 0 or result["away_xg"] > 0:
        xg_line = f"   🎯 xG: 🏳 {result['home_xg']}  |  🚩 {result['away_xg']}\n"

    return (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "      ⚽ MATCH ANALYSIS\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{league_line}"
        f"🏳 {result['h']}\n"
        f"🚩 {result['a']}\n"
        f"{ko_line}\n"
        f"⚡ Expected Goals:\n"
        f"   🏳 λ {result['lh']}  |  🚩 λ {result['la']}\n"
        f"   📊 Total λ: {result['lam_total']}\n"
        f"{xg_line}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "    📈 OVER / UNDER\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"   1.5 Over:  {o15}%  |  Under: {result['u15']}%\n"
        f"   Last 6: 🏳 {result['home_o15_6']}  🚩 {result['away_o15_6']}\n"
        f"   👉 {v15}\n\n"
        f"   2.5 Over:  {o25}%  |  Under: {result['u25']}%\n"
        f"   Last 6: 🏳 {result['home_o25_6']}  🚩 {result['away_o25_6']}\n"
        f"   👉 {v25}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "    ⏱ HT / 2H BREAKDOWN\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"   HT λ: {result['lam_ht']}  |  2H λ: {result['lam_sh']}\n\n"
        f"   🏳 Home — HT scored avg:    {result['home_ht_avg']}\n"
        f"   🏳 Home — HT conceded avg:  {result['home_ht_conc']}\n"
        f"   🏳 Home — 2H scored avg:    {result['home_sh_avg']}\n"
        f"   🏳 Home — 2H conceded avg:  {result['home_sh_conc']}\n\n"
        f"   🚩 Away — HT scored avg:    {result['away_ht_avg']}\n"
        f"   🚩 Away — HT conceded avg:  {result['away_ht_conc']}\n"
        f"   🚩 Away — 2H scored avg:    {result['away_sh_avg']}\n"
        f"   🚩 Away — 2H conceded avg:  {result['away_sh_conc']}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "    🔫 SHOTS & CORNERS\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"   Shots on target: 🏳 {result['home_shots']}  |  🚩 {result['away_shots']}\n"
        f"   Corners avg:     🏳 {result['home_corners']}  |  🚩 {result['away_corners']}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "    🤝 H2H (2025+)\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"   {result['h2h_note']}\n"
        f"{warn_lines}\n"
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
            if not r:
                continue
            matches = r.get("response", [])
            if not matches:
                continue
            for m in matches:
                fid = m["fixture"]["id"]
                if fid in seen_ids:
                    continue
                if m["fixture"]["status"]["short"] not in ["NS", "TBD"]:
                    continue
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
        time.sleep(0.2)
    return all_fixtures

def find_auto_pick():
    global shown_auto
    fixtures = get_todays_fixtures()
    if not fixtures:
        return None, None, None

    unseen = [f for f in fixtures if f"{f['home_id']}_{f['away_id']}" not in shown_auto]
    if not unseen:
        shown_auto.clear()
        unseen = fixtures

    random.shuffle(unseen)

    for fix in unseen:
        mk = f"{fix['home_id']}_{fix['away_id']}"
        result = analyze_teams(fix["home_id"], fix["home_name"], fix["away_id"], fix["away_name"])
        shown_auto.add(mk)
        if not result:
            continue
        if result["reliability"] == "🔴 Low":
            continue
        # %70+ güven duvarı: 1.5 veya 2.5 üst
        if result["o15"] >= CONFIDENCE_THRESHOLD or result["o25"] >= CONFIDENCE_THRESHOLD:
            return fix, result, "over"
        time.sleep(0.15)
    return None, None, None


# ── TELEGRAM ──────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔️ Access Denied.")
        return
    await update.message.reply_text(
        "👋 Welcome to Over/Under Analysis Bot!\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 Commands:\n\n"
        "⚽ /analyze\n"
        "   Manual match analysis\n"
        "   1.5 & 2.5 Over/Under\n"
        "   HT/2H breakdown\n"
        "   Shots, Corners, xG\n\n"
        "🤖 /auto\n"
        "   Auto pick from bulletin\n"
        "   70%+ confidence only\n"
        "   Different match each time\n\n"
        "🔴 /stop — Pause bot\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🌍 All world leagues covered\n"
        "📊 Poisson + Dixon-Coles + MC\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )

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
    wait = await update.message.reply_text("⏳ Analyzing... Please wait.")

    id1, name1 = search_team_id(t1)
    id2, name2 = search_team_id(t2)

    if not id1:
        await wait.edit_text(f"❌ Team not found: '{t1}'\n\n➡️ /analyze to try again.")
        return ConversationHandler.END
    if not id2:
        await wait.edit_text(f"❌ Team not found: '{t2}'\n\n➡️ /analyze to try again.")
        return ConversationHandler.END

    result = analyze_teams(id1, name1, id2, name2)
    if not result:
        await wait.edit_text("❌ No data found.\n\n➡️ /analyze to try again.")
        return ConversationHandler.END

    await wait.delete()
    await update.message.reply_text(format_analysis(result))
    return ConversationHandler.END

async def auto_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔️ Access Denied.")
        return

    wait = await update.message.reply_text(
        "🛜 Scanning today's bulletin...\n"
        "Looking for 70%+ confidence picks."
    )
    try:
        fix, result, _ = find_auto_pick()
        if not fix or not result:
            await wait.edit_text(
                "❌ No match found with 70%+ confidence today.\n\n"
                "➡️ Try /auto again later."
            )
            return

        try:
            ko = datetime.fromisoformat(fix["kickoff"].replace("Z", "+00:00"))
            ko_str = ko.strftime("%H:%M")
        except:
            ko_str = "?"

        msg = (
            "🤖 AUTO PICK\n\n"
        ) + format_analysis(result, fix["league"], ko_str) + "\n\n➡️ /auto for another pick"

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
            app.add_handler(CommandHandler("auto", auto_cmd))
            app.add_handler(conv)

            print("OVER/UNDER BOT RUNNING")
            app.run_polling(drop_pending_updates=True)

        except Exception as e:
            print("BOT RESTARTING:", e)
            time.sleep(5)

run_bot()
