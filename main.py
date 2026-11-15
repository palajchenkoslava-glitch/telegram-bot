import telebot
import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask
from threading import Thread

# ТЕПЕРЬ ТОКЕН БЕРЕТСЯ ИЗ ПЕРЕМЕННЫХ RENDER, А НЕ ИЗ КОДА
TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)

DATABASE_URL = os.environ.get('DATABASE_URL')

def init_db():
    if not DATABASE_URL: return
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS bot_state (id INTEGER PRIMARY KEY CHECK (id = 1), bank REAL, history JSONB)")
        cur.execute("INSERT INTO bot_state (id, bank, history) VALUES (1, 110000, '[]') ON CONFLICT (id) DO NOTHING")
        conn.commit()
        cur.close()
        conn.close()
        print("✅ БАЗА ДАННЫХ ПОДКЛЮЧЕНА!")
    except Exception as e:
        print(f"❌ ОШИБКА БД: {e}")

def load_data():
    if not DATABASE_URL: return 110000, []
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT bank, history FROM bot_state WHERE id = 1")
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row: return row['bank'], row['history']
    except: pass
    return 110000, []

def save_data(current_bank, current_history):
    if not DATABASE_URL: return
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cur = conn.cursor()
        cur.execute("UPDATE bot_state SET bank = %s, history = %s WHERE id = 1", (current_bank, json.dumps(current_history)))
        conn.commit()
        cur.close()
        conn.close()
    except: pass

init_db()
BANK, HISTORY = load_data()
CURRENT_BET = 0
CURRENT_ODDS = 0
CURRENT_MATCH = "Нет"

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, f"🟢 Бот Протокола 80/20 v7.0!\nТвой банк: {BANK:.2f} ₽.\n\nКоманды:\n/bank - баланс\n/bet Сумма Кэф Матч - ставка\n/win Сумма - выигрыш\n/lose - проигрыш\n/value Сумма Кэф Вероятность(%) - расчет валуя\n/stats - статистика\n/history - история\n/check - правила")

@bot.message_handler(commands=['value'])
def calculate_value(message):
    try:
        parts = message.text.split()
        if len(parts) != 4: raise ValueError
        stake = float(parts[1])
        odds = float(parts[2])
        prob = float(parts[3]) / 100 
        
        ev = (stake * odds * prob) - stake
        implied_prob = (1 / odds) * 100
        
        text = f"🧮 Анализ:\nСумма: {stake} ₽ | Кэф: {odds}\n"
        text += f"Вероятность БК: {implied_prob:.1f}%\n"
        text += f"Твоя вероятность: {prob*100:.1f}%\n\n"
        
        if ev > 0:
            text += f"✅ ВАЛУЙ! Матожидание: +{ev:.2f} ₽.\nМожно брать."
        else:
            text += f"❌ ЛОВУШКА! Матожидание: {ev:.2f} ₽.\nБукмекер завысил цену."
            
        bot.send_message(message.chat.id, text)
    except:
        bot.send_message(message.chat.id, "⚠️ Формат: /value 1000 1.85 65")

@bot.message_handler(commands=['check'])
def check_list(message):
    bot.send_message(message.chat.id, "🛑 ПРАВИЛА v7.0:\n1. Кэф от 1.70 до 1.90?\n2. Вероятность > 55%?\n3. Нет травм/ротации?\n4. Сумма < 3% банка?\n5. Это не экспресс?\n\nЕсли да — используй /value!")

@bot.message_handler(commands=['bank'])
def show_bank(message):
    bet_info = f"{CURRENT_BET} ₽ на {CURRENT_MATCH} (кэф {CURRENT_ODDS})" if CURRENT_BET > 0 else "Нет"
    bot.send_message(message.chat.id, f"💰 Банк: {BANK:.2f} ₽\n🎯 В игре: {bet_info}")

@bot.message_handler(commands=['bet'])
def place_bet(message):
    global BANK, CURRENT_BET, CURRENT_ODDS, CURRENT_MATCH
    try:
        parts = message.text.split(maxsplit=3) 
        if len(parts) < 3: raise ValueError
        stake = float(parts[1])
        odds = float(parts[2])
        match_name = parts[3] if len(parts) > 3 else "Неизвестный матч"
        
        limit = BANK * 0.03
        if stake > limit:
            bot.send_message(message.chat.id, f"⚠️ Лимит 3%! Максимум {limit:.0f} ₽.")
            return
        if stake > BANK:
            bot.send_message(message.chat.id, "❌ Недостаточно средств!")
            return

        BANK -= stake
        CURRENT_BET = stake
        CURRENT_ODDS = odds
        CURRENT_MATCH = match_name
        save_data(BANK, HISTORY) 
        bot.send_message(message.chat.id, f"✅ Принято!\n📌 {match_name}\n💰 {stake} ₽ | Кэф: {odds}\nСвободный банк: {BANK:.2f} ₽")
    except:
        bot.send_message(message.chat.id, "⚠️ Формат: /bet 1000 1.85 Спартак П1")

@bot.message_handler(commands=['win'])
def win(message):
    global BANK, CURRENT_BET, CURRENT_MATCH, HISTORY
    if CURRENT_BET == 0: return
    try:
        amount = float(message.text.split()[1])
        BANK += amount
        HISTORY.append({'match': CURRENT_MATCH, 'stake': CURRENT_BET, 'odds': CURRENT_ODDS, 'result': 'WIN', 'profit': amount - CURRENT_BET})
        save_data(BANK, HISTORY) 
        bot.send_message(message.chat.id, f"🎉 Выигрыш {amount} ₽!\nНовый банк: {BANK:.2f} ₽")
        CURRENT_BET = 0
        CURRENT_MATCH = "Нет"
    except: pass

@bot.message_handler(commands=['lose'])
def lose(message):
    global CURRENT_BET, CURRENT_MATCH, HISTORY
    if CURRENT_BET == 0: return
    HISTORY.append({'match': CURRENT_MATCH, 'stake': CURRENT_BET, 'odds': CURRENT_ODDS, 'result': 'LOSE', 'profit': -CURRENT_BET})
    save_data(BANK, HISTORY)
    bot.send_message(message.chat.id, f"😔 Проигрыш {CURRENT_BET} ₽ ({CURRENT_MATCH}).\nБанк: {BANK:.2f} ₽")
    CURRENT_BET = 0
    CURRENT_MATCH = "Нет"

@bot.message_handler(commands=['history'])
def show_history(message):
    if not HISTORY: return
    text = "📜 Последние 5 ставок:\n\n"
    for bet in HISTORY[-5:]:
        icon = "✅" if bet['result'] == 'WIN' else "❌"
        text += f"{icon} {bet['match']} | {bet['stake']} ₽ (кэф {bet['odds']})\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['stats'])
def show_stats(message):
    if not HISTORY: return
    total = len(HISTORY)
    wins = sum(1 for b in HISTORY if b['result'] == 'WIN')
    total_profit = sum(b['profit'] for b in HISTORY)
    winrate = (wins / total) * 100
    bot.send_message(message.chat.id, f"📊 Статистика:\nСтавок: {total}\nВыигрышей: {wins} ({winrate:.1f}%)\nПрофит: {total_profit:+.2f} ₽\nБанк: {BANK:.2f} ₽")

app = Flask('')
@app.route('/')
def home(): return "Bot is alive!"
def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
def keep_alive():
    t = Thread(target=run)
    t.start()
keep_alive()

print("=== ЗАПУСК БОТА v7.0 ===")
bot.polling(none_stop=True)
