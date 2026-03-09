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

BOT_TOKEN = "8732987460:AAHJb_1TkA5cFYSgGc-Jq09Z8URJN_eQOko"
ADMIN_ID = 8480843841
API_KEY = "7d7e4508cb4cfe8006ccc9422bb28b1d"
API_URL = "https://v3.football.api-sports.io"

HOME_NAME, AWAY_NAME = range(2)

analysis_cache = {}
CACHE_TIME = 43200
bot_active = True

VIP_FILE = "vip_users.json"

# ── VIP YÖNETİMİ ──────────────────────────────────────────────
def load_vip():
    if os.path.exists(VIP_FILE):
        with open(VIP_FILE, "r") as f:
            return json.load(f)
    return {}

def save_vip(data):
    with open(VIP_FILE, "w") as f:
        json.dump(data, f)

def add_vip(user_id, days=7):
    data = load_vip()
    expires = (datetime.now() + timedelta(days=days)).isoformat()
    data[str(user_id)] = expires
    save_vip(data)

def remove_vip(user_id):
    data = load_vip()
    data.pop(str(user_id), None)
    save_vip(data)

def is_vip(user_id):
    if user_id == ADMIN_ID:
        return True
    data = load_vip()
    uid = str(user_id)
    if uid not in data:
        return False
    expires = datetime.fromisoformat(data[uid])
    return datetime.now() < expires

def get_expired_vips():
    data = load_vip()
    expired = []
    for uid, exp in data.items():
        if datetime.now() >= datetime.fromisoformat(exp):
            expired.append(uid)
    return expired

def get_all_vips():
    data = load_vip()
    result = []
    for uid, exp in data.items():
        expires = datetime.fromisoformat(exp)
        kalan = (expires - datetime.now()).days
        durum = "✅ Aktif" if datetime.now() < expires else "❌ Süresi Doldu"
        result.append((uid, exp, kalan, durum))
    return result

