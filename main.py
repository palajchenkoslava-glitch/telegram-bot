import telebot
import json
import os
from flask import Flask
from threading import Thread

# ВСТАВЬ СЮДА СВОЙ НОВЫЙ ТОКЕН ОТ BOTFATHER
TOKEN = '9263476588:AAGZNVV6iKQIYAvQL96uOMafnjdqT5zO6Bc' 
bot = telebot.TeleBot(TOKEN)

# Файл, где будет храниться наш банк
DATA_FILE = 'bank_data.json'

# Функция для загрузки банка
def load_bank():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            return data.get('bank', 110000)
    return 110000

# Функция для сохранения банка
def save_bank(current_bank):
    with open(DATA_FILE, 'w') as f:
        json.dump({'bank': current_bank}, f)

BANK = load_bank()
CURRENT_BET = 0
CURRENT_ODDS = 0
CURRENT_MATCH = "Нет"

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, f"🟢 Бот Протокола 80/20 v3.0 запущен!\nТвой текущий банк: {BANK:.2f} ₽.\n\nКоманды:\n/bank - проверить баланс\n/bet Сумма Кэф Матч - записать ставку\n/win Сумма - зафиксировать выигрыш\n/lose - зафиксировать проигрыш")

@bot.message_handler(commands=['bank'])
def show_bank(message):
    bet_info = f"{CURRENT_BET} ₽ на {CURRENT_MATCH} (кэф {CURRENT_ODDS})" if CURRENT_BET > 0 else "Нет"
    bot.send_message(message.chat.id, f"💰 Текущий банк: {BANK:.2f} ₽\n🎯 В игре: {bet_info}")

@bot.message_handler(commands=['bet'])
def place_bet(message):
    global BANK, CURRENT_BET, CURRENT_ODDS, CURRENT_MATCH
    try:
        parts = message.text.split(maxsplit=3) 
        if len(parts) < 3:
            raise ValueError
            
        stake = float(parts[1])
        odds = float(parts[2])
        match_name = parts[3] if len(parts) > 3 else "Неизвестный матч"
        
        limit = BANK * 0.03
        if stake > limit:
            bot.send_message(message.chat.id, f"⚠️ ВНИМАНИЕ! Ставка {stake} ₽ превышает наш лимит в 3% (максимум {limit:.0f} ₽).")
            return

        if stake > BANK:
            bot.send_message(message.chat.id, "❌ Ошибка: Недостаточно средств в банке!")
            return

        BANK -= stake
        CURRENT_BET = stake
        CURRENT_ODDS = odds
        CURRENT_MATCH = match_name
        save_bank(BANK) 
        
        potential_win = stake * odds
        
        bot.send_message(message.chat.id, f"✅ Ставка принята!\n📌 Матч: {match_name}\n💰 Сумма: {stake} ₽\n📈 Кэф: {odds}\n💵 Потенциальный выигрыш: {potential_win:.2f} ₽\n\nСвободный банк: {BANK:.2f} ₽")
    except:
        bot.send_message(message.chat.id, "⚠️ Неверный формат. Пиши так: /bet 2500 1.85 Спартак П1")

@bot.message_handler(commands=['win'])
def win(message):
    global BANK, CURRENT_BET, CURRENT_MATCH
    if CURRENT_BET == 0:
        bot.send_message(message.chat.id, "У тебя нет активных ставок.")
        return
    try:
        amount = float(message.text.split()[1])
        BANK += amount
        save_bank(BANK) 
        bot.send_message(message.chat.id, f"🎉 Выигрыш {amount} ₽ зачислен на счет!\nМатч: {CURRENT_MATCH}\nНовый банк: {BANK:.2f} ₽")
        CURRENT_BET = 0
        CURRENT_MATCH = "Нет"
    except:
        bot.send_message(message.chat.id, "Формат: /win 4600")

@bot.message_handler(commands=['lose'])
def lose(message):
    global CURRENT_BET, CURRENT_MATCH
    if CURRENT_BET == 0:
        bot.send_message(message.chat.id, "У тебя нет активных ставок.")
        return
    bot.send_message(message.chat.id, f"😔 Ставка на {CURRENT_BET} ₽ ({CURRENT_MATCH}) проиграла.\nБанк остается {BANK:.2f} ₽")
    CURRENT_BET = 0
    CURRENT_MATCH = "Нет"

# --- ХАК ДЛЯ RENDER (Чтобы сервер не выключал бота) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()
# -----------------------------------------------------

print("Бот версии 3.0 запущен в облаке!")
bot.polling(none_stop=True)
