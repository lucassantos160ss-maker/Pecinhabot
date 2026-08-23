import sys
import types
import logging
import os
import urllib.request
import urllib.parse
import uuid
import json
from datetime import datetime
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

# Importações do Telegram (Versão Moderna v20+)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ----------------------------------------------------
# Mini Servidor Web para atender aos requisitos do Render (Keep-Alive)
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
    servidor_serve = getattr(servidor, "serve_forever", None)
    if servidor_serve:
        servidor_serve()

# ----------------------------------------------------
# Gestão de Estoque e Saldo via JSON (Persistência Real)
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
        "374769": {"bandeira": "Amex", "estoque": ["374769002216776|10/30|0000|LIVE", "374769012120570|06/33|5457|LIVE"]},
        "406669": {"bandeira": "Visa", "estoque": ["4066699965118237|04/31|321|LIVE"]},
        "406655": {"bandeira": "Visa", "estoque": ["406655000000001|01/30|987|Nome Exemplo"]},
        "250061": {"bandeira": "Mastercard", "estoque": ["250061000000001|03/31|111|Nome Exemplo"]}
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
PIX_API_KEY = 'APP_USR-3303740326386787-081418-953681c933f125f4e5d8b34f8cf70ea8-3615204291'
PIX_API_URL = 'https://api.mercadopago.com/v1/payments'
URL_SUPORTE = 'https://t.me/Pecinhadosete'
URL_IMAGEM = "https://i.ibb.co/VcSYtKr2/pecinha-inicio.jpg"

PAGAMENTOS_PENDENTES = {}

def calcular_preco_e_bandeira(bin_id, bandeira_cadastrada=""):
    if "amex" in bandeira_cadastrada.lower() or bin_id.startswith("37"):
        return 10.0
    else:
        return 5.0

