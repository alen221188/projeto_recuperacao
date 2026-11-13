"""
montar_tabelas.py - monta a fato e as 4 dimensoes a partir dos CSVs brutos.
Usa as funcoes do limpeza.py e aplica as regras de negocio do enunciado (secao 4.2).
Rodar: python -m src.montar_tabelas  (grava os CSVs em data/processed/ e imprime a conferencia)
"""

import pandas as pd

from src import config, limpeza

# Tabelas de apoio (anexo do enunciado)
MODALIDADES = {4: "Concorrência - Eletrônica", 5: "Concorrência - Presencial", 6: "Pregão - Eletrônico",
               7: "Pregão - Presencial", 8: "Dispensa", 9: "Inexigibilidade", 12: "Credenciamento"}
REGIAO = {"AC": "Norte", "AM": "Norte", "AP": "Norte", "PA": "Norte", "RO": "Norte", "RR": "Norte", "TO": "Norte",
          "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste", "MA": "Nordeste", "PB": "Nordeste", "PE": "Nordeste",
          "PI": "Nordeste", "RN": "Nordeste", "SE": "Nordeste", "DF": "Centro-Oeste", "GO": "Centro-Oeste",
          "MS": "Centro-Oeste", "MT": "Centro-Oeste", "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
          "PR": "Sul", "RS": "Sul", "SC": "Sul"}
PODER = {"E": "Executivo", "L": "Legislativo", "J": "Judiciário", "N": "Não informado"}
PORTES_VALIDOS = {"ME": "ME", "EPP": "EPP", "DEMAIS": "Demais"}


def ler(nome):
    """Le o CSV tudo como texto, para o CNPJ nao perder o zero da esquerda."""
    return pd.read_csv(config.PASTA_RAW / f"{nome}.csv", dtype=str, keep_default_na=False)


def padronizar_porte(texto):
    """O porte vira ME, EPP, Demais ou Não informado.
    Nulo disfarcado (N/A, NULL, -, 'Não Informado'...) ja volta None do limpar_texto."""
    limpo = limpeza.limpar_texto(texto)
    if limpo is None:
        return "Não informado"
    return PORTES_VALIDOS.get(limpo.upper(), "Não informado")


def data_valida(d):
    return d is not None and not pd.isna(d)


