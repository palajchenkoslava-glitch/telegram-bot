import telebot
import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask
from threading import Thread

# ВСТАВЬ СЮДА ТОКЕН ОТ BOTFATHER (тот, что ты получил после /revoke)
TOKEN = 'ТВОЙ_ТОКЕН_ЗДЕСЬ' 
bot = telebot.TeleBot(TOKEN)

DATABASE_URL = os.environ.get('DATABASE_URL')

def init_db():
    if not DATABASE_URL:
        print("!!! ВНИМАНИЕ: DATABASE_URL НЕ НАЙДЕН В ПЕРЕМЕННЫХ RENDER !!!")
        return
    try:
        print("Попытка подключения к базе данных Supabase...")
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bot_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                bank REAL,
                history JSONB
            )
        """)
        cur.execute("""
            INSERT INTO bot_state (id, bank, history) 
            VALUES (1, 110000, '[]') 
            ON CONFLICT (id) DO NOTHING
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("✅ БАЗА ДАННЫХ УСПЕШНО ПОДКЛЮЧЕНА!")
    except Exception as e:
        print(f"❌ ОШИБКА БАЗЫ ДАННЫХ: {e}")

def load_data():
    if not DATABASE_URL:
        return 110000, []
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT bank, history FROM bot_state WHERE id = 1")
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return row['bank'], row['history']
    except Exception as e:
        print(f"❌ ОШИБКА ЗАГРУЗКИ: {e}")
    return 110000, []

def save_data(current_bank, current_history):
    if not DATABASE_URL:
        return
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cur = conn.cursor()
        cur.execute("UPDATE bot_state SET bank = %s, history = %s WHERE id = 1", (current_bank, json.dumps(current_history)))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ ОШИБКА СОХРАНЕНИЯ: {e}")

# Запускаем проверку базы ДО запуска бота
init_db()
BANK, HISTORY = load_data()

CURRENT_BET = 0
CURRENT_ODDS = 0
CURRENT_MATCH = "Нет"

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, f"🟢 Бот Протокола 80/20 v5.0 запущен!\nТвой банк: {BANK:.2f} ₽.\n\nКоманды:\n/bank - баланс\n/bet Сумма Кэф Матч - записать ставку\n/win Сумма - зафиксировать выигрыш\n/lose - зафиксировать проигрыш\n/stats - статистика\n/history - история\n/check - чек-лист")

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
            bot.send_message(message.chat.id, f"⚠️ Ставка {stake} ₽ превышает лимит 3% (макс {limit:.0f} ₽).")
            return
        if stake > BANK:
            bot.send_message(message.chat.id, "❌ Недостаточно средств!")
            return

        BANK -= stake
        CURRENT_BET = stake
        CURRENT_ODDS = odds
        CURRENT_MATCH = match_name
        save_data(BANK, HISTORY) 
        bot.send_message(message.chat.id, f"✅ Ставка принята!\n📌 {match_name}\n💰 {stake} ₽\n📈 Кэф: {odds}\n💵 Потенциал: {stake*odds:.2f} ₽\n\nСвободный банк: {BANK:.2f} ₽")
    except:
        bot.send_message(message.chat.id, "⚠️ Формат: /bet 2500 1.85 Спартак П1")

@bot.message_handler(commands=['win'])
def win(message):
    global BANK, CURRENT_BET, CURRENT_MATCH, HISTORY
    if CURRENT_BET == 0:
        bot.send_message(message.chat.id, "Нет активных ставок.")
        return
    try:
        amount = float(message.text.split()[1])
        BANK += amount
        HISTORY.append({'match': CURRENT_MATCH, 'stake': CURRENT_BET, 'odds': CURRENT_ODDS, 'result': 'WIN', 'profit': amount - CURRENT_BET})
        save_data(BANK, HISTORY) 
        bot.send_message(message.chat.id, f"🎉 Выигрыш {amount} ₽ зачислен!\nНовый банк: {BANK:.2f} ₽")
        CURRENT_BET = 0
        CURRENT_MATCH = "Нет"
    except:
        bot.send_message(message.chat.id, "Формат: /win 4600")

@bot.message_handler(commands=['lose'])
def lose(message):
    global CURRENT_BET, CURRENT_MATCH, HISTORY
    if CURRENT_BET == 0:
        bot.send_message(message.chat.id, "Нет активных ставок.")
        return
    HISTORY.append({'match': CURRENT_MATCH, 'stake': CURRENT_BET, 'odds': CURRENT_ODDS, 'result': 'LOSE', 'profit': -CURRENT_BET})
    save_data(BANK, HISTORY)
    bot.send_message(message.chat.id, f"😔 Ставка {CURRENT_BET} ₽ ({CURRENT_MATCH}) проиграла.\nБанк: {BANK:.2f} ₽")
    CURRENT_BET = 0
    CURRENT_MATCH = "Нет"

@bot.message_handler(commands=['history'])
def show_history(message):
    if not HISTORY:
        bot.send_message(message.chat.id, "История пуста.")
        return
    text = "📜 Последние 5 ставок:\n\n"
    for bet in HISTORY[-5:]:
        icon = "✅" if bet['result'] == 'WIN' else "❌"
        text += f"{icon} {bet['match']} | {bet['stake']} ₽\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['stats'])
def show_stats(message):
    if not HISTORY:
        bot.send_message(message.chat.id, "Нет данных.")
        return
    total = len(HISTORY)
    wins = sum(1 for b in HISTORY if b['result'] == 'WIN')
    total_profit = sum(b['profit'] for b in HISTORY)
    winrate = (wins / total) * 100
    bot.send_message(message.chat.id, f"📊 Статистика:\nСтавок: {total}\nВыигрышей: {wins} ({winrate:.1f}%)\nПрофит: {total_profit:+.2f} ₽\nБанк: {BANK:.2f} ₽")

@bot.message_handler(commands=['check'])
def check_list(message):
    bot.send_message(message.chat.id, "🛑 ЧЕК-ЛИСТ:\n1. Вероятность > 75%?\n2. Нет травм?\n3. Кэф адекватный?\n4. Это не лайв-догон?\n5. Сумма < 3% банка?\n\nЕсли всё 'ДА' — жми /bet!")

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

print("=== ЗАПУСК БОТА v5.0 ===")
bot.polling(none_stop=True)
