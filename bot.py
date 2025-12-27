from time import sleep
from telebot import TeleBot
from telebot.types import (Message,
                           KeyboardButton,
                           ReplyKeyboardMarkup,
                           ReplyKeyboardRemove)
import db
from random import choice
import os
from dotenv import load_dotenv

load_dotenv

db.init_db()

TOKEN = os.getenv("TOKEN")
bot = TeleBot(TOKEN)

game = False
night = False

def get_killed(night_flag: bool) -> str:
    if not night_flag:
        u_killed = db.citizen_kill()
        return f"Горожане выгнали: {u_killed}"
    u_killed = db.mafia_kill()
    return f"Мафия убила: {u_killed}"

def autoplay_mafia():
    players_roles = db.get_players_roles() or []
    alive_usernames = db.get_all_alive() or []
    for player_id, role in players_roles:
        bot_name = f"bot_{player_id}"
        if player_id < 5 and bot_name in alive_usernames and role == "mafia":
            targets = [u for u in alive_usernames if u != bot_name]
            if not targets:
                continue
            vote_username = choice(targets)
            db.cast_vote("mafia", vote_username, player_id)

def autoplay_citizen(message: Message):
    players_roles = db.get_players_roles() or []
    alive_usernames = db.get_all_alive() or [] 
    for player_id, _ in players_roles:
        bot_name = f"bot_{player_id}"
        if player_id < 5 and bot_name in alive_usernames:
            targets = [u for u in alive_usernames if u != bot_name]
            if not targets:
                continue
            vote_username = choice(targets)
            db.cast_vote("citizen", vote_username, player_id)
            bot.send_message(message.chat.id, f"{bot_name} проголосовал против {vote_username}")
            sleep(0.5)

def game_loop(message: Message):
    global game, night
    bot.send_message(message.chat.id, "Добро пожаловать в игру! Вам даётся 2 минуты чтобы познакомиться")
    sleep(10)

    while True:
        msg = get_killed(night)
        bot.send_message(message.chat.id, msg)


        if not night:
            bot.send_message(message.chat.id, "Город засыпает, просыпается мафия. Наступила ночь!")
        else:
            bot.send_message(message.chat.id, "Город просыпается. Наступил день!")

        winner = db.check_winner()
        if winner:
            game = False
            bot.send_message(message.chat.id, f"Игра окончена: победили {winner}")
            return
        
        db.clear_round(reset_dead=False)
        night = not night
        alive = db.get_all_alive()
        alive_list = "\n".join(alive) if alive else "никого"
        bot.send_message(message.chat.id, f"В игре:\n{alive_list}")
        sleep(10)
        autoplay_mafia() if night else autoplay_citizen(message)


@bot.message_handler(func=lambda m: m.text.lower() == "готов", chat_types=['private'])
def send_text(message: Message):
    bot.send_message(message.chat.id, f"{message.from_user.first_name} играет!", reply_markup=ReplyKeyboardRemove())
    if db.user_exists(message.from_user.id):
        bot.send_message(message.chat.id, "Вы уже есть")
    else:
        db.insert_player(message.from_user.id, message.from_user.first_name)
        bot.send_message(message.chat.id, "Вы добавлены в игру!")


@bot.message_handler(commands=['start'], chat_types=['private'])
def start(message: Message):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("готов"))
    bot.send_message(message.chat.id, "Если хочешь играть, нажми готов", reply_markup=keyboard)

@bot.message_handler(commands=["game"], chat_types=['group', 'supergroup'])
def game_start(message: Message):
    global game
    players = db.players_amount()
    if players >= 5 and not game:
        db.set_roles()
        players_roles = db.get_players_roles() or []
        mafia_usernames = db.get_mafia_usernames()
        for player_id, role in players_roles:
            try:
                bot.send_message(player_id, role)
                if role == "mafia":
                    bot.send_message(player_id, f"Все члены мафии:\n{mafia_usernames}")
            except Exception:
                print(f"ID: {player_id}, ROLE: {role}")
                continue
        
        game = True
        bot.send_message(message.chat.id, "Игра началась!")
        game_loop(message)
        return
    
    bot.send_message(message.chat.id, "Недостаточно людей! Добавляю ботов")
    for i in range(5):
        bot_name = f"bot_{i}"
        db.insert_player(i, bot_name)
        bot.send_message(message.chat.id, f"{bot_name} добавлен!")
        sleep(0.2) # from time import sleep
    game_start(message)

@bot.message_handler(commands=['kick'], chat_types=['group', "supergroup"])
def kick(message: Message):
    username = " ".join(message.text.split(' ')[1:]).strip() # /kick Артём -> ['kick', "Артём"] -> Артём
    if not username:
        bot.send_message(message.chat.id, "Укажите имя: /kick <имя>")
        return
    
    alive = db.get_all_alive() or []
    if not night:
        if username not in alive:
            bot.send_message(message.chat.id, "Такого имени нет")
            return
        voted = db.cast_vote("citizen", username, message.from_user.id)
        if voted:
            bot.send_message(message.chat.id, "Ваш голос учтён")
            return
        bot.send_message(message.chat.id, "У вас больше нет права голосовать")
        return
    bot.send_message(message.chat.id, "Сейчас ночь - вы не можете никого выгнать")

@bot.message_handler(commands=['kill'], chat_types=['private'])
def kill(message: Message):
    username = " ".join(message.text.split(" ")[1:]).strip()
    if not username:
        bot.send_message(message.chat.id, "Укажите имя: /kill <имя>")
        return
    alive = db.get_all_alive() or []
    mafia_usernames = db.get_mafia_usernames()
    if night and message.from_user.first_name in mafia_usernames:
        if username not in alive:
            bot.send_message(message.chat.id, "Такого имени нет")
            return
        voted = db.cast_vote("mafia", username, message.from_user.id)
        if voted:
            bot.send_message(message.chat.id, "Ваш голос учтён")
            return
        bot.send_message(message.chat.id, "У вас больше нет права голосовать")
        return
    bot.send_message(message.chat.id, "Сейчас день - нельзя убивать")   


bot.polling(non_stop=True)