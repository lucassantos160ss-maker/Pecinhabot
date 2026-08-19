import sys
import types

# Correção automática para o módulo imghdr removido nas versões recentes do Python
m = types.ModuleType('imghdr')
m.what = lambda *a, **kw: None
sys.modules['imghdr'] = m

import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import logging
import os
import urllib.request
import urllib.parse
import uuid
import json
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

# ----------------------------------------------------
# Mini Servidor Web para atender aos requisitos do Render
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
# Gestão de Estoque e Saldo via JSON
# ----------------------------------------------------
ESTOQUE_FILE = "estoque.json"
SALDOS_FILE = "saldos.json"

def carregar_estoque():
    if os.path.exists(ESTOQUE_FILE):
        try:
            with open(ESTOQUE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    estoque_padrao = {
        "374769": {"bandeira": "Amex", "valor": 1.0, "estoque": ["374769002216776|10/30|0000|LIVE", "374769012120570|06/33|5457|LIVE", "374769065454290|10/30|0000|LIVE"]},
        "406669": {"bandeira": "Visa", "valor": 1.0, "estoque": ["4066699965118237|04/31|321|LIVE", "4066699960586354|04/31|654|LIVE"]},
        "406655": {"bandeira": "Visa", "valor": 1.0, "estoque": ["406655000000001|01/30|987|Nome Exemplo 6"]},
        "250061": {"bandeira": "Mastercard", "valor": 1.0, "estoque": ["250061000000001|03/31|111|Nome Exemplo 7", "250061000000002|04/32|222|Nome Exemplo 8"]}
    }
    salvar_estoque(estoque_padrao)
    return estoque_padrao

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

def registrar_log_pix(user_id, nome, valor, payment_id, status="gerado"):
    try:
        os.makedirs("logs", exist_ok=True)
        hoje = datetime.now().strftime("%Y-%m-%d")
        caminho_arquivo = "logs/pix_logs_{}.json".format(hoje)
        
        logs = []
        if os.path.exists(caminho_arquivo):
            try:
                with open(caminho_arquivo, "r", encoding="utf-8") as f:
                    logs = json.load(f)
            except Exception:
                logs = []
                
        registro_existente = False
        for log in logs:
            if str(log.get("payment_id")) == str(payment_id):
                log["status"] = status
                registro_existente = True
                break
                
        if not registro_existente:
            logs.append({
                "hora": datetime.now().strftime("%H:%M:%S"),
                "user_id": user_id,
                "nome": nome,
                "valor": valor,
                "status": status,
                "payment_id": str(payment_id)
            })
            
        with open(caminho_arquivo, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error("Erro silencioso ao gravar log do PIX: {}".format(e))

# ----------------------------------------------------
# Configuracoes do Bot
# ----------------------------------------------------
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = '8918914171:AAFzDtXIQoW4ttAFy6iGmylYrSfM6Yg8CDM'
PIX_API_KEY = 'APP_USR-3303740326386787-081418-953681c933f125f4e5d8b34f8cf70ea8-3615204291'
PIX_API_URL = 'https://api.mercadopago.com/v1/payments'
URL_SUPORTE = 'https://t.me/Pecinhadosete'
URL_IMAGEM = "https://i.ibb.co/VcSYtKr2/pecinha-inicio.jpg"

SALDOS_USUARIOS = carregar_saldos()
PAGAMENTOS_PENDENTES = {}

def obter_saldo(user_id):
    if user_id not in SALDOS_USUARIOS:
        SALDOS_USUARIOS[user_id] = 0.0
        salvar_saldos(SALDOS_USUARIOS)
    return SALDOS_USUARIOS[user_id]

# ----------------------------------------------------
# Comandos Principais
# ----------------------------------------------------
def start(update, context=None):
    query = update.callback_query
    if query:
        query.answer()
        user = query.from_user
    else:
        user = update.effective_user

    saldo = obter_saldo(user.id)

    texto = (
        "[\u200b]({})"
        "Ola {}, seja muito bem-vindo!\n\n"
        "Atencao: Este e um bot que vende a PRECO DE ATACADO!\n"
        "Todos os nossos produtos estao saindo por apenas R$ 2,00.\n\n"
        "Precisa de ajuda? Chame o Suporte\n"
        "Informacoes Rapidas:\n"
        "- GGs com nomes e CPFs aleatorios.\n"
        "- Logins diretos do painel.\n"
        "- Recargas instantaneas via /pix [valor] (Ex: /pix 10).\n"
        "- GGs Direto do Chk.\n"
        "- Leia as Regras antes de comprar.\n\n"
        "Seu perfil:\n"
        " - ID: `{}`\n"
        " - Saldo: R$ {:.2f}"
    ).format(URL_IMAGEM, user.first_name, user.id, saldo)

    keyboard = [
        [InlineKeyboardButton("GGs Disponiveis", callback_data="ggs_disponiveis")],
        [InlineKeyboardButton("Recarregar", callback_data="recarregar"), InlineKeyboardButton("Suporte", url=URL_SUPORTE)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        query.edit_message_text(
            text=texto,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    else:
        update.message.reply_text(
            text=texto,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

# ----------------------------------------------------
# Menu Dinamico de GGs
# ----------------------------------------------------
def ggs_disponiveis(update, context=None):
    query = update.callback_query
    query.answer()

    user = query.from_user
    saldo = obter_saldo(user.id)
    dados_bins = carregar_estoque()

    texto = (
        "GGs Disponiveis (Preco de Atacado)\n"
        "Escolha a BIN desejada para ver detalhes e confirmar a compra.\n\n"
        "Seu perfil:\n"
        " - ID: `{}`\n"
        " - Saldo: R$ {:.2f}\n"
    ).format(user.id, saldo)

    keyboard = []
    linha = []
    
    for bin_id, info in dados_bins.items():
        qtd = len(info.get("estoque", []))
        valor = info.get("valor", 2.0)
        str_valor = "{:.2f}".format(valor).replace('.', ',')
        
        btn_txt = "{} ({}) | R$ {}".format(bin_id, qtd, str_valor)
        linha.append(InlineKeyboardButton(btn_txt, callback_data="bin_{}".format(bin_id)))
        
        if len(linha) == 2:
            keyboard.append(linha)
            linha = []
            
    if linha:
        keyboard.append(linha)

    keyboard.append([InlineKeyboardButton("Pedir bin especifica", url=URL_SUPORTE)])
    keyboard.append([InlineKeyboardButton("Voltar", callback_data="voltar_inicio")])

    query.edit_message_text(
        text=texto,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def selecionar_bin(update, context=None):
    query = update.callback_query
    query.answer()

    bin_id = query.data.split('_')[1]
    dados_bins = carregar_estoque()
    info = dados_bins.get(bin_id)

    if not info:
        query.answer("BIN nao encontrada!", show_alert=True)
        return

    qtd_disponivel = len(info.get("estoque", []))

    texto = (
        "Detalhes da BIN: {}\n"
        "Bandeira: {}\n"
        "Preco unitario: R$ {:.2f}\n"
        "Estoque disponivel: {} unidades\n\n"
        "Deseja realizar a compra agora usando o seu saldo?"
    ).format(bin_id, info.get('bandeira', 'Desconhecida'), info.get('valor', 2.0), qtd_disponivel)

    keyboard = [
        [InlineKeyboardButton("Confirmar e Comprar", callback_data="comprar_{}".format(bin_id))],
        [InlineKeyboardButton("Voltar", callback_data="ggs_disponiveis")]
    ]

    query.edit_message_text(text=texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

def efetuar_compra(update, context=None):
    query = update.callback_query
    user = query.from_user
    bin_id = query.data.split('_')[1]
    
    dados_bins = carregar_estoque()
    info = dados_bins.get(bin_id)

    if not info or len(info.get("estoque", [])) == 0:
        query.answer("Estoque esgotado para esta BIN!", show_alert=True)
        return

    preco = info.get("valor", 2.0)
    saldo_atual = obter_saldo(user.id)

    if saldo_atual < preco:
        query.answer("Saldo insuficiente! Recarregue via PIX.", show_alert=True)
        return

    SALDOS_USUARIOS[user.id] = saldo_atual - preco
    salvar_saldos(SALDOS_USUARIOS)

    item_comprado = info["estoque"].pop(0)
    salvar_estoque(dados_bins)

    texto_sucesso = (
        "Compra Aprovada com Sucesso!\n\n"
        "BIN: {} ({})\n"
        "Dado entregue:\n`{}`\n\n"
        "Novo Saldo: R$ {:.2f}"
    ).format(bin_id, info.get('bandeira'), item_comprado, SALDOS_USUARIOS[user.id])

    keyboard = [
        [InlineKeyboardButton("Comprar Mais", callback_data="ggs_disponiveis")],
        [InlineKeyboardButton("Menu Principal", callback_data="voltar_inicio")]
    ]

    query.edit_message_text(text=texto_sucesso, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# ----------------------------------------------------
# Sistema de Recarga PIX
# ----------------------------------------------------
def pix_command(update, text_args=""):
    user = update.effective_user
    
    if not text_args:
        update.message.reply_text("Por favor, informe o valor. Exemplo: /pix 10", parse_mode="Markdown")
        return

    try:
        valor = float(text_args.replace(',', '.'))
        if valor <= 0:
            raise ValueError
    except ValueError:
        update.message.reply_text("Valor invalido. Digite um numero maior que zero. Ex: /pix 5", parse_mode="Markdown")
        return

    headers = {
        "Authorization": "Bearer {}".format(PIX_API_KEY),
        "Content-Type": "application/json",
        "X-Idempotency-Key": str(uuid.uuid4())
    }

    payload = {
        "transaction_amount": valor,
        "description": "Recarga de Saldo - Usuario {}".format(user.id),
        "payment_method_id": "pix",
        "payer": {
            "email": "user_{}@bot.com".format(user.id),
            "first_name": user.first_name or "Usuario",
            "last_name": "Telegram"
        }
    }

    try:
        data_bytes = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(PIX_API_URL, data=data_bytes, headers=headers, method='POST')
        
        with urllib.request.urlopen(req) as response:
            if response.status in [200, 201]:
                res_data = json.loads(response.read().decode('utf-8'))
                payment_id = str(res_data["id"])
                qr_code = res_data["point_of_interaction"]["transaction_data"]["qr_code"]
                
                PAGAMENTOS_PENDENTES[payment_id] = {"user_id": user.id, "valor": valor}
                registrar_log_pix(user.id, user.first_name, valor, payment_id, status="gerado")

                texto = (
                    "Cobranca PIX Gerada com Sucesso!\n\n"
                    "Valor: R$ {:.2f}\n"
                    "ID da Transacao: `{}`\n\n"
                    "Copie o codigo abaixo e pague no seu aplicativo de banco:\n\n"
                    "`{}`\n\n"
                    "Apos pagar, clique no botao abaixo para aprovar seu saldo."
                ).format(valor, payment_id, qr_code)

                keyboard = [
                    [InlineKeyboardButton("Verificar Pagamento", callback_data="verificar_pix_{}".format(payment_id))],
                    [InlineKeyboardButton("Voltar", callback_data="voltar_inicio")]
                ]

                update.message.reply_text(texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                update.message.reply_text("Ocorreu um erro ao gerar a cobranca PIX no Mercado Pago.")
    except Exception as e:
        logging.error("Erro no comando /pix: {}".format(e))
        update.message.reply_text("Erro de conexao com o servidor de pagamento.")

def verificar_pix_callback(update, context=None):
    query = update.callback_query

    try:
        payment_id = query.data.replace("verificar_pix_", "").strip()
        user = query.from_user

        headers = {"Authorization": "Bearer {}".format(PIX_API_KEY)}
        req = urllib.request.Request("{}/{}".format(PIX_API_URL, payment_id), headers=headers, method='GET')

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                res_data = json.loads(response.read().decode('utf-8'))
                status = res_data.get("status")

                if status == "approved":
                    valor = float(res_data.get("transaction_amount", 0.0))

                    saldo_atual = obter_saldo(user.id)
                    SALDOS_USUARIOS[user.id] = saldo_atual + valor
                    salvar_saldos(SALDOS_USUARIOS)

                    registrar_log_pix(user.id, user.first_name, valor, payment_id, status="aprovado")

                    texto = (
                        "Pagamento Confirmado!\n\n"
                        "Valor creditado: R$ {:.2f}\n"
                        "Seu novo saldo e: R$ {:.2f}\n\n"
                        "Agora voce ja pode realizar suas compras!"
                    ).format(valor, SALDOS_USUARIOS[user.id])
                    keyboard = [[InlineKeyboardButton("GGs Disponiveis", callback_data="ggs_disponiveis")]]
                    
                    query.answer("Pagamento Aprovado!")
                    query.edit_message_text(text=texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
                else:
                    query.answer(
                        "Pagamento ainda nao identificado (Status: {}). Aguarde alguns instantes e tente novamente.".format(status), 
                        show_alert=True
                    )
            else:
                query.answer("Nao foi possivel consultar o pagamento. Tente novamente.", show_alert=True)

    except Exception as e:
        logging.error("Erro ao verificar PIX: {}".format(e))
        query.answer("Ocorreu um erro interno na consulta. Tente novamente.", show_alert=True)

def recarregar_callback(update, context=None):
    query = update.callback_query
    query.answer()

    texto = (
        "Como recarregar seu saldo:\n\n"
        "Envie o comando /pix seguido do valor que deseja recarregar diretamente no chat.\n\n"
        "Exemplos:\n"
        "- /pix 2 - Recarrega R$ 2,00\n"
        "- /pix 10 - Recarrega R$ 10,00\n"
        "- /pix 50 - Recarrega R$ 50,00\n\n"
        "O QR Code e o Copia e Cola serao gerados automaticamente!"
    )
    keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar_inicio")]]
    query.edit_message_text(text=texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

voltar_inicio = start

# ----------------------------------------------------
# Comandos Admin
# ----------------------------------------------------
ADMINS = [7970384949, 7622528057]

def admpix(update, text_args=""):
    user_id = update.effective_user.id

    if user_id not in ADMINS:
        update.message.reply_text("Voce nao tem permissao para usar este comando.")
        return

    partes = text_args.split()
    if len(partes) < 2:
        update.message.reply_text(
            "Uso correto: /admpix <ID_DO_USUARIO> <VALOR>\n\n"
            "Exemplo: /admpix 123456789 50",
            parse_mode="Markdown"
        )
        return

    try:
        target_id = int(partes[0])
        valor = float(partes[1].replace(',', '.'))

        if valor <= 0:
            update.message.reply_text("O valor deve ser maior que zero.")
            return

        saldo_atual = obter_saldo(target_id)
        novo_saldo = saldo_atual + valor
        SALDOS_USUARIOS[target_id] = novo_saldo
        salvar_saldos(SALDOS_USUARIOS)

        update.message.reply_text(
            "Saldo Adicionado com Sucesso!\n\n"
            "Usuario Receptante (ID): `{}`\n"
            "Valor Adicionado: R$ {:.2f}\n"
            "Novo Saldo do Usuario: R$ {:.2f}".format(target_id, valor, novo_saldo),
            parse_mode="Markdown"
        )

        try:
            updater.bot.send_message(
                chat_id=target_id,
                text="Voce recebeu uma recarga de saldo!\n\nValor: R$ {:.2f}\nSeu Novo Saldo: R$ {:.2f}".format(valor, novo_saldo),
                parse_mode="Markdown"
            )
        except Exception:
            pass

    except ValueError:
        update.message.reply_text("Formato invalido! Certifique-se de que o ID e um numero e o valor e numerico.", parse_mode="Markdown")

def addestoque(update, text_args=""):
    user_id = update.effective_user.id

    if user_id not in ADMINS:
        update.message.reply_text("Voce não tem permissão para usar este comando.")
        return

    partes = text_args.split(' ', 1)
    if len(partes) < 2:
        update.message.reply_text(
            "Uso correto:\n`/addestoque <BIN> <dado_ou_cartao>`\n\n"
            "Exemplo:\n`/addestoque 374769 374769002216776|10/30|0000|LIVE`",
            parse_mode="Markdown"
        )
        return

    bin_id = partes[0].strip()
    novo_item = partes[1].strip()

    dados_bins = carregar_estoque()

    if bin_id not in dados_bins:
        # Se a BIN não existir, cria uma nova automaticamente com bandeira "Desconhecida" e valor 2.0
        dados_bins[bin_id] = {"bandeira": "Cartao", "valor": 2.0, "estoque": []}

    dados_bins[bin_id]["estoque"].append(novo_item)
    salvar_estoque(dados_bins)

    qtd_total = len(dados_bins[bin_id]["estoque"])
    update.message.reply_text(
        "Estoque Atualizado com Sucesso!\n\n"
        "BIN: `{}`\n"
        "Item adicionado:\n`{}`\n\n"
        "Total agora nesta BIN: {} unidades".format(bin_id, novo_item, qtd_total),
        parse_mode="Markdown"
    )

def verestoque(update):
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        return

    dados_bins = carregar_estoque()
    texto = "Resumo do Estoque Atual:\n\n"
    for bin_id, info in dados_bins.items():
        qtd = len(info.get("estoque", []))
        texto += "- BIN `{}` ({}) : {} unidades\n".format(bin_id, info.get('bandeira'), qtd)

    update.message.reply_text(texto, parse_mode="Markdown")

# ----------------------------------------------------
# Roteador de Mensagens de Texto
# ----------------------------------------------------
def tratar_mensagem(update, context):
    if not update.message or not update.message.text:
        return
    
    texto_msg = update.message.text.strip()
    
    if texto_msg.startswith("/start"):
        start(update)
    elif texto_msg.startswith("/pix"):
        partes = texto_msg.split(' ', 1)
        args = partes[1] if len(partes) > 1 else ""
        pix_command(update, args)
    elif texto_msg.startswith("/admpix"):
        partes = texto_msg.split(' ', 1)
        args = partes[1] if len(partes) > 1 else ""
        admpix(update, args)
    elif texto_msg.startswith("/addestoque"):
        partes = texto_msg.split(' ', 1)
        args = partes[1] if len(partes) > 1 else ""
        addestoque(update, args)
    elif texto_msg.startswith("/verestoque"):
        verestoque(update)

# ----------------------------------------------------
# Main (Inicializacao)
# ----------------------------------------------------
if __name__ == '__main__':
    # Inicia o servidor HTTP em background para o Render não derrubar o serviço
    t = Thread(target=iniciar_servidor_web)
    t.daemon = True
    t.start()

    updater = Updater(TOKEN)
    dp = updater.dispatcher

    dp.add_handler(MessageHandler(Filters.text, tratar_mensagem))

    dp.add_handler(CallbackQueryHandler(voltar_inicio, pattern="^voltar_inicio$"))
    dp.add_handler(CallbackQueryHandler(ggs_disponiveis, pattern="^ggs_disponiveis$"))
    dp.add_handler(CallbackQueryHandler(selecionar_bin, pattern="^bin_"))
    dp.add_handler(CallbackQueryHandler(efetuar_compra, pattern="^comprar_"))
    dp.add_handler(CallbackQueryHandler(recarregar_callback, pattern="^recarregar$"))
    dp.add_handler(CallbackQueryHandler(verificar_pix_callback, pattern="^verificar_pix_"))

    print("Bot rodando com painel de estoque dinamico e servidor web ativo...")
    updater.start_polling()
    updater.idle()
