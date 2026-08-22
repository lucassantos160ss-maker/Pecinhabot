def addestoque(update, text_args=""):
    user_id = update.effective_user.id

    if user_id not in ADMINS:
        update.message.reply_text("Voce nao tem permissao para usar este comando.")
        return

    partes = text_args.split('\n', 1)
    if len(partes) < 2:
        update.message.reply_text(
            "Uso correto:\n`/addestoque <BIN>\nitem1\nitem2\nitem3`\n\n"
            "Exemplo:\n`/addestoque 406669\n4066699982452023|01/2034|159\n4066699982457162|01/2034|385`",
            parse_mode="Markdown"
        )
        return

    cabecalho = partes[0].strip().split()
    if not cabecalho:
        update.message.reply_text("Voce precisa informar a BIN logo apos o comando.")
        return

    bin_id = cabecalho[0].strip()
    linhas_texto = partes[1].split('\n')

    dados_bins = carregar_estoque()

    if bin_id not in dados_bins:
        dados_bins[bin_id] = {"bandeira": "Cartao", "valor": 1.0, "estoque": []}

    adicionados = 0
    for linha in linhas_texto:
        item = linha.strip()
        if item:  # Ignora linhas em branco
            dados_bins[bin_id]["estoque"].append(item)
            adicionados += 1

    salvar_estoque(dados_bins)

    qtd_total = len(dados_bins[bin_id]["estoque"])
    update.message.reply_text(
        "Estoque Atualizado com Sucesso!\n\n"
        "BIN: `{}`\n"
        "Itens adicionados em lote: {}\n\n"
        "Total agora nesta BIN: {} unidades".format(bin_id, adicionados, qtd_total),
        parse_Mode="Markdown"
    )
