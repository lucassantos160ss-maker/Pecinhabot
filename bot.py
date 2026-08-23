import time
import telebot
from telebot.apihelper import ApiTelegramException

# Configurações do Bot
TOKEN = "SEU_TOKEN_AQUI"
CHANNEL_ID = "@A_ToolsX"  # Ou o ID numérico do canal
CACHE_EXPIRE_TIME = 60    # Tempo em segundos para revalidar o canal (ex: 1 minuto)

bot = telebot.TeleBot(TOKEN)

# Dicionario simples de cache para evitar spam na API do Telegram: {user_id: (status_bool, timestamp)}
subscription_cache = {}

def check_subscription(user_id):
    current_time = time.time()
    
    # Verifica se já temos o usuário no cache e se ainda está válido
    if user_id in subscription_cache:
        is_subbed, timestamp = subscription_cache[user_id]
        if current_time - timestamp < CACHE_EXPIRE_TIME:
            return is_subbed

    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        # Status válidos que indicam que o usuário está no canal
        if member.status in ['member', 'creator', 'administrator']:
            subscription_cache[user_id] = (True, current_time)
            return True
        else:
        # Se for 'left' ou 'kicked'
            subscription_cache[user_id] = (False, current_time)
            return False
            
    except ApiTelegramException as e:
        # Tratativa para erros de API (ex: bot sem permissão no canal ou usuário não encontrado)
        print(f"Erro na checagem de inscrição: {e}")
        # Em caso de falha da API, é mais seguro liberar ou usar o último estado válido se houver
        if user_id in subscription_cache:
            return subscription_cache[user_id][0]
        return False

@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    
    # Valida a inscrição usando o cache otimizado
    if not check_subscription(user_id):
        markup = telebot.types.InlineKeyboardMarkup()
        btn_channel = telebot.types.InlineKeyboardButton("VER CANAL", url="https://t.me/A_ToolsX")
        markup.add(btn_channel)
        
        bot.send_message(
            message.chat.id,
            "🚀 To use this bot, you must join our channel: https://t.me/A_ToolsX",
            reply_markup=markup
        )
        return

    # Se estiver inscrito, segue o fluxo normal do bot
    bot.send_message(
        message.chat.id,
        "Bem-vindo de volta! Escolha a opção desejada no menu:"
    )

# Mantém o bot rodando de forma estável
if __name__ == "__main__":
    print("Bot iniciado com correção de cache e loop...")
    bot.infinity_polling(skip_pending=True)