# ----------------------------------------------------
# Comandos Principais (Assíncronos - Padrão v20+)
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
        f"Ola {user.first_name}, seja muito bem-vindo!\n\n"
        "Atencao: Este e um bot que vende Geradas!\n"
        "Todos os nossos produtos estao com novos precos!\n\n"
        "Precisa de ajuda? Chame o Suporte\n"
        "Informacoes Rapidas:\n"
        "- GGs com nomes e CPFs aleatorios.\n"
        "- Logins diretos do painel.\n"
        "- Recargas instantaneas via /pix [valor] (Ex: /pix 10).\n"
        "- GGs Direto do Chk.\n"
        "- Leia as Regras antes de comprar.\n\n"
        "Seu perfil:\n"
        f" - ID: `{user.id}`\n"
        f" - Saldo: R$ {saldo:.2f}"
    )

    keyboard = [
        [InlineKeyboardButton("GGs Disponiveis", callback_data="ggs_disponiveis")],
        [InlineKeyboardButton("Recarregar", callback_data="recarregar"), InlineKeyboardButton("Suporte", url=URL_SUPORTE)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(
            text=texto,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            text=texto,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

# ----------------------------------------------------
# Menu Dinamico de GGs
# ----------------------------------------------------
async def ggs_disponiveis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    saldo = obter_saldo(user.id)
    dados_bins = carregar_estoque()

    texto = (
        "GGs Disponiveis (Preco de Atacado)\n"
        "Escolha a BIN desejada para ver detalhes e confirmar a compra.\n\n"
        "Seu perfil:\n"
        f" - ID: `{user.id}`\n"
        f" - Saldo: R$ {saldo:.2f}\n"
    )

    keyboard = []
    linha = []
    
    for bin_id, info in dados_bins.items():
        qtd = len(info.get("estoque", []))
        bandeira_nome = info.get('bandeira', 'Cartao')
        
        valor = calcular_preco_e_bandeira(bin_id, bandeira_nome)
        str_valor = f"{valor:.2f}".replace('.', ',')
        
        btn_txt = f"{bin_id} ({qtd}) | R$ {str_valor}"
        linha.append(InlineKeyboardButton(btn_txt, callback_data=f"bin_{bin_id}"))
        
        if len(linha) == 2:
            keyboard.append(linha)
            linha = []
            
    if linha:
        keyboard.append(linha)

    keyboard.append([InlineKeyboardButton("Pedir bin especifica", url=URL_SUPORTE)])
    keyboard.append([InlineKeyboardButton("Voltar", callback_data="voltar_inicio")])

    await query.edit_message_text(
        text=texto,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def selecionar_bin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    bin_id = query.data.split('_')[1]
    dados_bins = carregar_estoque()
    info = dados_bins.get(bin_id)

    if not info:
        await query.answer("BIN nao encontrada!", show_alert=True)
        return

    qtd_disponivel = len(info.get("estoque", []))
    bandeira_nome = info.get('bandeira', 'Desconhecida')
    preco = calcular_preco_e_bandeira(bin_id, bandeira_nome)

    texto = (
        f"Detalhes da BIN: {bin_id}\n"
        f"Bandeira: {bandeira_nome}\n"
        f"Preco unitario: R$ {preco:.2f}\n"
        f"Estoque disponivel: {qtd_disponivel} unidades\n\n"
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

    bandeira_nome = info.get('bandeira', 'Cartao')
    preco = calcular_preco_e_bandeira(bin_id, bandeira_nome)
    saldo_atual = obter_saldo(user.id)

    if saldo_atual < preco:
        await query.answer("Saldo insuficiente! Recarregue via PIX.", show_alert=True)
        return

    novo_saldo = saldo_atual - preco
    atualizar_saldo(user.id, novo_saldo)

    item_comprado = info["estoque"].pop(0)
    salvar_estoque(dados_bins)

    texto_sucesso = (
        "Compra Aprovada com Sucesso!\n\n"
        f"BIN: {bin_id} ({bandeira_nome})\n"
        "Dado entregue:\n"
        f"`{item_comprado}`\n\n"
        f"Novo Saldo: R$ {novo_saldo:.2f}"
    )

    keyboard = [
        [InlineKeyboardButton("Comprar Mais", callback_data="ggs_disponiveis")],
        [InlineKeyboardButton("Menu Principal", callback_data="voltar_inicio")]
    ]

    await query.edit_message_text(text=texto_sucesso, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# ----------------------------------------------------
# Sistema de Recarga PIX
# ----------------------------------------------------
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
        await update.message.reply_text("Valor invalido. Digite um numero maior que zero. Ex: /pix 5", parse_mode="Markdown")
        return

    headers = {
        "Authorization": f"Bearer {PIX_API_KEY}",
        "Content-Type": "application/json",
        "X-Idempotency-Key": str(uuid.uuid4())
    }

    payload = {
        "transaction_amount": valor,
        "description": f"Recarga de Saldo - Usuario {user.id}",
        "payment_method_id": "pix",
        "payer": {
            "email": f"user_{user.id}@bot.com",
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
                    f"Valor: R$ {valor:.2f}\n"
                    f"ID da Transacao: `{payment_id}`\n\n"
                    "Copie o codigo abaixo e pague no seu aplicativo de banco:\n\n"
                    f"`{qr_code}`\n\n"
                    "Apos pagar, clique no botao abaixo para aprovar seu saldo."
                )

                keyboard = [
                    [InlineKeyboardButton("Verificar Pagamento", callback_data=f"verificar_pix_{payment_id}")],
                    [InlineKeyboardButton("Voltar", callback_data="voltar_inicio")]
                ]

                await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await update.message.reply_text("Ocorreu um erro ao gerar a cobranca PIX no Mercado Pago.")
    except Exception as e:
        logging.error(f"Erro no comando /pix: {e}")
        await update.message.reply_text("Erro de conexao com o servidor de pagamento.")

async def verificar_pix_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    try:
        payment_id = query.data.replace("verificar_pix_", "").strip()
        user = query.from_user

        headers = {"Authorization": f"Bearer {PIX_API_KEY}"}
        req = urllib.request.Request(f"{PIX_API_URL}/{payment_id}", headers=headers, method='GET')

        with urllib.request.urlopen(req) as response:
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
                        f"Seu novo saldo e: R$ {novo_saldo:.2f}\n\n"
                        "Agora voce ja pode realizar suas compras!"
                    )
                    keyboard = [[InlineKeyboardButton("GGs Disponiveis", callback_data="ggs_disponiveis")]]
                    
                    await query.answer("Pagamento Aprovado!")
                    await query.edit_message_text(text=texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
                else:
                    await query.answer(
                        f"Pagamento ainda nao identificado (Status: {status}). Aguarde alguns instantes e tente novamente.", 
                        show_alert=True
                    )
            else:
                await query.answer("Nao foi possivel consultar o pagamento. Tente novamente.", show_alert=True)

    except Exception as e:
        logging.error(f"Erro ao verificar PIX: {e}")
        await query.answer("Ocorreu um erro interno na consulta. Tente novamente.", show_alert=True)

async def recarregar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    texto = (
        "Como recarregar seu saldo:\n\n"
        "Envie o comando /pix seguido do valor que deseja recarregar diretamente no chat.\n\n"
        "Exemplos:\n"
        "- /pix 5 - Recarrega R$ 5,00\n"
        "- /pix 10 - Recarrega R$ 10,00\n"
        "- /pix 50 - Recarrega R$ 50,00\n\n"
        "O QR Code e o Copia e Cola serao gerados automaticamente!"
    )
    keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar_inicio")]]
    await query.edit_message_text(text=texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def voltar_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# ----------------------------------------------------
# Comandos Admin
# ----------------------------------------------------
ADMINS = [7970384949, 7622528057]

async def admpix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        await update.message.reply_text("Voce nao tem permissao para usar este comando.")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Uso correto: /admpix <ID_DO_USUARIO> <VALOR>\n\nExemplo: /admpix 123456789 50",
            parse_mode="Markdown"
        )
        return

    try:
        target_id = int(args[0])
        valor = float(args[1].replace(',', '.'))

        if valor <= 0:
            await update.message.reply_text("O valor deve ser maior que zero.")
            return

        saldo_atual = obter_saldo(target_id)
        novo_saldo = saldo_atual + valor
        atualizar_saldo(target_id, novo_saldo)

        await update.message.reply_text(
            "Saldo Adicionado com Sucesso!\n\n"
            f"Usuario Receptante (ID): `{target_id}`\n"
            f"Valor Adicionado: R$ {valor:.2f}\n"
            f"Novo Saldo do Usuario: R$ {novo_saldo:.2f}",
            parse_mode="Markdown"
        )

        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"Voce recebeu uma recarga de saldo!\n\nValor: R$ {valor:.2f}\nSeu Novo Saldo: R$ {novo_saldo:.2f}",
                parse_mode="Markdown"
            )
        except Exception:
            pass

    except ValueError:
        await update.message.reply_text("Formato invalido! Certifique-se de que o ID e um numero e o valor e numerico.", parse_mode="Markdown")

async def addestoque(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        await update.message.reply_text("Voce nao tem permissao para usar este comando.")
        return

    texto_completo = update.message.text[len("/addestoque"):].strip()
    if not texto_completo:
        await update.message.reply_text(
            "Uso correto:\n`/addestoque <BIN> <Bandeira>\nitem1\nitem2`",
            parse_mode="Markdown"
        )
        return

    linhas = texto_completo.split('\n')
    primeira_linha = linhas[0].strip().split(' ', 1)
    bin_id = primeira_linha[0].strip()
    bandeira_informada = primeira_linha[1].strip() if len(primeira_linha) > 1 else "Cartao"

    itens_novos = [l.strip() for l in linhas[1:] if l.strip()]
    dados_bins = carregar_estoque()

    if bin_id not in dados_bins:
        dados_bins[bin_id] = {"bandeira": bandeira_informada, "estoque": []}
    else:
        dados_bins[bin_id]["bandeira"] = bandeira_informada

    dados_bins[bin_id]["estoque"].extend(itens_novos)
    salvar_estoque(dados_bins)

    qtd_total = len(dados_bins[bin_id]["estoque"])
    await update.message.reply_text(
        "Estoque Atualizado com Sucesso!\n\n"
        f"BIN: `{bin_id}`\n"
        f"Bandeira: {bandeira_informada}\n"
        f"Itens adicionados: {len(itens_novos)}\n"
        f"Total agora nesta BIN: {qtd_total} unidades",
        parse_mode="Markdown"
    )

async def verestoque(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        return

    dados_bins = carregar_estoque()
    texto = "Resumo do Estoque Atual:\n\n"
    for bin_id, info in dados_bins.items():
        qtd = len(info.get("estoque", []))
        texto += f"- BIN `{bin_id}` ({info.get('bandeira')}): {qtd} unidades\n"

    await update.message.reply_text(texto, parse_mode="Markdown")

# ----------------------------------------------------
# Main (Inicialização Padrão v20+ com ApplicationBuilder)
# ----------------------------------------------------
if __name__ == '__main__':
    # Inicia o servidor web do Render em segundo plano
    t = Thread(target=iniciar_servidor_web)
    t.daemon = True
    t.start()

    # Configura a aplicação moderna
    application = ApplicationBuilder().token(TOKEN).build()

    # Adicionando os manipuladores de comandos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("pix", pix_command))
    application.add_handler(CommandHandler("admpix", admpix))
    application.add_handler(CommandHandler("addestoque", addestoque))
    application.add_handler(CommandHandler("verestoque", verestoque))

    # Adicionando os manipuladores de botões (Callbacks)
    application.add_handler(CallbackQueryHandler(voltar_inicio, pattern="^voltar_inicio$"))
    application.add_handler(CallbackQueryHandler(ggs_disponiveis, pattern="^ggs_disponiveis$"))
    application.add_handler(CallbackQueryHandler(selecionar_bin, pattern="^bin_"))
    application.add_handler(CallbackQueryHandler(efetuar_compra, pattern="^comprar_"))
    application.add_handler(CallbackQueryHandler(recarregar_callback, pattern="^recarregar$"))
    application.add_handler(CallbackQueryHandler(verificar_pix_callback, pattern="^verificar_pix_"))

    print("Bot moderno iniciado com sucesso via polling...")
    application.run_polling()
