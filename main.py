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
shown_auto = set()

# ── VIP ───────────────────────────────────────────────────────
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
    data[str(user_id)] = (datetime.now() + timedelta(days=days)).isoformat()
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
    return datetime.now() < datetime.fromisoformat(data[uid])

def get_expired_vips():
    data = load_vip()
    return [uid for uid, exp in data.items() if datetime.now() >= datetime.fromisoformat(exp)]

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
    49: "Non League", 51: "Football League Trophy",

    # İSPANYA
    140: "La Liga", 141: "Segunda Division", 142: "Copa del Rey", 143: "Primera RFEF",

    # İTALYA
    135: "Serie A", 136: "Serie B", 137: "Coppa Italia", 138: "Serie C",

    # ALMANYA
    78: "Bundesliga", 79: "2. Bundesliga", 80: "3. Liga", 81: "DFB Pokal",
    197: "Regionalliga Bayern",

    # FRANSA
    61: "Ligue 1", 62: "Ligue 2", 63: "National", 66: "Coupe de France",

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
    210: "HNL", 211: "HNL 2",

    # SIRBİSTAN
    286: "Super Liga RS", 287: "Liga 2 RS",

    # DANİMARKA
    119: "Superliga DK", 120: "1. Division DK",

    # NORVEÇ
    103: "Eliteserien", 104: "1. Division NO", 105: "2. Division NO",

    # İSVEÇ
    113: "Allsvenskan", 114: "Superettan", 115: "Division 1",

    # FİNLANDİYA
    244: "Veikkausliiga", 245: "Ykkönen",

    # UKRAYNA
    333: "Premier League UA", 334: "Persha Liga UA",

    # MACARİSTAN
    271: "OTP Bank Liga", 272: "Merkur Liga",

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
    172: "First League BG", 173: "Second League BG",

    # İZLANDA
    164: "Úrvalsdeild", 165: "1. deild",

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

    # KOSOVA
    382: "Football Superleague Kosovo",

    # LÜKSEMBURG
    117: "National Division LUX",

    # MALTA
    356: "Premier League MT",

    # GİBRALTAR
    392: "Gibraltar Premier Division",

    # FAROE ADALARI
    387: "Faroe Islands Premier League",

    # ERMENİSTAN
    371: "Armenian Premier League",

    # GÜRCİSTAN
    372: "Erovnuli Liga",

    # AZERBAYCAN
    373: "Premier League AZ",

    # KAZAKİSTAN
    376: "Premier League KZ",

    # ── ORTA DOĞU ──
    307: "Saudi Pro League", 308: "Division 1 SA",
    435: "UAE Pro League", 436: "UAE Division 1",
    350: "Stars League QAT",
    290: "Persian Gulf Pro League", 291: "Azadegan League",
    384: "Ligat ha'Al", 385: "Liga Leumit",
    285: "Jordan Pro League",
    403: "Lebanon Premier League",
    406: "Iraqi Premier League",
    343: "Bahrain Premier League",
    344: "Kuwait Premier League",
    430: "Oman Professional League",

    # ── ASYA ──
    98: "J1 League", 99: "J2 League", 100: "J3 League",
    292: "K League 1", 293: "K League 2",
    169: "Chinese Super League", 170: "China League One", 171: "China League Two",
    323: "Indian Super League", 324: "I-League",
    296: "Thai League 1", 297: "Thai League 2",
    313: "Liga 1 ID", 314: "Liga 2 ID",
    301: "Malaysia Super League",
    304: "Singapore Premier League",
    302: "Vietnam V.League 1",
    336: "Philippines Football League",
    397: "AFC Champions League",
    260: "Pakistan Premier League",
    303: "Myanmar National League",
    305: "Hong Kong Premier League",
    306: "Macau Premier League",

    # ── AVUSTRALYA ──
    188: "A-League", 189: "NPL Australia",

    # ── AFRİKA ──
    288: "Premier Soccer League ZA",
    233: "Egyptian Premier League",
    200: "Botola Pro MA",
    201: "Ligue Pro TN",
    299: "CAF Champions League",
    370: "Nigeria Professional Football League",
    366: "Ghana Premier League",
    362: "Ethiopian Premier League",
    363: "Kenyan Premier League",
    369: "Zambia Super League",
    368: "Zimbabwe Premier Soccer League",
    367: "Ugandan Premier League",
    364: "Tanzanian Mainland",
    361: "Rwandan Premier League",
    359: "Angolan Girabola",
    358: "Mozambique Moçambola",
    360: "Botswana Premier League",
    365: "Senegal Premier League",
    386: "Ivory Coast Ligue 1",
    388: "Cameroon Elite One",
    389: "DR Congo Linafoot",
    390: "Algeria Ligue Professionnelle 1",
    391: "Libya Premier League",
    393: "Sudan Premier League",
    394: "Somalia Premier League",
    395: "Tanzania Mainland",
    396: "Malawi Super League",

    # ── KUZEY AMERİKA ──
    253: "MLS", 254: "USL Championship", 255: "USL League One",
    321: "Canadian Premier League",
    262: "Liga MX", 263: "Liga de Expansion MX",

    # ── ORTA AMERİKA / KARİBLER ──
    309: "Liga Nacional GT",
    310: "Primera Division SV",
    312: "Liga Nacional HN",
    317: "Panama Liga",
    320: "Costa Rica Primera Division",
    319: "Nicaragua Primera Division",
    315: "Dominican Republic LDF",

    # ── GÜNEY AMERİKA ──
    71: "Serie A BR", 72: "Serie B BR", 73: "Serie C BR",
    128: "Liga Profesional AR", 129: "Primera Nacional AR",
    265: "Primera Division CL", 266: "Primera B CL",
    239: "Liga BetPlay CO",
    268: "Primera Division UY",
    267: "Division Profesional PY",
    281: "Liga 1 PE",
    240: "LigaPro EC",
    269: "Liga FUTVE",
    242: "Primera Division BO",
    278: "Primera Division CR",
    11: "Copa Libertadores", 13: "Copa Sudamericana",

    # ── ULUSLARARASI ──
    2: "Şampiyonlar Ligi", 3: "Avrupa Ligi", 848: "Konferans Ligi",
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
    16: "UEFA Nations League",
    17: "AFC Asian Cup",
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
        matches.append({
            "scored":   gh if is_home else ga,
            "conceded": ga if is_home else gh,
            "gh": gh, "ga": ga,
            "is_home": is_home,
        })
    return matches

