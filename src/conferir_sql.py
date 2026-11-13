"""
conferir_sql.py  -  roda sql/02_perguntas.sql no banco e imprime o resultado de cada consulta
=============================================================================================
Serve para conferir os numeros contra a prova real (anexo 8) sem abrir o pgAdmin. As consultas continuam sendo
as do arquivo sql/02_perguntas.sql (a resposta oficial); este script so as executa e mostra.

COMO RODAR (depois da carga):   python -m src.conferir_sql
"""

import re

import pandas as pd

from src import banco, config


def main():
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 30)
    pd.set_option("display.float_format", lambda v: f"{v:,.2f}")
    con = banco.conectar()
    texto = (config.PASTA_SQL / "02_perguntas.sql").read_text(encoding="utf-8")
    # cada bloco comeca em um comentario "-- P<numero>"; o que vem depois e a consulta (ate o proximo ';')
    comandos = banco._separar_comandos(texto)
    titulos = [linha.strip("- ").strip() for linha in texto.splitlines() if re.match(r"-- P\d+", linha)]
    for titulo, comando in zip(titulos, comandos):
        print(f"\n=== {titulo[:110]}")
        cursor = con.cursor()
        cursor.execute(comando)
        colunas = [c[0] for c in cursor.description]
        print(pd.DataFrame(cursor.fetchall(), columns=colunas).to_string(index=False))
        cursor.close()
    con.close()


if __name__ == "__main__":
    main()
