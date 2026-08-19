import sys
import types
import re # Necessário para limpar a BIN
import logging
import os
import urllib.request
import urllib.parse
import uuid
import json
import ssl
from datetime import datetime
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
)

# Correção para módulos removidos
m = types.ModuleType('imghdr')
m.what = lambda *a, **kw: None
sys.modules['imghdr'] = m
ssl._create_default_https_context = ssl._create_unverified_context

# ----------------------------------------------------
# Mini Servidor Web (Keep-Alive)
# ----------------------------------------------------
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running successfully!")

def iniciar_servidor_web():
    porta = int(os.environ.get("PORT", 10000))
    servidor = HTTPServer(("0.0.0.0", porta), DummyHandler)
    servidor.serve_forever()

# ----------------------------------------------------
# Gestão de Estoque e Saldo
# ----------------------------------------------------
ESTOQUE_FILE = "estoque.json"
SALDOS_FILE = "saldos.json"

def carregar_estoque():
    if os.path.exists(ESTOQUE_FILE):
        try:
            with open(ESTOQUE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def salvar_estoque(dados):
    with open(ESTOQUE_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

def carregar_saldos():
    if os.path.exists(SALDOS_FILE):
        try:
            with open(SALDOS_FILE, "r", encoding="utf-8") as f:
                dados = json.load(f)
                return {int(k): float(v) for k, v in dados.items()}
        except Exception:
            pass
    return {}

def salvar_saldos(saldos):
    with open(SALDOS_FILE, "w", encoding="utf-8") as f:
        json.dump(saldos, f, ensure_ascii=False, indent=4)

def obter_saldo(user_id):
    saldos = carregar_saldos()
    return saldos.get(user_id, 0.0)

def atualizar_saldo(user_id, novo_valor):
    saldos = carregar_saldos()
    saldos[user_id] = float(novo_valor)
    salvar_saldos(saldos)

# ----------------------------------------------------
# Configuracoes
# ----------------------------------------------------
logging.basicConfig(level=logging.INFO)
TOKEN = '8918914171:AAFzDtXIQoW4ttAFy6iGmylYrSfM6Yg8CDM'
PIX_API_KEY = 'APP_USR-3303740326386787-081418-953681c933f125f4e5d8b34f8cf70ea8-3615204291'
PIX_API_URL = 'https://api.mercadopago.com/v1/payments'
URL_SUPORTE = 'https://t.me/Pecinhadosete'
URL_IMAGEM = "https://i.ibb.co/VcSYtKr2/pecinha-inicio.jpg"
ADMINS = [7970384949, 7622528057]

# ----------------------------------------------------
# Funções de Bot
# ----------------------------------------------------
def start(update, context=None):
    query = update.callback_query
    user = query.from_user if query else update.effective_user
    saldo = obter_saldo(user.id)
    texto = "Ola {}, saldo: R$ {:.2f}".format(user.first_name, saldo)
    
    keyboard = [
        [InlineKeyboardButton("GGs Disponiveis", callback_data="ggs_disponiveis")],
        [InlineKeyboardButton("Suporte", url=URL_SUPORTE)]
    ]
    if query:
        query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        update.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(keyboard))

def ggs_disponiveis(update, context=None):
    query = update.callback_query
    query.answer()
    dados_bins = carregar_estoque()
    keyboard = []
    for bin_id, info in dados_bins.items():
        qtd = len(info.get("estoque", []))
        keyboard.append([InlineKeyboardButton("{} ({})".format(bin_id, qtd), callback_data="bin_{}".format(bin_id))])
    keyboard.append([InlineKeyboardButton("Voltar", callback_data="voltar_inicio")])
    query.edit_message_text("Escolha a BIN:", reply_markup=InlineKeyboardMarkup(keyboard))

def addestoque(update, text_args=""):
    user_id = update.effective_user.id
    if user_id not in ADMINS: return

    partes = text_args.split(' ', 1)
    if len(partes) < 2:
        update.message.reply_text("Uso: /addestoque <BIN> <lista>")
        return

    # LIMPEZA OBRIGATÓRIA DA BIN (Remove tudo que não for número)
    bin_digitada = re.sub(r'\D', '', partes[0])
    
    lista_bruta = partes[1].replace(',', '\n')
    cartoes = [c.strip() for c in lista_bruta.split('\n') if c.strip()]

    dados_bins = carregar_estoque()
    if bin_digitada not in dados_bins:
        dados_bins[bin_digitada] = {"bandeira": "Cartao", "valor": 1.0, "estoque": []}

    dados_bins[bin_digitada]["estoque"].extend(cartoes)
    salvar_estoque(dados_bins)
    update.message.reply_text("✅ BIN `{}` atualizada! Total: {}".format(bin_digitada, len(dados_bins[bin_digitada]["estoque"])), parse_mode="Markdown")

def tratar_mensagem(update, context):
    if not update.message or not update.message.text: return
    txt = update.message.text
    if txt.startswith("/start"): start(update)
    elif txt.startswith("/addestoque"): addestoque(update, txt.replace("/addestoque ", ""))

# ----------------------------------------------------
# Main
# ----------------------------------------------------
if __name__ == '__main__':
    Thread(target=iniciar_servidor_web, daemon=True).start()
    updater = Updater(TOKEN)
    dp = updater.dispatcher
    dp.add_handler(MessageHandler(Filters.text, tratar_mensagem))
    dp.add_handler(CallbackQueryHandler(ggs_disponiveis, pattern="^ggs_disponiveis$"))
    dp.add_handler(CallbackQueryHandler(start, pattern="^voltar_inicio$"))
    updater.start_polling()
    updater.idle()
