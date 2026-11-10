import telebot
import json
import os
from flask import Flask
from threading import Thread

# ВСТАВЬ СЮДА СВОЙ ТОКЕН
TOKEN = '9263476588:AAGZNVV6iKQIYAvQL96uOMafnjdqT5zO6Bc' 
bot = telebot.TeleBot(TOKEN)

DATA_FILE = 'bank_data.json'

# Обновленная функция загрузки (теперь хранит банк и историю)
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            return data.get('bank', 110000), data.get('history', [])
    return 110000, []

# Обновленная функция сохранения
def save_data(current_bank, current_history):
    with open(DATA_FILE, 'w') as f:
        json.dump({'bank': current_bank, 'history': current_history}, f)

BANK, HISTORY = load_data()
CURRENT_BET = 0
CURRENT_ODDS = 0
CURRENT_MATCH = "Нет"

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, f"🟢 Бот Протокола 80/20 v4.0 запущен!\nТвой банк: {BANK:.2f} ₽.\n\nКоманды:\n/bank - баланс\n/bet Сумма Кэф Матч - записать ставку\n/win Сумма - зафиксировать выигрыш\n/lose - зафиксировать проигрыш\n/stats - твоя статистика и ROI\n/history - последние 5 ставок\n/check - чек-лист перед ставкой")

@bot.message_handler(commands=['check'])
def check_list(message):
    bot.send_message(message.chat.id, "🛑 СТОП! Прогони ставку по Протоколу 80/20:\n1. Вероятность > 75%?\n2. Нет скрытых травм?\n3. Кэф адекватный (валуй)?\n4. Это не лайв-догон?\n5. Сумма < 3% от банка?\n\nЕсли на все ответ 'ДА' — жми /bet!")

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
            bot.send_message(message.chat.id, f"⚠️ ВНИМАНИЕ! Ставка {stake} ₽ превышает лимит 3% (максимум {limit:.0f} ₽).")
            return

        if stake > BANK:
            bot.send_message(message.chat.id, "❌ Недостаточно средств!")
            return

        BANK -= stake
        CURRENT_BET = stake
        CURRENT_ODDS = odds
        CURRENT_MATCH = match_name
        save_data(BANK, HISTORY) 
        
        bot.send_message(message.chat.id, f"✅ Ставка принята!\n📌 Матч: {match_name}\n💰 Сумма: {stake} ₽\n📈 Кэф: {odds}\n💵 Потенциал: {stake*odds:.2f} ₽\n\nСвободный банк: {BANK:.2f} ₽")
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
        # Записываем в историю
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
    # Записываем в историю
    HISTORY.append({'match': CURRENT_MATCH, 'stake': CURRENT_BET, 'odds': CURRENT_ODDS, 'result': 'LOSE', 'profit': -CURRENT_BET})
    save_data(BANK, HISTORY)
    
    bot.send_message(message.chat.id, f"😔 Ставка на {CURRENT_BET} ₽ ({CURRENT_MATCH}) проиграла.\nБанк: {BANK:.2f} ₽")
    CURRENT_BET = 0
    CURRENT_MATCH = "Нет"

@bot.message_handler(commands=['history'])
def show_history(message):
    if not HISTORY:
        bot.send_message(message.chat.id, "История пуста.")
        return
    last_5 = HISTORY[-5:] # Берем последние 5
    text = "📜 Последние 5 ставок:\n\n"
    for bet in last_5:
        icon = "✅" if bet['result'] == 'WIN' else "❌"
        text += f"{icon} {bet['match']} | {bet['stake']} ₽ (кэф {bet['odds']})\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['stats'])
def show_stats(message):
    if not HISTORY:
        bot.send_message(message.chat.id, "Нет данных для статистики.")
        return
    
    total = len(HISTORY)
    wins = sum(1 for b in HISTORY if b['result'] == 'WIN')
    total_profit = sum(b['profit'] for b in HISTORY)
    winrate = (wins / total) * 100
    
    text = (f"📊 Твоя статистика:\n"
            f"Всего ставок: {total}\n"
            f"Выигрышей: {wins} ({winrate:.1f}%)\n"
            f"Общий профит: {total_profit:+.2f} ₽\n"
            f"Текущий банк: {BANK:.2f} ₽")
    bot.send_message(message.chat.id, text)

# --- ХАК ДЛЯ RENDER ---
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

print("Бот версии 4.0 запущен в облаке!")
bot.polling(none_stop=True)
