import logging
import os
import urllib.request
import urllib.parse
import uuid
import json
import asyncio
from datetime import datetime
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
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
# Gestão de Estoque, Saldo e Histórico via JSON
# ----------------------------------------------------
ESTOQUE_FILE = "estoque.json"
SALDOS_FILE = "saldos.json"
HISTORICO_FILE = "historico_compras.json"

# Dicionário de preços das BINs fornecidas
PRECOS_BINS = {
    "250060": 6.0, "250061": 12.0, "406655": 6.0, "406669": 5.0,
    "414718": 4.0, "414720": 2.0, "415896": 4.0, "417938": 5.0,
    "421960": 5.0, "422061": 4.0, "425850": 7.0, "449773": 7.0,
    "459384": 5.0, "464611": 8.0, "466068": 5.0, "466070": 5.0,
    "478200": 4.0, "485464": 6.0, "489389": 6.0, "498407": 7.0,
    "512267": 6.0, "512707": 8.0, "515104": 8.0, "515601": 10.0
}

def gerar_estoque_ficticio(bin_id, quantidade=50):
    """Gera itens fictícios para a BIN para simular um grande estoque."""
    itens = []
    for i in range(1, quantidade + 1):
        num_cartao = f"{bin_id}{i:010d}"
        itens.append(f"{num_cartao}|12|2029|999|Nome Ficticio|12345678900")
    return itens

def carregar_estoque():
    dados_atuais = {}
    if os.path.exists(ESTOQUE_FILE):
        try:
            with open(ESTOQUE_FILE, "r", encoding="utf-8") as f:
                dados_atuais = json.load(f)
        except Exception:
            dados_atuais = {}

    # Preenche as BINs que faltarem ou que estiverem sem estoque com dados fictícios
    alterou = False
    for bin_key in PRECOS_BINS.keys():
        bandeira = "Visa" if bin_key.startswith("4") else ("Mastercard" if bin_key.startswith("5") or bin_key.startswith("2") else "Outra")
        if bin_key not in dados_atuais or not dados_atuais[bin_key].get("estoque"):
            dados_atuais[bin_key] = {
                "bandeira": bandeira,
                "estoque": gerar_estoque_ficticio(bin_key)
            }
            alterou = True

    if alterou:
        salvar_estoque(dados_atuais)

    return dados_atuais

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
    if user_id not in saldos:
        saldos[user_id] = 0.0
        salvar_saldos(saldos)
    return saldos[user_id]

def atualizar_saldo(user_id, novo_valor):
    saldos = carregar_saldos()
    saldos[user_id] = float(novo_valor)
    salvar_saldos(saldos)

def carregar_historico():
    if os.path.exists(HISTORICO_FILE):
        try:
            with open(HISTORICO_FILE, "r", encoding="utf-8") as f:
                dados = json.load(f)
            return {int(k): v for k, v in dados.items()}
        except Exception:
            pass
    return {}