# ── TÜM DÜNYA LİGLERİ ─────────────────────────────────────────
MAJOR_LEAGUES = {
    # İNGİLTERE
    39: "Premier League", 40: "Championship", 41: "League One",
    42: "League Two", 43: "National League", 45: "FA Cup", 48: "League Cup",

    # İSPANYA
    140: "La Liga", 141: "Segunda Division", 142: "Copa del Rey",
    143: "Primera RFEF",

    # İTALYA
    135: "Serie A", 136: "Serie B", 137: "Coppa Italia", 138: "Serie C",

    # ALMANYA
    78: "Bundesliga", 79: "2. Bundesliga", 80: "3. Liga", 81: "DFB Pokal",

    # FRANSA
    61: "Ligue 1", 62: "Ligue 2", 66: "Coupe de France", 67: "Coupe de la Ligue",

    # TÜRKİYE
    203: "Süper Lig", 204: "1. Lig", 205: "2. Lig", 206: "3. Lig",

    # HOLLANDA
    88: "Eredivisie", 89: "Eerste Divisie",

    # PORTEKİZ
    94: "Primeira Liga", 95: "Segunda Liga",

    # BELÇİKA
    144: "Jupiler Pro League", 145: "Eerste Nationale",

    # İSKOÇYA
    179: "Scottish Premiership", 180: "Scottish Championship",
    181: "Scottish League One", 182: "Scottish League Two",

    # RUSYA
    235: "Premier League RU", 236: "FNL", 237: "PFL",

    # AVUSTURYA
    218: "Bundesliga AT", 219: "2. Liga AT",

    # İSVİÇRE
    207: "Super League CH", 208: "Challenge League",

    # YUNANİSTAN
    197: "Super League GR", 198: "Super League 2 GR",

    # ÇEK CUMHURİYETİ
    345: "Czech Liga", 346: "Czech FNL",

    # POLONYA
    106: "Ekstraklasa", 107: "I Liga PL",

    # ROMANYA
    283: "Liga 1 RO", 284: "Liga 2 RO",

    # HIRVATİSTAN
    210: "HNL",

    # SIRBİSTAN
    286: "Super Liga RS",

    # DANİMARKA
    119: "Superliga DK", 120: "1. Division DK",

    # NORVEÇ
    103: "Eliteserien", 104: "1. Division NO",

    # İSVEÇ
    113: "Allsvenskan", 114: "Superettan", 115: "Division 1",

    # FİNLANDİYA
    244: "Veikkausliiga", 245: "Ykkönen",

    # UKRAYNA
    333: "Premier League UA",

    # MACARİSTAN
    271: "OTP Bank Liga",

    # SLOVAKYA
    332: "Super Liga SK",

    # SLOVENYA
    322: "PrvaLiga",

    # BOSNA HERSEK
    318: "Premier Liga BIH",

    # KARADAĞ
    341: "Prva CFL",

    # ARNAVUTLUK
    316: "Kategoria Superiore",

    # BULGARİSTAN
    172: "First League BG",

    # İZLANDA
    164: "Úrvalsdeild",

    # İRLANDA
    357: "League of Ireland",

    # KUZEY İRLANDA
    374: "NIFL Premiership",

    # GALLER
    375: "Cymru Premier",

    # LİTVANYA
    377: "A Lyga",

    # LETONYA
    378: "Virsliga",

    # ESTONYA
    379: "Meistriliiga",

    # BELARUS
    380: "Vysshaya Liga",

    # MOLDOVA
    381: "Divizia Nationala",

    # KUZEY MAKEDONYA
    383: "Prva Liga MKD",

    # KOSOVo
    382: "Football Superleague Kosovo",

    # LÜKSEMBURG
    117: "National Division LUX",

    # MALTA
    356: "Premier League MT",

    # KIBRIS
    262: "Liga MX", # (id çakışmaması için aşağıda düzeltildi)

    # ── ORTA DOĞU ──
    307: "Saudi Pro League", 308: "Division 1 SA",
    435: "UAE Pro League",
    350: "Stars League QAT",
    290: "Persian Gulf Pro League",
    384: "Ligat ha'Al",
    285: "Jordan Pro League",
    403: "Lebanon Premier League",
    406: "Iraqi Premier League",

    # ── ASYA ──
    98: "J1 League", 99: "J2 League", 100: "J3 League",
    292: "K League 1", 293: "K League 2",
    169: "Chinese Super League", 170: "China League One",
    323: "Indian Super League", 324: "I-League",
    296: "Thai League 1", 297: "Thai League 2",
    313: "Liga 1 ID",
    333: "Premier League UA",
    301: "Malaysia Super League",
    304: "Singapore Premier League",
    302: "Vietnam V.League 1",
    336: "Philippines Football League",

    # ── AVUSTRALYA/OKYANUSİA ──
    188: "A-League",

    # ── AFRİKA ──
    288: "Premier Soccer League ZA",
    233: "Egyptian Premier League",
    200: "Botola Pro MA",
    201: "Ligue Pro TN",
    299: "CAF Champions League",
    370: "Nigeria Professional Football League",
    371: "Ghana Premier League",
    372: "Ethiopian Premier League",
    373: "Kenyan Premier League",
    369: "Zambia Super League",
    368: "Zimbabwe Premier Soccer League",
    367: "Ugandan Premier League",
    363: "Tanzanian Mainland",
    361: "Rwandan Premier League",
    359: "Angolan Girabola",
    358: "Mozambique Moçambola",

    # ── KUZEY AMERİKA ──
    253: "MLS",
    254: "USL Championship",
    321: "Canadian Premier League",
    262: "Liga MX",
    263: "Liga de Expansion MX",
    264: "Copa MX",

    # ── ORTA AMERİKA / KARİBLER ──
    309: "Liga Nacional GT",
    310: "Liga Mayor SV",
    312: "Liga Nacional HN",

    # ── GÜNEY AMERİKA ──
    71: "Serie A BR", 72: "Serie B BR", 73: "Serie C BR",
    128: "Liga Profesional AR", 129: "Primera Nacional AR",
    265: "Primera Division CL",
    239: "Liga BetPlay CO",
    268: "Primera Division UY",
    267: "Division Profesional PY",
    281: "Liga 1 PE",
    240: "LigaPro EC",
    269: "Liga FUTVE",
    332: "Super Liga SK",
    242: "Primera Division BO",
    278: "Primera Division CR",

    # ── ULUSLARARASI ──
    2: "Şampiyonlar Ligi",
    3: "Avrupa Ligi",
    848: "Konferans Ligi",
    1: "Dünya Kupası",
    9: "Dünya Kupası Elemeleri Avrupa",
    29: "Dünya Kupası Elemeleri Güney Amerika",
    30: "Dünya Kupası Elemeleri Asya",
    31: "Dünya Kupası Elemeleri Afrika",
    32: "Dünya Kupası Elemeleri CONCACAF",
    4: "Avrupa Şampiyonası",
    6: "Afrika Uluslar Kupası",
    7: "CONCACAF Gold Cup",
    10: "Copa America",
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
    "istanbulspor": "Istanbulspor", "bodrum": "Bodrum FK", "bodrumspor": "Bodrum FK",
    "çorum": "Corum FK", "corum": "Corum FK",
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

# ── VERİ ÇEKİMİ ───────────────────────────────────────────────
def get_last_matches(team_id, count=10):
    """Son N maç — hem genel hem ev/dep ayrımıyla"""
    r = safe_request(f"{API_URL}/fixtures?team={team_id}&last={count}&status=FT")
    if not r:
        return []
    matches = []
    for m in r.get("response", []):
        gh = m["goals"]["home"]
        ga = m["goals"]["away"]
        if gh is None or ga is None:
            continue
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

def get_home_matches(team_id, count=8):
    r = safe_request(f"{API_URL}/fixtures?team={team_id}&last=20&status=FT")
    if not r:
        return []
    matches = []
    for m in r.get("response", []):
        if m["teams"]["home"]["id"] != team_id:
            continue
        gh = m["goals"]["home"]
        ga = m["goals"]["away"]
        if gh is None or ga is None:
            continue
        matches.append({"scored": gh, "conceded": ga, "gh": gh, "ga": ga})
        if len(matches) >= count:
            break
    return matches

def get_away_matches(team_id, count=8):
    r = safe_request(f"{API_URL}/fixtures?team={team_id}&last=20&status=FT")
    if not r:
        return []
    matches = []
    for m in r.get("response", []):
        if m["teams"]["away"]["id"] != team_id:
            continue
        gh = m["goals"]["home"]
        ga = m["goals"]["away"]
        if gh is None or ga is None:
            continue
        matches.append({"scored": ga, "conceded": gh, "gh": gh, "ga": ga})
        if len(matches) >= count:
            break
    return matches

def get_h2h(id1, id2):
    r = safe_request(f"{API_URL}/fixtures/headtohead?h2h={id1}-{id2}&last=10")
    if not r:
        return [], 0, 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=3*365)
    recent, total = [], 0
    for m in r.get("response", []):
        gh = m["goals"]["home"]
        ga = m["goals"]["away"]
        if gh is None or ga is None:
            continue
        total += 1
        try:
            md = datetime.fromisoformat(m["fixture"]["date"].replace("Z", "+00:00"))
            if md >= cutoff:
                recent.append((gh, ga))
        except:
            pass
    return recent, len(recent), total