def get_venue_matches(team_id, venue="home", count=8):
    r = safe_request(f"{API_URL}/fixtures?team={team_id}&last=25&status=FT")
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
        matches.append({
            "scored":   gh if is_home else ga,
            "conceded": ga if is_home else gh,
            "gh": gh, "ga": ga,
        })
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

# ── ANALİZ FONKSİYONLARI ──────────────────────────────────────
def poisson_prob(lam, k):
    if k > 15:
        return 0.0
    return (math.exp(-lam) * (lam ** k)) / math.factorial(k)

def weighted_avg(values, decay=0.88):
    if not values:
        return 0.0
    total_w, weighted_sum, w = 0.0, 0.0, 1.0
    for v in reversed(values):
        weighted_sum += v * w
        total_w += w
        w *= decay
    return weighted_sum / total_w if total_w > 0 else 0.0

def calc_lambda(home_gen, away_gen, home_venue, away_venue):
    """
    Gelişmiş lambda:
    - Son 10 maç ağırlıklı ortalama (decay=0.88)
    - Ev/dep venue spesifik %60 + genel %40
    - Ev sahibi avantajı x1.08
    """
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

def btts_prob_calc(lh, la):
    return 1 - (math.exp(-lh) + math.exp(-la) - math.exp(-(lh + la)))