def main():
    compras, itens, resultados = ler("compras"), ler("itens"), ler("resultados")
    print(f"Linhas lidas: compras={len(compras)} itens={len(itens)} resultados={len(resultados)}  (esperado: 2042 / 7077 / 15896)")

    # ---------------------------------------------------------------------------------
    # Etapa 1 - limpar os 3 arquivos
    # ---------------------------------------------------------------------------------
    # compras
    compras["cnpj_orgao"] = compras["cnpj_orgao"].map(lambda v: limpeza.limpar_documento(v, "PJ"))
    compras["nome_orgao"] = compras["razao_social_orgao"].map(limpeza.padronizar_nome)
    compras["uf_sigla"] = compras["uf_sigla"].map(limpeza.padronizar_nome)
    compras["uf_nome"] = compras["uf_nome"].map(limpeza.padronizar_nome)
    compras["regiao"] = compras["uf_sigla"].map(REGIAO)          # a regiao nao vem no arquivo
    compras["poder"] = compras["poder_id"].map(PODER).fillna("Não informado")
    compras["modalidade_id"] = compras["modalidade_id"].astype(int)
    compras["nome_modalidade"] = compras["modalidade_id"].map(MODALIDADES)   # nome vem do id
    compras["data_publicacao"] = compras["data_publicacao"].map(limpeza.converter_data)
    compras["objeto_compra"] = compras["objeto_compra"].map(limpeza.limpar_texto)

    # itens
    itens["descricao_item"] = itens["descricao"].map(limpeza.padronizar_nome)
    itens["material_ou_servico"] = itens["material_ou_servico"].map(limpeza.limpar_texto)
    for coluna in ["quantidade", "valor_unitario_estimado"]:
        itens[coluna] = itens[coluna].map(limpeza.converter_numero)
    itens["sigiloso"] = itens["sigiloso"].str.lower() == "true"
    itens["numero_item"] = itens["numero_item"].astype(int)

    # resultados
    resultados["numero_item"] = resultados["numero_item"].astype(int)
    resultados["nome_fornecedor"] = resultados["nome_fornecedor"].map(limpeza.padronizar_nome)
    resultados["porte"] = resultados["porte"].map(padronizar_porte)
    resultados["tipo_pessoa"] = resultados["tipo_pessoa"].map(limpeza.limpar_texto)
    # o documento depende do tipo da pessoa (PJ, PF ou PE)
    resultados["ni_fornecedor"] = [limpeza.limpar_documento(ni, tipo)
                                   for ni, tipo in zip(resultados["ni_fornecedor"], resultados["tipo_pessoa"])]
    for coluna in ["quantidade_homologada", "valor_unitario_homologado"]:
        resultados[coluna] = resultados[coluna].map(limpeza.converter_numero)
    resultados["data_resultado"] = resultados["data_resultado"].map(limpeza.converter_data)
    resultados["cancelado"] = resultados["data_cancelamento"].str.strip() != ""

    # ---------------------------------------------------------------------------------
    # Etapa 2 - um vencedor por item (regra 2)
    # ---------------------------------------------------------------------------------
    # primeiro tira os cancelados, depois fica com o 1o colocado
    resultados = resultados[~resultados["cancelado"]].copy()
    resultados["ordem"] = pd.to_numeric(resultados["ordem_classificacao_srp"], errors="coerce").fillna(1)
    resultados["sequencial"] = pd.to_numeric(resultados["sequencial_resultado"], errors="coerce").fillna(1)
    # o sequencial vira numero para o 2 vir antes do 10 (desempate)
    resultados = resultados.sort_values(["numero_controle_pncp", "numero_item", "ordem", "sequencial"])
    resultados = resultados.drop_duplicates(["numero_controle_pncp", "numero_item"])

    # ---------------------------------------------------------------------------------
    # Etapa 3 - juntar os arquivos; so entram itens com resultado (regra 3)
    # ---------------------------------------------------------------------------------
    # escolho as colunas antes do merge porque compras e itens tem valor_total proprio, que nao usamos
    compras_f = compras[["numero_controle_pncp", "objeto_compra", "cnpj_orgao", "nome_orgao", "poder", "uf_sigla",
                         "uf_nome", "regiao", "modalidade_id", "nome_modalidade", "data_publicacao"]]
    itens_f = itens[["numero_controle_pncp", "numero_item", "descricao_item", "material_ou_servico", "quantidade",
                     "valor_unitario_estimado", "sigiloso"]]
    resultados_f = resultados[["numero_controle_pncp", "numero_item", "ni_fornecedor", "tipo_pessoa", "nome_fornecedor",
                               "porte", "quantidade_homologada", "valor_unitario_homologado", "data_resultado"]]
    fato = itens_f.merge(resultados_f, on=["numero_controle_pncp", "numero_item"], how="inner")
    fato = fato.merge(compras_f, on="numero_controle_pncp", how="left")
    print(f"Itens sem resultado: {len(itens_f) - len(fato)}  (esperado: 852)")

    # ---------------------------------------------------------------------------------
    # Etapa 4 - valores (regra 5)
    # ---------------------------------------------------------------------------------
    # usa a quantidade homologada; se vier vazia ou zero, usa a do item
    qtd_homologada = fato["quantidade_homologada"]
    fato["quantidade"] = qtd_homologada.where(qtd_homologada > 0, fato["quantidade"])
    fato["valor_total_estimado"] = (fato["valor_unitario_estimado"] * fato["quantidade"]).round(2)
    fato["valor_total_homologado"] = (fato["valor_unitario_homologado"] * fato["quantidade"]).round(2)

    # ---------------------------------------------------------------------------------
    # Etapa 5 - itens rejeitados (regra 4)
    # ---------------------------------------------------------------------------------
    est, hom = fato["valor_total_estimado"], fato["valor_total_homologado"]
    # ~(x > 0) pega valor <= 0 e tambem valor vazio
    motivos = [
        ("quantidade vazia ou <= 0", ~(fato["quantidade"] > 0)),
        ("valor unitario estimado ausente ou <= 0", ~(fato["valor_unitario_estimado"] > 0)),
        ("valor unitario homologado ausente ou <= 0", ~(fato["valor_unitario_homologado"] > 0)),
        ("orcamento sigiloso", fato["sigiloso"]),
        ("valor total estimado < R$ 1", ~(est >= 1)),
        ("homologado > 1000x o estimado", hom > 1000 * est),
        ("valor total acima de R$ 1 trilhao", (est > 1e12) | (hom > 1e12)),
    ]
    fato["motivo_rejeicao"] = None
    for texto_motivo, condicao in motivos:
        # guarda so o primeiro motivo de cada item
        fato.loc[condicao & fato["motivo_rejeicao"].isna(), "motivo_rejeicao"] = texto_motivo
    rejeitado = fato["motivo_rejeicao"].notna()
    print(f"Itens rejeitados: {rejeitado.sum()}  (esperado: 99)")
    print(fato.loc[rejeitado, "motivo_rejeicao"].value_counts().to_string())
    fato = fato[~rejeitado].copy()

    # ---------------------------------------------------------------------------------
    # Etapa 6 - comparavel e economia (regra 6)
    # ---------------------------------------------------------------------------------
    est, hom = fato["valor_total_estimado"], fato["valor_total_homologado"]
    razao = hom / est
    # comparavel: nao e Credenciamento (id 12) e a razao homologado/estimado fica entre 0,1 e 10
    fato["comparavel"] = ((fato["modalidade_id"] != 12) & razao.between(0.1, 10)).astype(int)
    # economia so nos comparaveis; nos outros fica vazia (NULL)
    fato["economia_valor"] = (est - hom).where(fato["comparavel"] == 1, None).round(2)

    # ---------------------------------------------------------------------------------
    # Etapa 7 - cronologia (regra 7)
    # ---------------------------------------------------------------------------------
    fato["data_homologacao"] = fato["data_resultado"]
    # homologar antes de publicar e impossivel: a data fica vazia (o item continua na fato)
    antes = pd.Series([data_valida(h) and data_valida(p) and h < p
                       for h, p in zip(fato["data_homologacao"], fato["data_publicacao"])], index=fato.index)
    fato.loc[antes, "data_homologacao"] = None
    # ciclo = dias entre publicacao e homologacao
    fato["dias_ciclo"] = [(h - p).days if data_valida(h) and data_valida(p) else None
                          for h, p in zip(fato["data_homologacao"], fato["data_publicacao"])]

    # ---------------------------------------------------------------------------------
    # Etapa 8 - perfil do gasto (regra 8)
    # ---------------------------------------------------------------------------------
    # palavras de obra: obra, construcao, reforma, engenharia (\b = palavra inteira,
    # senao "cobranca" e "dobradica" virariam obra). Procura na descricao e no objeto da compra.
    texto = fato["descricao_item"].fillna("") + " " + fato["objeto_compra"].fillna("").str.upper()
    eh_obra = texto.str.contains(r"\b(?:OBRAS?|CONSTRUÇÃO|CONSTRUCAO|REFORMA|ENGENHARIA)\b", regex=True)
    fato["perfil_gasto"] = "Bens"
    fato.loc[fato["material_ou_servico"].fillna("").str.upper().str.startswith("SERVI"), "perfil_gasto"] = "Serviços"
    fato.loc[eh_obra, "perfil_gasto"] = "Obras e engenharia"    # obra tem prioridade

    # ---------------------------------------------------------------------------------
    # Etapa 9 - dimensoes com chave substituta (sk_)
    # ---------------------------------------------------------------------------------
    # uma linha por valor da chave natural; o sk numera as linhas (1, 2, 3...)
    dim_orgao = fato.drop_duplicates("cnpj_orgao")[["cnpj_orgao", "nome_orgao", "poder"]].reset_index(drop=True)
    dim_orgao.insert(0, "sk_orgao", dim_orgao.index + 1)

    dim_fornecedor = fato.drop_duplicates("ni_fornecedor")[["ni_fornecedor", "nome_fornecedor", "tipo_pessoa",
                                                          "porte"]].reset_index(drop=True)
    dim_fornecedor.insert(0, "sk_fornecedor", dim_fornecedor.index + 1)

    dim_modalidade = fato.drop_duplicates("modalidade_id")[["modalidade_id", "nome_modalidade"]].reset_index(drop=True)
    dim_modalidade.insert(0, "sk_modalidade", dim_modalidade.index + 1)

    dim_localidade = fato.drop_duplicates("uf_sigla")[["uf_sigla", "uf_nome", "regiao"]].reset_index(drop=True)
    dim_localidade.insert(0, "sk_localidade", dim_localidade.index + 1)

    # troca a chave natural pela chave substituta na fato
    for dim, chave, sk in [(dim_orgao, "cnpj_orgao", "sk_orgao"), (dim_fornecedor, "ni_fornecedor", "sk_fornecedor"),
                           (dim_modalidade, "modalidade_id", "sk_modalidade"), (dim_localidade, "uf_sigla", "sk_localidade")]:
        fato[sk] = fato[chave].map(dict(zip(dim[chave], dim[sk])))
        # se sobrar vazio, tem FK solta e seria preciso criar a linha "Não informado" (sk = -1)
        assert fato[sk].notna().all(), f"FK solta em {sk}"

    colunas = ["numero_controle_pncp", "numero_item", "sk_orgao", "sk_fornecedor", "sk_modalidade", "sk_localidade",
               "data_publicacao", "data_homologacao", "descricao_item", "perfil_gasto", "quantidade",
               "valor_unitario_estimado", "valor_total_estimado", "valor_unitario_homologado", "valor_total_homologado",
               "comparavel", "economia_valor", "dias_ciclo"]
    fato = fato[colunas]

    # ---------------------------------------------------------------------------------
    # Etapa 10 - salvar e conferir com a prova real
    # ---------------------------------------------------------------------------------
    config.PASTA_PROCESSED.mkdir(parents=True, exist_ok=True)
    for nome, tabela in [("fato_item_contratado", fato), ("dim_orgao", dim_orgao), ("dim_fornecedor", dim_fornecedor),
                         ("dim_modalidade", dim_modalidade), ("dim_localidade", dim_localidade)]:
        tabela.to_csv(config.PASTA_PROCESSED / f"{nome}.csv", index=False, encoding="utf-8")

    comp = fato["comparavel"] == 1
    est_comp = fato.loc[comp, "valor_total_estimado"].sum()
    vol = fato["valor_total_homologado"]
    sobre = comp & (fato["valor_total_homologado"] > fato["valor_total_estimado"])
    print("\n=== Conferencia (valor esperado entre parenteses) ===")
    print(f"itens na fato ........ {len(fato)}  (6126)")
    print(f"contratacoes ......... {fato['numero_controle_pncp'].nunique()}  (1962)")
    print(f"fornecedores ......... {len(dim_fornecedor)}  (2652)")
    print(f"orgaos (CNPJ) ........ {len(dim_orgao)}  (363)")
    print(f"volume homologado .... R$ {vol.sum():,.2f}  (8.044.498.805,74)")
    print(f"estimado total ....... R$ {fato['valor_total_estimado'].sum():,.2f}  (32.629.639.732,13)")
    print(f"estimado comparavel .. R$ {est_comp:,.2f}  (6.867.663.469,91)")
    print(f"itens comparaveis .... {comp.sum()}  (5457)")
    print(f"economia ............. R$ {fato['economia_valor'].sum():,.2f}  (992.861.686,95)")
    print(f"economia % ........... {100 * fato['economia_valor'].sum() / est_comp:.2f}%  (14,46%)")
    print(f"ciclo medio / maximo . {fato['dias_ciclo'].mean():.1f} / {fato['dias_ciclo'].max():.0f} dias  (48,1 / 611)")
    print(f"itens sem ciclo ...... {fato['dias_ciclo'].isna().sum()}  (230)")
    print("perfil (% volume) .... ", (100 * fato.groupby("perfil_gasto")["valor_total_homologado"].sum() / vol.sum()).round(1).to_dict(),
          " (Obras 60,8 | Serviços 36,6 | Bens 2,6)")
    print(f"itens com sobrepreco . {sobre.sum()}  (27)")
    print(f"valor do sobrepreco .. R$ {(fato.loc[sobre, 'valor_total_homologado'] - fato.loc[sobre, 'valor_total_estimado']).sum():,.2f}  (44.440,34)")


if __name__ == "__main__":
    main()