def get_team_form(team_id):
    """Son 5 maç form: W/D/L"""
    matches = get_last_matches(team_id, 5)
    form = []
    for m in matches:
        if m["scored"] > m["conceded"]:
            form.append("W")
        elif m["scored"] == m["conceded"]:
            form.append("D")
        else:
            form.append("L")
    return form

# ── ANALİZ FONKSİYONLARI ──────────────────────────────────────
def poisson_prob(lam, k):
    if k > 15:
        return 0.0
    return (math.exp(-lam) * (lam ** k)) / math.factorial(k)

def weighted_avg(values, decay=0.9):
    """Ağırlıklı ortalama — son maçlar daha ağırlıklı"""
    if not values:
        return 0.0
    total_w, weighted_sum, w = 0.0, 0.0, 1.0
    for v in reversed(values):
        weighted_sum += v * w
        total_w += w
        w *= decay
    return weighted_sum / total_w if total_w > 0 else 0.0

def calc_lambda(home_matches, away_matches, home_venue_matches, away_venue_matches):
    """
    Gelişmiş lambda hesabı:
    - Son 10 maç ağırlıklı ortalama
    - Ev/dep spesifik veri
    - %60 venue + %40 genel karışımı
    """
    # Genel ağırlıklı ortalama
    h_scored_gen   = weighted_avg([m["scored"]   for m in home_matches])
    h_conceded_gen = weighted_avg([m["conceded"] for m in home_matches])
    a_scored_gen   = weighted_avg([m["scored"]   for m in away_matches])
    a_conceded_gen = weighted_avg([m["conceded"] for m in away_matches])

    # Venue spesifik
    if home_venue_matches:
        h_scored_ven   = weighted_avg([m["scored"]   for m in home_venue_matches])
        h_conceded_ven = weighted_avg([m["conceded"] for m in home_venue_matches])
    else:
        h_scored_ven   = h_scored_gen
        h_conceded_ven = h_conceded_gen

    if away_venue_matches:
        a_scored_ven   = weighted_avg([m["scored"]   for m in away_venue_matches])
        a_conceded_ven = weighted_avg([m["conceded"] for m in away_venue_matches])
    else:
        a_scored_ven   = a_scored_gen
        a_conceded_ven = a_conceded_gen

    # %60 venue + %40 genel
    h_scored   = h_scored_ven   * 0.6 + h_scored_gen   * 0.4
    h_conceded = h_conceded_ven * 0.6 + h_conceded_gen * 0.4
    a_scored   = a_scored_ven   * 0.6 + a_scored_gen   * 0.4
    a_conceded = a_conceded_ven * 0.6 + a_conceded_gen * 0.4

    lh = (h_scored + a_conceded) / 2
    la = (a_scored + h_conceded) / 2

    # Ev sahibi avantajı
    lh = lh * 1.08

    return max(0.15, min(lh, 5.0)), max(0.15, min(la, 5.0))