def over_prob_calc(lam_total, threshold):
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

def calc_form_bonus(matches):
    if not matches:
        return 0.0
    son5 = matches[-5:]
    puan = sum(3 if m["scored"] > m["conceded"] else (1 if m["scored"] == m["conceded"] else 0) for m in son5)
    return (puan / 15 - 0.5) * 0.05

def calculate_ht_ft(lh, la):
    """
    İY/MS — Python kodundan alınan algoritma
    İlk yarı %45, ikinci yarı %55 lambda
    """
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
            if h_ht > a_ht:   ht = "1"
            elif h_ht < a_ht: ht = "2"
            else:              ht = "X"

            for h_2h in range(6):
                for a_2h in range(6):
                    p_2h = poisson_prob(lh_2h, h_2h) * poisson_prob(la_2h, a_2h)
                    if p_2h < 0.0003:
                        continue
                    h_ft = h_ht + h_2h
                    a_ft = a_ht + a_2h
                    if h_ft > a_ft:   ft = "1"
                    elif h_ft < a_ft: ft = "2"
                    else:             ft = "X"
                    ht_ft_probs[f"{ht}/{ft}"] += p_ht * p_2h

    top2 = sorted(ht_ft_probs.items(), key=lambda x: x[1], reverse=True)[:2]
    return [(k, v * 100) for k, v in top2]

def ht_ft_desc(code):
    return {
        "1/1": "Ev Önde → Ev Kazanır",
        "X/1": "Berabere → Ev Kazanır",
        "X/2": "Berabere → Dep. Kazanır",
        "2/2": "Dep. Önde → Dep. Kazanır",
        "X/X": "Berabere → Berabere",
        "2/1": "Dep. Önde → Ev Kazanır",
        "1/X": "Ev Önde → Berabere",
        "1/2": "Ev Önde → Dep. Kazanır",
        "2/X": "Dep. Önde → Berabere",
    }.get(code, code)

def top_scores_list(lh, la, n=3):
    probs = {}
    for h in range(8):
        ph = math.exp(-lh) * (lh**h) / math.factorial(h)
        for a in range(8):
            pa = math.exp(-la) * (la**a) / math.factorial(a)
            probs[f"{h}-{a}"] = ph * pa
    return sorted(probs.items(), key=lambda x: x[1], reverse=True)[:n]