def salvar_historico(dados):
    with open(HISTORICO_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

def adicionar_historico_usuario(user_id, item, bin_id, bandeira):
    historico = carregar_historico()
    user_str = str(user_id)
    if user_str not in historico:
        historico[user_str] = []
    historico[user_str].append({
        "bin": bin_id,
        "bandeira": bandeira,
        "item": item,
        "data": datetime.now().strftime("%d/%m/%Y %H:%M")
    })
    salvar_historico(historico)

def registrar_log_pix(user_id, nome, valor, payment_id, status="gerado"):
    try:
        os.makedirs("logs", exist_ok=True)
        hoje = datetime.now().strftime("%Y-%m-%d")
        caminho_arquivo = f"logs/pix_logs_{hoje}.json"
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
        logging.error(f"Erro silencioso ao gravar log do PIX: {e}")

# ----------------------------------------------------
# Configurações do Bot
# ----------------------------------------------------
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
TOKEN = '8918914171:AAEQQQ1u1Og7S8runtt0_OWDeIgjlyRct2A'

MP_PUBLIC_KEY = 'APP_USR-b2f9aa36-d667-48e6-873b-47550fb30e90'
MP_ACCESS_TOKEN = 'APP_USR-3303740326386787-081418-953681c933f125f4e5d8b34f8cf70ea8-3615204291'
PIX_API_URL = 'https://api.mercadopago.com/v1/payments'
URL_SUPORTE = 'https://t.me/Pecinhadosete'
URL_IMAGEM = "https://i.ibb.co/VcSYtKr2/pecinha-inicio.jpg"
PAGAMENTOS_PENDENTES = {}

def calcular_preco(bin_id):
    return PRECOS_BINS.get(bin_id, 5.0)

# ----------------------------------------------------
# Comandos Principais
# ----------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        user = query.from_user
    else:
        user = update.effective_user

    saldo = obter_saldo(user.id)
    texto = (
        f"[\u200b]({URL_IMAGEM})"
        f"Olá {user.first_name}, seja muito bem-vindo!\n\n"
        "Atenção: Este é um bot que vende Geradas!\n"
        "Todos os nossos produtos estão com novos preços!\n\n"
        "Precisa de ajuda? Chame o Suporte\n"
        "Informações Rápidas:\n"
        "- GGs com nomes e CPFs aleatórios.\n"
        "- Logins diretos do painel.\n"
        "- Recargas instantâneas via /pix [valor] (Ex: /pix 10).\n"
        "- Leia as Regras antes de comprar.\n\n"
        "Seu perfil:\n"
        f" - ID: `{user.id}`\n"
        f" - Saldo: R$ {saldo:.2f}"
    )
    keyboard = [
        [InlineKeyboardButton("GGs Disponíveis", callback_data="ggs_disponiveis")],
        [InlineKeyboardButton("Meus Cartões / Histórico", callback_data="historico_compras")],
        [InlineKeyboardButton("Recarregar", callback_data="recarregar"), InlineKeyboardButton("Suporte", url=URL_SUPORTE)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(text=texto, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(text=texto, parse_mode="Markdown", reply_markup=reply_markup)

async def historico_compras_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    historico = carregar_historico()
    compras_usuario = historico.get(str(user.id), [])

    if not compras_usuario:
        texto = "📦 Você ainda não realizou nenhuma compra de cartões."
    else:
        texto = "📦 **Seu Histórico de Cartões Comprados:**\n\n"
        for idx, compra in enumerate(reversed(compras_usuario[-15:]), 1):
            texto += f"#{idx} - **BIN:** {compra['bin']} ({compra['bandeira']})\n"
            texto += f"📅 {compra['data']}\n"
            texto += f"`{compra['item']}`\n\n"

    keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar_inicio")]]
    await query.edit_message_text(text=texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def ggs_disponiveis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    saldo = obter_saldo(user.id)
    dados_bins = carregar_estoque()

    texto = (
        "GGs Disponíveis\n"
        "Escolha a BIN desejada para ver detalhes e confirmar a compra.\n\n"
        "Seu perfil:\n"
        f" - ID: `{user.id}`\n"
        f" - Saldo: R$ {saldo:.2f}\n"
    )

    keyboard = []
    linha = []

    # Monta os botões exatamente no formato: BIN | R$ VALOR (sem a quantidade de estoque)
    for bin_id in PRECOS_BINS.keys():
        valor = PRECOS_BINS[bin_id]
        str_valor = f"{valor:.2f}".replace('.', ',').rstrip('0').rstrip(',') if valor.is_integer() else f"{valor:.2f}".replace('.', ',')
        btn_txt = f"{bin_id} | R$ {str_valor}"
        
        linha.append(InlineKeyboardButton(btn_txt, callback_data=f"bin_{bin_id}"))

        if len(linha) == 2:
            keyboard.append(linha)
            linha = []

    if linha:
        keyboard.append(linha)

    keyboard.append([InlineKeyboardButton("Pedir bin específica", url=URL_SUPORTE)])
    keyboard.append([InlineKeyboardButton("Voltar", callback_data="voltar_inicio")])

    await query.edit_message_text(text=texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def selecionar_bin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    bin_id = query.data.split('_')[1]
    dados_bins = carregar_estoque()
    info = dados_bins.get(bin_id)

    if not info:
        await query.answer("BIN não encontrada!", show_alert=True)
        return

    bandeira_nome = info.get('bandeira', 'Desconhecida')
    preco = calcular_preco(bin_id)

    texto = (
        f"Detalhes da BIN: {bin_id}\n"
        f"Bandeira: {bandeira_nome}\n"
        f"Preço unitário: R$ {preco:.2f}\n\n"
        "Deseja realizar a compra agora usando o seu saldo?"
    )

    keyboard = [
        [InlineKeyboardButton("Confirmar e Comprar", callback_data=f"comprar_{bin_id}")],
        [InlineKeyboardButton("Voltar", callback_data="ggs_disponiveis")]
    ]

    await query.edit_message_text(text=texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def efetuar_compra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    bin_id = query.data.split('_')[1]

    dados_bins = carregar_estoque()
    info = dados_bins.get(bin_id)

    if not info or len(info.get("estoque", [])) == 0:
        await query.answer("Estoque esgotado para esta BIN!", show_alert=True)
        return

    bandeira_nome = info.get('bandeira', 'Cartão')
    preco = calcular_preco(bin_id)
    saldo_atual = obter_saldo(user.id)

    if saldo_atual < preco:
        await query.answer("Saldo insuficiente! Recarregue via PIX.", show_alert=True)
        return

    novo_saldo = saldo_atual - preco
    atualizar_saldo(user.id, novo_saldo)

    # Retira o item do estoque e salva
    item_comprado = info["estoque"].pop(0)
    salvar_estoque(dados_bins)

    # Registra no histórico do usuário
    adicionar_historico_usuario(user.id, item_comprado, bin_id, bandeira_nome)

    texto_sucesso = (
        "Compra Aprovada com Sucesso!\n\n"
        f"BIN: {bin_id} ({bandeira_nome})\n"
        "Dado entregue:\n"
        f"`{item_comprado}`\n\n"
        f"Novo Saldo: R$ {novo_saldo:.2f}\n\n"
        "💡 *Dica:* Se precisar ver este cartão novamente, acesse 'Meus Cartões / Histórico' no menu inicial!"
    )

    keyboard = [
        [InlineKeyboardButton("Comprar Mais", callback_data="ggs_disponiveis")],
        [InlineKeyboardButton("Menu Principal", callback_data="voltar_inicio")]
    ]

    await query.edit_message_text(text=texto_sucesso, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def pix_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args

    if not args:
        await update.message.reply_text("Por favor, informe o valor. Exemplo: /pix 10", parse_mode="Markdown")
        return

    try:
        valor = float(args[0].replace(',', '.'))
        if valor <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Valor inválido. Digite um número maior que zero. Ex: /pix 5", parse_mode="Markdown")
        return

    headers = {
        "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Idempotency-Key": str(uuid.uuid4())
    }

    payload = {
        "transaction_amount": valor,
        "description": f"Recarga Saldo Usuario {user.id}",
        "payment_method_id": "pix",
        "payer": {
            "email": f"user_{user.id}@telegram.com",
            "first_name": user.first_name or "Usuario",
            "last_name": user.last_name or "Telegram"
        }
    }

    try:
        data_bytes = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(PIX_API_URL, data=data_bytes, headers=headers, method='POST')

        with urllib.request.urlopen(req, timeout=15) as response:
            res_data = json.loads(response.read().decode('utf-8'))

            payment_id = str(res_data.get("id"))
            point_of_interaction = res_data.get("point_of_interaction", {})
            qr_data = point_of_interaction.get("transaction_data", {})
            qr_code = qr_data.get("qr_code")

            if not qr_code:
                await update.message.reply_text(f"API respondeu, mas sem o código Pix.")
                return

            PAGAMENTOS_PENDENTES[payment_id] = {"user_id": user.id, "valor": valor}
            registrar_log_pix(user.id, user.first_name, valor, payment_id, status="gerado")

            texto = (
                "💳 **Cobrança PIX Gerada com Sucesso!**\n\n"
                f"💰 **Valor:** R$ {valor:.2f}\n\n"
                "📲 **Copie o código abaixo e pague no seu banco:**\n\n"
                f"`{qr_code}`\n\n"
                "⏳ Após o pagamento, clique no botão abaixo para creditar seu saldo automaticamente."
            )

            keyboard = [
                [InlineKeyboardButton("Verificar Pagamento", callback_data=f"verificar_pix_{payment_id}")],
                [InlineKeyboardButton("Voltar", callback_data="voltar_inicio")]
            ]

            await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logging.error(f"Erro ao gerar Pix: {e}")
        await update.message.reply_text(f"Erro ao processar Pix: `{e}`", parse_mode="Markdown")

async def verificar_pix_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        payment_id = query.data.replace("verificar_pix_", "").strip()
        user = query.from_user

        headers = {"Authorization": f"Bearer {MP_ACCESS_TOKEN}"}
        req = urllib.request.Request(f"{PIX_API_URL}/{payment_id}", headers=headers, method='GET')

        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                res_data = json.loads(response.read().decode('utf-8'))
                status = res_data.get("status")

                if status == "approved":
                    valor = float(res_data.get("transaction_amount", 0.0))
                    saldo_atual = obter_saldo(user.id)
                    novo_saldo = saldo_atual + valor
                    atualizar_saldo(user.id, novo_saldo)
                    registrar_log_pix(user.id, user.first_name, valor, payment_id, status="aprovado")

                    texto = (
                        "Pagamento Confirmado!\n\n"
                        f"Valor creditado: R$ {valor:.2f}\n"
                        f"Seu novo saldo é: R$ {novo_saldo:.2f}\n\n"
                        "Agora você já pode realizar suas compras!"
                    )
                    keyboard = [[InlineKeyboardButton("GGs Disponíveis", callback_data="ggs_disponiveis")]]
                    await query.answer("Pagamento Aprovado!")
                    await query.edit_message_text(text=texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
                else:
                    await query.answer("Pagamento ainda não identificado. Aguarde alguns instantes e tente novamente.", show_alert=True)
            else:
                await query.answer("Não foi possível consultar o pagamento.", show_alert=True)
    except Exception as e:
        logging.error(f"Erro ao verificar PIX: {e}")
        await query.answer("Erro interno ao consultar pagamento.", show_alert=True)

async def recarregar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    texto = (
        "Como recarregar seu saldo:\n\n"
        "Envie o comando /pix seguido do valor que deseja recarregar no chat.\n\n"
        "Exemplos:\n"
        "- /pix 5 - Recarrega R$ 5,00\n"
        "- /pix 10 - Recarrega R$ 10,00\n\n"
        "O QR Code será gerado automaticamente!"
    )
    keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar_inicio")]]
    await query.edit_message_text(text=texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def voltar_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# ----------------------------------------------------
# Inicialização
# ----------------------------------------------------
async def main():
    t = Thread(target=iniciar_servidor_web)
    t.daemon = True
    t.start()

    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("pix", pix_command))

    application.add_handler(CallbackQueryHandler(voltar_inicio, pattern="^voltar_inicio$"))
    application.add_handler(CallbackQueryHandler(ggs_disponiveis, pattern="^ggs_disponiveis$"))
    application.add_handler(CallbackQueryHandler(historico_compras_callback, pattern="^historico_compras$"))
    application.add_handler(CallbackQueryHandler(selecionar_bin, pattern="^bin_"))
    application.add_handler(CallbackQueryHandler(efetuar_compra, pattern="^comprar_"))
    application.add_handler(CallbackQueryHandler(recarregar_callback, pattern="^recarregar$"))
    application.add_handler(CallbackQueryHandler(verificar_pix_callback, pattern="^verificar_pix_"))

    print("Iniciando bot...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    stop_event = asyncio.Event()
    await stop_event.wait()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