def btts_prob(lh, la):
    return 1 - (math.exp(-lh) + math.exp(-la) - math.exp(-(lh + la)))

def over_prob(lam_total, threshold):
    k_max = math.floor(threshold)
    p_under = sum(poisson_prob(lam_total, k) for k in range(k_max + 1))
    return max(0.0, min(1.0, 1 - p_under))

def monte_carlo(lh, la, sims=10000):
    def sample(lam):
        L = math.exp(-lam)
        k, p = 0, 1.0
        while p > L:
            k += 1
            p *= random.random()
        return k - 1

    btts_yes = over15 = over25 = 0
    for _ in range(sims):
        h = sample(lh)
        a = sample(la)
        if h > 0 and a > 0:
            btts_yes += 1
        if h + a > 1:
            over15 += 1
        if h + a > 2:
            over25 += 1

    return btts_yes/sims, over15/sims, over25/sims

def form_bonus(form):
    """Form bonusu — son 5 maç"""
    if not form:
        return 0.0
    score = sum({"W": 3, "D": 1, "L": 0}[f] for f in form[-5:])
    max_score = 15
    return (score / max_score - 0.5) * 0.06

def h2h_kg_rate(h2h_matches):
    if not h2h_matches:
        return None
    return sum(1 for gh, ga in h2h_matches if gh > 0 and ga > 0) / len(h2h_matches)

def calculate_ht_ft(lh, la):
    """Python kodundaki İY/MS algoritması — geliştirilmiş"""
    lh_ht = lh * 0.45
    la_ht = la * 0.45
    lh_2h = lh * 0.55
    la_2h = la * 0.55

    ht_ft_probs = defaultdict(float)

    for h_ht in range(6):
        for a_ht in range(6):
            p_ht = poisson_prob(lh_ht, h_ht) * poisson_prob(la_ht, a_ht)
            if p_ht < 0.0003:
                continue
            ht​​​​​​​​​​​​​​​​