# ── ANA ANALİZ ────────────────────────────────────────────────
def analyze_teams(id1, name1, id2, name2):
    key = f"{name1.lower()}_{name2.lower()}"
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

    # Lambda hesapla
    lh, la = calc_lambda(home_gen, away_gen, home_venue, away_venue)
    lam_total = lh + la

    # Form bonusu
    fb_home = calc_form_bonus(home_gen)
    fb_away = calc_form_bonus(away_gen)
    form_adj = (fb_home + fb_away) / 2

    # KG
    kg_poisson  = btts_prob_calc(lh, la)
    mc_kg, mc_o15, mc_o25 = monte_carlo(lh, la, 10000)
    kg_raw = (kg_poisson * 0.6 + mc_kg * 0.4) + form_adj
    kg_raw = max(0.05, min(0.95, kg_raw))

    # H2H KG düzeltmesi
    h2h, h2h_recent, h2h_total = get_h2h(id1, id2)
    h2h_note = "yok"
    if h2h and h2h_recent >= 2:
        h2h_kg = sum(1 for gh, ga in h2h if gh > 0 and ga > 0) / len(h2h)
        kg_final = kg_raw * 0.65 + h2h_kg * 0.35
        h2h_note = f"{sum(1 for gh,ga in h2h if gh>0 and ga>0)}/{len(h2h)}"
    elif h2h_recent == 1:
        h2h_kg = sum(1 for gh, ga in h2h if gh > 0 and ga > 0) / len(h2h)
        kg_final = kg_raw * 0.80 + h2h_kg * 0.20
        h2h_note = f"{sum(1 for gh,ga in h2h if gh>0 and ga>0)}/{len(h2h)}"
    elif h2h_total > 0 and h2h_recent == 0:
        kg_final = kg_raw
        h2h_note = "eski"
    else:
        kg_final = kg_raw

    kg_final = max(0.05, min(0.95, kg_final))

    # Alt/Üst
    o15_poisson = over_prob_calc(lam_total, 1.5)
    o25_poisson = over_prob_calc(lam_total, 2.5)
    o15_final = max(0.05, min(0.95, (o15_poisson * 0.6 + mc_o15 * 0.4) + form_adj))
    o25_final = max(0.05, min(0.95, (o25_poisson * 0.6 + mc_o25 * 0.4) + form_adj))

    # İY/MS
    ht_ft = calculate_ht_ft(lh, la)

    # Son maç KG sayıları
    home5_kg  = sum(1 for m in home_gen[:5] if m["gh"] > 0 and m["ga"] > 0)
    away5_kg  = sum(1 for m in away_gen[:5] if m["gh"] > 0 and m["ga"] > 0)
    home10_kg = sum(1 for m in home_gen if m["gh"] > 0 and m["ga"] > 0)
    away10_kg = sum(1 for m in away_gen if m["gh"] > 0 and m["ga"] > 0)

    # Güvenilirlik
    warns = []
    if len(home_gen) < 5:  warns.append("⚠️ Ev takımı verisi yetersiz")
    if len(away_gen) < 5:  warns.append("⚠️ Deplasman takımı verisi yetersiz")
    if h2h_note == "yok":  warns.append("⚠️ H2H verisi bulunamadı")
    elif h2h_note == "eski": warns.append("⚠️ H2H verisi 3 yıldan eski")
    if lh <= 0.2 and la <= 0.2: warns.append("⚠️ Çok düşük xG — veri güvenilmez olabilir")

    if len(warns) == 0:   reliability = "🟢 Yüksek"
    elif len(warns) == 1: reliability = "🟡 Orta"
    else:                 reliability = "🔴 Düşük — dikkatli ol"

    scores = top_scores_list(lh, la, 3)

    result = {
        "h": name1, "a": name2,
        "lh": round(lh, 2), "la": round(la, 2),
        "kg":    int(kg_final * 100),
        "kg_no": int((1 - kg_final) * 100),
        "o15": int(o15_final * 100), "u15": int((1 - o15_final) * 100),
        "o25": int(o25_final * 100), "u25": int((1 - o25_final) * 100),
        "htft": ht_ft,
        "home5_kg":  f"{home5_kg}/5",
        "away5_kg":  f"{away5_kg}/5",
        "home10_kg": f"{home10_kg}/{len(home_gen)}",
        "away10_kg": f"{away10_kg}/{len(away_gen)}",
        "h2h_note": h2h_note,
        "scores": scores,
        "warns": warns,
        "reliability": reliability,
    }
    analysis_cache[key] = {"data": result, "time": now}
    return result

