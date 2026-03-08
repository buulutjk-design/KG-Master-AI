import requests
import math
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


def poisson_zero(x):
    return math.exp(-x)


def safe_request(url):

    headers = {
        "x-rapidapi-key": API_KEY,
        "x-rapidapi-host": "v3.football.api-sports.io"
    }

    for _ in range(3):

        try:

            r = requests.get(url, headers=headers, timeout=10)

            if r.status_code == 200:
                return r.json()

        except:
            pass

        time.sleep(1)

    return None


def get_team_id(name):

    r = safe_request(f"{API_URL}/teams?search={name}")

    if not r:
        return None

    data = r.get("response")

    if data:
        return data[0]["team"]["id"]

    return None


def get_team_stats(team_id):

    r = safe_request(f"{API_URL}/fixtures?team={team_id}&last=10")

    if not r:
        return None

    matches = r.get("response", [])

    if not matches:
        return None

    btts = 0
    goals_for = []
    goals_against = []
    form_points = 0

    for m in matches:

        gh = m["goals"]["home"]
        ga = m["goals"]["away"]

        home_id = m["teams"]["home"]["id"]

        if gh is None or ga is None:
            continue

        if gh > 0 and ga > 0:
            btts += 1

        if home_id == team_id:

            goals_for.append(gh)
            goals_against.append(ga)

            if gh > ga:
                form_points += 3
            elif gh == ga:
                form_points += 1

        else:

            goals_for.append(ga)
            goals_against.append(gh)

            if ga > gh:
                form_points += 3
            elif gh == ga:
                form_points += 1

    if not goals_for:
        return None

    return {

        "btts": btts/len(matches),

        "attack": sum(goals_for)/len(goals_for),

        "defense": sum(goals_against)/len(goals_against),

        "form": form_points/30
    }


def get_match_analysis(t1,t2):

    key=f"{t1.lower()}_{t2.lower()}"

    now=datetime.now().timestamp()

    if key in analysis_cache:

        cached=analysis_cache[key]

        if now-cached["time"] < CACHE_TIME:

            return cached["data"]

    id1 = get_team_id(t1)
    id2 = get_team_id(t2)

    if not id1 or not id2:
        return None

    s1 = get_team_stats(id1)
    s2 = get_team_stats(id2)

    if not s1 or not s2:
        return None

    home_xg = (s1["attack"] + s2["defense"]) / 2
    away_xg = (s2["attack"] + s1["defense"]) / 2

    p_home0 = poisson_zero(home_xg)
    p_away0 = poisson_zero(away_xg)

    poisson = 1 - p_home0 - p_away0 + (p_home0*p_away0)

    stat = (s1["btts"] + s2["btts"]) / 2
    form = (s1["form"] + s2["form"]) / 2

    final = (
        poisson*0.5 +
        stat*0.3 +
        form*0.2
    )

    prob=int(final*100)

    result={
        "h":t1,
        "a":t2,
        "p":prob
    }

    analysis_cache[key]={
        "data":result,
        "time":now
    }

    return result


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    await update.message.reply_text("👋 Welcome to the BTTS Analysis Bot")
    await update.message.reply_text("🏳 Home Team Name.")

    return HOME_NAME


async def get_home(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["t1"]=update.message.text

    await update.message.reply_text("🚩 Away Team Name:")

    return AWAY_NAME


async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):

    t1=context.user_data["t1"]
    t2=update.message.text

    wait=await update.message.reply_text(
        "🛜 Analysis in progress...\nFetching match data..."
    )

    result=get_match_analysis(t1,t2)

    if not result:

        await wait.edit_text(
            "❌ Data not found.\n\nTry official team names."
        )

        return ConversationHandler.END

    await wait.delete()

    prob=result["p"]

    status_icon="✅" if prob>=50 else "⛔️"
    status="BTTS YES" if prob>=50 else "BTTS NO"

    report=(
        "📊 MATCH ANALYSIS\n\n"
        f"🏳 {result['h']}\n"
        f"🚩 {result['a']}\n\n"
        f"{status_icon} {status}\n"
        f"{prob}%"
    )

    await update.message.reply_text(report)

    return ConversationHandler.END


def run_bot():

    while True:

        try:

            app=Application.builder().token(BOT_TOKEN).build()

            conv=ConversationHandler(

                entry_points=[CommandHandler("start",start)],

                states={

                    HOME_NAME:[MessageHandler(filters.TEXT & ~filters.COMMAND,get_home)],

                    AWAY_NAME:[MessageHandler(filters.TEXT & ~filters.COMMAND,analyze)]

                },

                fallbacks=[]

            )

            app.add_handler(conv)

            print("BOT RUNNING")

            app.run_polling()

        except Exception as e:

            print("BOT CRASHED RESTARTING",e)

            time.sleep(5)


run_bot()
