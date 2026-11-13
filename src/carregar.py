"""
carregar.py - carrega as tabelas limpas no PostgreSQL.
Passos: 1) recria o banco e as tabelas  2) carrega as dimensoes  3) carrega a fato  4) confere as contagens
Rodar (depois do montar_tabelas): python -m src.carregar
"""

import pandas as pd

from src import banco, config


def ler(nome, **opcoes):
    """Le um CSV de data/processed. Campo vazio vira NaN (depois vira NULL no banco)."""
    return pd.read_csv(config.PASTA_PROCESSED / f"{nome}.csv", keep_default_na=False, na_values=[""], **opcoes)


def tuplas(tabela, colunas):
    """Transforma o DataFrame em lista de tuplas. Valor vazio vira None (NULL no banco)."""
    dados = tabela[colunas].astype(object)
    dados = dados.where(dados.notna(), None)
    return [tuple(linha) for linha in dados.itertuples(index=False, name=None)]


def inserir(con, tabela, colunas, dados):
    """Monta o INSERT e envia todas as linhas de uma vez (em lote)."""
    marcadores = ", ".join(["%s"] * len(colunas))
    sql = f"INSERT INTO {tabela} ({', '.join(colunas)}) VALUES ({marcadores})"
    banco.inserir_em_lote(con, sql, tuplas(dados, colunas))
    print(f"   {tabela}: {len(dados)} linhas")


def main():
    # 1) apaga e cria o banco de novo, depois cria as tabelas
    banco.recriar_banco()
    con = banco.conectar()
    banco.executar_script(con, config.PASTA_SQL / "01_criar_banco.sql")

    try:
        # 2) dimensoes primeiro, porque a fato tem chave estrangeira para elas
        print("Carga:")
        for nome, colunas in [("dim_orgao", ["sk_orgao", "cnpj_orgao", "nome_orgao", "poder"]),
                              ("dim_fornecedor", ["sk_fornecedor", "ni_fornecedor", "nome_fornecedor", "tipo_pessoa", "porte"]),
                              ("dim_modalidade", ["sk_modalidade", "modalidade_id", "nome_modalidade"]),
                              ("dim_localidade", ["sk_localidade", "uf_sigla", "uf_nome", "regiao"])]:
            # dtype=str para o CNPJ nao perder o zero da esquerda
            inserir(con, nome, colunas, ler(nome, dtype=str))

        # 3) fato
        fato = ler("fato_item_contratado")
        # dias_ciclo vem como 48.0 por causa dos vazios; "Int64" volta para inteiro
        fato["dias_ciclo"] = fato["dias_ciclo"].astype("Int64")
        colunas = ["numero_controle_pncp", "numero_item", "sk_orgao", "sk_fornecedor", "sk_modalidade", "sk_localidade",
                   "data_publicacao", "data_homologacao", "descricao_item", "perfil_gasto", "quantidade",
                   "valor_unitario_estimado", "valor_total_estimado", "valor_unitario_homologado",
                   "valor_total_homologado", "comparavel", "economia_valor", "dias_ciclo"]
        inserir(con, "fato_item_contratado", colunas, fato)
    except Exception:
        # se der erro (FK, CHECK, UNIQUE...), desfaz a transacao e avisa
        con.rollback()
        con.close()
        print("ERRO na carga: transacao desfeita. Corrija o erro abaixo e rode de novo.")
        raise

    # 4) conferencia com a prova real (anexo 8)
    print("Conferencia (linhas por tabela):")
    ok = True
    for tabela, esperado in [("fato_item_contratado", 6126), ("dim_orgao", 363), ("dim_fornecedor", 2652),
                             ("dim_modalidade", 7), ("dim_localidade", 27)]:
        n = banco.consultar(con, f"SELECT COUNT(*) FROM {tabela}")[0][0]
        ok &= n == esperado
        print(f"   {tabela}: {n} (esperado {esperado}) -> {'OK' if n == esperado else 'DIVERGENTE'}")

    # FK solta = linha da fato sem linha correspondente na dimensao
    print("Conferencia (FK solta, tem que ser 0):")
    for dim, sk in [("dim_orgao", "sk_orgao"), ("dim_fornecedor", "sk_fornecedor"),
                    ("dim_modalidade", "sk_modalidade"), ("dim_localidade", "sk_localidade")]:
        n = banco.consultar(con, f"SELECT COUNT(*) FROM fato_item_contratado f LEFT JOIN {dim} d USING ({sk}) "
                                 f"WHERE d.{sk} IS NULL")[0][0]
        ok &= n == 0
        print(f"   fato x {dim}: {n} -> {'OK' if n == 0 else 'DIVERGENTE'}")
    con.close()
    print("Carga concluida e conferida." if ok else "ATENCAO: ha divergencias, confira acima.")


if __name__ == "__main__":
    main()