def format_analysis(result):
    h2h_line = {
        "yok":  "🤝 H2H: Veri yok\n",
        "eski": "🤝 H2H: 3 yıldan eski — kullanılmadı\n",
    }.get(result["h2h_note"], f"🤝 H2H KG: {result['h2h_note']}\n")

    kg_karar  = "✅ KG VAR"  if result["kg"]  >= 60 else ("❌ KG YOK"  if result["kg_no"] >= 60 else "⚠️ BELİRSİZ")
    o15_karar = "✅ 1.5 ÜST" if result["o15"] >= 65 else "❌ 1.5 ALT"
    o25_karar = "✅ 2.5 ÜST" if result["o25"] >= 55 else "❌ 2.5 ALT"

    htft_emojis = {
        "1/1": "🏠", "X/1": "🔄", "X/2": "🔄", "2/2": "✈️",
        "X/X": "🤝", "2/1": "🔄", "1/X": "🤝", "1/2": "🔄", "2/X": "🤝",
    }
    htft_lines = ""
    for i, (code, prob) in enumerate(result["htft"], 1):
        emoji = htft_emojis.get(code, "⚽")
        htft_lines += f"   {i}. {emoji} {code} — %{prob:.1f} ({ht_ft_desc(code)})\n"

    score_lines = ""
    for sc, prob in result["scores"]:
        parts = sc.split("-")
        kg_icon = "✅" if int(parts[0]) > 0 and int(parts[1]) > 0 else "❌"
        score_lines += f"   {kg_icon} {sc}  %{prob*100:.1f}\n"

    warn_lines = ("\n" + "\n".join(result["warns"]) + "\n") if result["warns"] else ""

    return (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "      📊 MAÇ ANALİZİ\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏳 {result['h']}\n"
        f"🚩 {result['a']}\n\n"
        f"⚡ xG: Ev {result['lh']}  |  Dep {result['la']}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "  ⚽ KARŞILIKLI GOL (KG)\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"   KG VAR: %{result['kg']}\n"
        f"   KG YOK: %{result['kg_no']}\n"
        f"   Son 5:  🏳 {result['home5_kg']}  🚩 {result['away5_kg']}\n"
        f"   Son 10: 🏳 {result['home10_kg']}  🚩 {result['away10_kg']}\n"
        f"   {h2h_line}"
        f"   👉 {kg_karar}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "     📈 ALT / ÜST\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"   1.5 Üst: %{result['o15']}  |  Alt: %{result['u15']}\n"
        f"   2.5 Üst: %{result['o25']}  |  Alt: %{result['u25']}\n"
        f"   👉 {o15_karar}  |  {o25_karar}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "  🔄 İLK YARI / MAÇ SONU\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{htft_lines}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "    🎯 OLASI SKORLAR\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{score_lines}"
        f"{warn_lines}\n"
        f"📶 Güvenilirlik: {result['reliability']}\n"
        "━━━━━━━━━━━━━━━━━━━━"
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
        time.sleep(0.25)
    return all_fixtures

def find_auto_pick(threshold=65):
    global shown_auto
    fixtures = get_todays_fixtures()
    if not fixtures:
        return None, None

    unseen = [f for f in fixtures if f"{f['home_id']}_{f['away_id']}" not in shown_auto]
    if not unseen:
        shown_auto.clear()
        unseen = fixtures

    random.shuffle(unseen)

    for fix in unseen:
        mk = f"{fix['home_id']}_{fix['away_id']}"
        result = analyze_teams(fix["home_id"], fix["home_name"], fix["away_id"], fix["away_name"])
        shown_auto.add(mk)
        if result and result["kg"] >= threshold and result["reliability"] != "🔴 Düşük — dikkatli ol":
            return fix, result
        time.sleep(0.15)
    return None, None

# ── VİP SÜRESİ KONTROL ────────────────────────────────────────
async def check_vip_expiry(app):
    while True:
        await asyncio.sleep(3600)
        for uid in get_expired_vips():
            remove_vip(uid)
            try:
                await app.bot.send_message(
                    chat_id=int(uid),
                    text=(
                        "⏰ VİP üyeliğinizin süresi doldu!\n\n"
                        "Analizlere devam etmek için VİP alın:\n\n"
                        "💎 7 Günlük VİP: 800₺\n"
                        "📩 İletişim: @blutad"
                    )
                )
            except:
                pass

# ── TELEGRAM KOMUTLARI ────────────────────────────────────────
VIP_REQUIRED_MSG = (
    "🚫 VİP Üye Olmadığınız için İşlem Yapılmıyor.\n\n"
    "💎 7 Günlük VİP: 800₺\n"
    "📩 İletişim: @blutad"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid == ADMIN_ID:
        await update.message.reply_text(
            "👑 Hoş geldin Admin!\n\n"
            "📌 Komutlar:\n\n"
            "⚽ /analiz — Maç analizi (KG + Alt/Üst + İY/MS)\n"
            "🤖 /otomatik — Bugünkü bültenden %65+ maç\n"
            "🔴 /dur — Botu durdur\n\n"
            "👑 Admin Komutları:\n"
            "/vipekle [user_id] — 7 günlük VİP ekle\n"
            "/toplamvip — Tüm VİP listesi"
        )
        return

    if is_vip(uid):
        await update.message.reply_text(
            "✅ Hoş geldin VİP Üye!\n\n"
            "📌 Komutlar:\n\n"
            "⚽ /analiz — Maç analizi (KG + Alt/Üst + İY/MS)\n"
            "🤖 /otomatik — Bugünkü bültenden %65+ maç\n"
            "🔴 /dur — Botu durdur"
        )
    else:
        await update.message.reply_text(
            "🚫 Merhaba!\n\n"
            "VİP Üye Olmadığınız için İşlem Yapılmıyor.\n"
            "Lütfen VİP Alın.\n\n"
            "📊 Günlük +400 Maç Analizi\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💎 VİP: 7 Günlük 800₺\n"
            "📩 İletişim: @blutad\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )

async def dur_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_active
    if not is_vip(update.effective_user.id):
        await update.message.reply_text(VIP_REQUIRED_MSG)
        return
    bot_active = False
    await update.message.reply_text("🔴 Bot durduruldu.\n\nDevam etmek için /analiz veya /otomatik yaz.")

async def vipekle_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔️ Sadece admin kullanabilir.")
        return
    if not context.args:
        await update.message.reply_text("Kullanım: /vipekle [user_id]")
        return
    try:
        uid = int(context.args[0])
        add_vip(uid, days=7)
        await update.message.reply_text(f"✅ {uid} kullanıcısına 7 günlük VİP eklendi.")
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=(
                    "🎉 VİP üyeliğiniz aktifleştirildi!\n\n"
                    "7 gün boyunca tüm analizlere erişebilirsiniz.\n\n"
                    "⚽ /analiz — Maç analizi\n"
                    "🤖 /otomatik — Otomatik maç\n\n"
                    "İyi analizler! 🍀"
                )
            )
        except:
            pass
    except ValueError:
        await update.message.reply_text("❌ Geçersiz user ID.")

async def toplamvip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔️ Sadece admin kullanabilir.")
        return
    vips = get_all_vips()
    if not vips:
        await update.message.reply_text("📋 Henüz VİP üye yok.")
        return
    lines = ["👑 TÜM VİP ÜYELER\n━━━━━━━━━━━━━━━━━━━━\n"]
    for uid, exp, kalan, durum in vips:
        exp_str = datetime.fromisoformat(exp).strftime("%d.%m.%Y %H:%M")
        lines.append(f"🆔 {uid}\n{durum}\n📅 Bitiş: {exp_str}\n⏳ Kalan: {kalan} gün\n")
    await update.message.reply_text("\n".join(lines))

async def analiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_active
    uid = update.effective_user.id
    if not is_vip(uid):
        await update.message.reply_text(VIP_REQUIRED_MSG)
        return ConversationHandler.END
    bot_active = True
    context.user_data.clear()
    await update.message.reply_text("🏳 Ev Sahibi Takım Adı:")
    return HOME_NAME

async def get_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_active:
        await update.message.reply_text("🔴 Bot durduruldu. /analiz ile yeniden başlat.")
        return ConversationHandler.END
    context.user_data["t1"] = update.message.text
    await update.message.reply_text("🚩 Deplasman Takım Adı:")
    return AWAY_NAME

async def get_away(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_active:
        await update.message.reply_text("🔴 Bot durduruldu.")
        return ConversationHandler.END
    if not is_vip(update.effective_user.id):
        await update.message.reply_text(VIP_REQUIRED_MSG)
        return ConversationHandler.END

    t1 = context.user_data.get("t1", "")
    t2 = update.message.text
    wait = await update.message.reply_text("⏳ Analiz yapılıyor...")

    id1, name1 = search_team_id(t1)
    id2, name2 = search_team_id(t2)

    if not id1:
        await wait.edit_text(f"❌ Takım bulunamadı: '{t1}'\n\n➡️ /analiz ile tekrar dene.")
        return ConversationHandler.END
    if not id2:
        await wait.edit_text(f"❌ Takım bulunamadı: '{t2}'\n\n➡️ /analiz ile tekrar dene.")
        return ConversationHandler.END

    result = analyze_teams(id1, name1, id2, name2)
    if not result:
        await wait.edit_text("❌ Maç verisi bulunamadı.\n\n➡️ /analiz ile tekrar dene.")
        return ConversationHandler.END

    await wait.delete()
    await update.message.reply_text(format_analysis(result))
    return ConversationHandler.END

async def otomatik_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_vip(update.effective_user.id):
        await update.message.reply_text(VIP_REQUIRED_MSG)
        return

    wait = await update.message.reply_text("🛜 Bugünün bülteni taranıyor...")
    try:
        fix, result = find_auto_pick(threshold=65)
        if not fix or not result:
            await wait.edit_text(
                "❌ Bugün %65+ güven ile maç bulunamadı.\n\n"
                "➡️ /otomatik ile tekrar dene."
            )
            return

        try:
            ko = datetime.fromisoformat(fix["kickoff"].replace("Z", "+00:00"))
            ko_str = ko.strftime("%H:%M")
        except:
            ko_str = "?"

        header = (
            f"🤖 OTOMATİK SEÇİM\n\n"
            f"🏆 {fix['league']}\n"
            f"⏰ {ko_str}\n\n"
        )
        await wait.edit_text(header + format_analysis(result) + "\n\n➡️ /otomatik ile yeni maç")
    except Exception as e:
        await wait.edit_text(f"❌ Hata: {e}")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ İptal edildi.")
    return ConversationHandler.END

async def unknown_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_vip(update.effective_user.id):
        await update.message.reply_text(
            "🚫 Merhaba!\n\n"
            "VİP Üye Olmadığınız için İşlem Yapılmıyor.\n"
            "Lütfen VİP Alın.\n\n"
            "📊 Günlük +400 Maç Analizi\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💎 VİP: 7 Günlük 800₺\n"
            "📩 İletişim: @blutad\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )

async def post_init(app):
    asyncio.create_task(check_vip_expiry(app))

def run_bot():
    while True:
        try:
            app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

            analiz_conv = ConversationHandler(
                entry_points=[CommandHandler("analiz", analiz_cmd)],
                states={
                    HOME_NAME: [
                        CommandHandler("analiz", analiz_cmd),
                        CommandHandler("dur", dur_cmd),
                        MessageHandler(filters.TEXT & ~filters.COMMAND, get_home),
                    ],
                    AWAY_NAME: [
                        CommandHandler("analiz", analiz_cmd),
                        CommandHandler("dur", dur_cmd),
                        MessageHandler(filters.TEXT & ~filters.COMMAND, get_away),
                    ],
                },
                fallbacks=[
                    CommandHandler("cancel", cancel),
                    CommandHandler("analiz", analiz_cmd),
                    CommandHandler("dur", dur_cmd),
                ],
                allow_reentry=True,
            )

            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("dur", dur_cmd))
            app.add_handler(CommandHandler("otomatik", otomatik_cmd))
            app.add_handler(CommandHandler("vipekle", vipekle_cmd))
            app.add_handler(CommandHandler("toplamvip", toplamvip_cmd))
            app.add_handler(analiz_conv)
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_user))

            print("BOT ÇALIŞIYOR")
            app.run_polling(drop_pending_updates=True)
        except Exception as e:
            print("BOT YENİDEN BAŞLATILIYOR:", e)
            time.sleep(5)

run_bot()
