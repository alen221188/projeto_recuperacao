"""
limpeza.py - funcoes que limpam os dados brutos (CNPJ com mascara, "R$ 1.234,56", datas em varios formatos...).
Para testar: python -m src.limpeza
"""

from datetime import datetime

# Textos que significam "sem valor" (comparados em maiusculas)
NULOS = {"N/A", "NULL", "NONE", "NAN", "-", "0", "SEM INFORMAÇÃO", "SEM INFORMACAO",
         "NÃO INFORMADO", "NAO INFORMADO", "NÃO SE APLICA", "NAO SE APLICA"}

# Formatos de data que aparecem nos arquivos
FORMATOS_DATA = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d", "%Y%m%d"]


# 1) TEXTO  (nulos disfarcados, espacos, acento quebrado)
def remover_invisiveis(texto):
    """Apaga caracteres invisiveis (largura zero) que vem de sistemas antigos."""
    for c in ["​", "‌", "‍", "﻿"]:
        texto = texto.replace(c, "")
    return texto


def consertar_acento(texto):
    """Corrige acento quebrado: 'AquisiÃ§Ã£o' vira 'Aquisição'.
    Se o texto ja esta certo, o try da erro e devolvemos o texto sem mexer."""
    try:
        return texto.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return texto


def tirar_espacos(texto):
    """Tira espacos das pontas e espacos repetidos.   '  Ana   Maria ' -> 'Ana Maria'  (  e o espaco 'sem quebra')."""
    return " ".join(texto.split())


def eh_nulo(texto, zero_eh_nulo=True):
    """True se o texto e um nulo disfarcado (vazio, N/A, NULL, -...).
    O "0" so e nulo em campo de texto. Em campo de numero o 0 vale (zero_eh_nulo=False)."""
    chave = texto.upper()
    if chave == "":
        return True
    if chave == "0":
        return zero_eh_nulo
    return chave in NULOS


def limpar_texto(texto, zero_eh_nulo=True):
    """Limpa o texto e devolve None se for nulo disfarcado."""
    if texto is None:
        return None
    texto = remover_invisiveis(texto)
    texto = consertar_acento(texto.strip(" "))
    texto = tirar_espacos(texto)
    if eh_nulo(texto, zero_eh_nulo):
        return None
    return texto


def padronizar_nome(texto):
    """Deixa o nome em MAIUSCULAS para o mesmo nome escrito de jeitos diferentes ficar igual.
    O hifen ganha espaco dos dois lados: 'Pregão-Eletrônico' vira 'PREGÃO - ELETRÔNICO'."""
    texto = limpar_texto(texto)
    if texto is None:
        return None
    texto = texto.upper()
    texto = texto.replace("-", " - ")
    return tirar_espacos(texto)


# 2) DOCUMENTOS  (CNPJ = 14 digitos, CPF = 11)
def limpar_documento(texto, tipo_pessoa=None):
    """Deixa so os digitos do CNPJ/CPF e devolve os zeros da esquerda.
    '11.222.333/0001-81' (PJ) vira '11222333000181'; '1222333000181' (PJ) vira '01222333000181'.
    Estrangeiro (PE) fica como esta. Lixo ('N/A', '-') ou digitos demais devolve None.
    tipo_pessoa: 'PJ' (14 digitos), 'PF' (11 digitos), 'PE' ou None."""
    texto = limpar_texto(texto)
    if texto is None:
        return None
    if tipo_pessoa == "PE":
        return texto.upper()
    digitos = "".join(c for c in texto if c.isdigit())
    if digitos == "":
        return None
    if tipo_pessoa == "PJ":
        tamanho = 14
    elif tipo_pessoa == "PF":
        tamanho = 11
    else:                                    # sem o tipo: mais de 11 digitos e CNPJ, senao CPF
        tamanho = 14 if len(digitos) > 11 else 11
    if len(digitos) > tamanho:               # digitos demais: documento impossivel
        return None
    return digitos.zfill(tamanho)


# 3) DINHEIRO E NUMEROS EM TEXTO
def converter_numero(texto):
    """Converte texto em numero: 'R$ 1.234,56' vira 1234.56 e '(1.500,00)' vira -1500.0.
    Regra desta base: ponto ou virgula sozinho e decimal ('746.815' vira 746.815).
    So o simbolo repetido e milhar ('1.234.567'). Se aparecem os dois, o ultimo e o decimal.
    Devolve None se nao der para converter. O zero e um numero valido."""
    texto = limpar_texto(texto, zero_eh_nulo=False)     # False: aqui o 0 e valor, nao nulo
    if texto is None:
        return None
    texto = texto.replace("R$", "").replace(" ", "")
    negativo = texto.startswith(("(", "-")) or texto.endswith("-")
    texto = texto.strip("()-")
    if "." in texto and "," in texto:
        if texto.rfind(",") > texto.rfind("."):
            # formato 1.234,56 (a virgula vem por ultimo)
            texto = texto.replace(".", "").replace(",", ".")
        else:
            # formato 1,234.56 (o ponto vem por ultimo)
            texto = texto.replace(",", "")
    elif "," in texto:
        if texto.count(",") > 1:
            # 1,234,567 (virgula repetida = milhar)
            texto = texto.replace(",", "")
        else:
            # 12,5 (virgula sozinha = decimal)
            texto = texto.replace(",", ".")
    elif texto.count(".") > 1:
        # 1.234.567 (ponto repetido = milhar)
        texto = texto.replace(".", "")
    # (ponto sozinho, como em 1234.56 ou 746.815, ja e decimal: nao precisa mexer)
    try:
        numero = float(texto)
    except ValueError:
        return None
    return -numero if negativo else numero


# 4) DATAS  (varios formatos no mesmo campo)
def converter_data(texto):
    """Converte texto em data (sem hora): '10/03/2025 14:20' e '2025-03-10T08:30:00' viram 2025-03-10.
    Devolve None para vazio, data impossivel ('31/02/2025') ou ano fora de 2000 a 2030."""
    texto = limpar_texto(texto)
    if texto is None:
        return None
    texto = texto[:10]    # descarta a hora
    for formato in FORMATOS_DATA:
        try:
            data = datetime.strptime(texto, formato).date()
        except ValueError:
            continue                          # nao era esse formato: tente o proximo
        if 2000 <= data.year <= 2030:
            return data
        return None
    return None


# =============================================================================================
# TESTE: python -m src.limpeza
# =============================================================================================
from datetime import date  # noqa: E402

CASOS = [
    # (funcao, argumentos, resultado esperado)
    ("tirar_espacos", ("  Ana   Maria ",), "Ana Maria"),
    ("eh_nulo", ("N/A",), True), ("eh_nulo", ("SEM INFORMAÇÃO",), True), ("eh_nulo", ("",), True),
    ("eh_nulo", ("Ana",), False), ("eh_nulo", ("0", True), True), ("eh_nulo", ("0", False), False),
    ("limpar_texto", ("AquisiÃ§Ã£o de mÃ³veis",), "Aquisição de móveis"),
    ("limpar_texto", ("Aquisição",), "Aquisição"),
    ("limpar_texto", ("  Ministério  da   Saúde  ",), "Ministério da Saúde"),
    ("limpar_texto", ("n/a",), None), ("limpar_texto", (" ",), None), ("limpar_texto", ("0",), None),
    ("padronizar_nome", ("  Ministério  da   Saúde  ",), "MINISTÉRIO DA SAÚDE"),
    ("padronizar_nome", ("Pregão-Eletrônico",), "PREGÃO - ELETRÔNICO"),
    ("limpar_documento", ("11.222.333/0001-81", "PJ"), "11222333000181"),
    ("limpar_documento", ("11222333000181", None), "11222333000181"),
    ("limpar_documento", ("1222333000181", "PJ"), "01222333000181"),
    ("limpar_documento", ("360305000104", "PJ"), "00360305000104"),
    ("limpar_documento", ("111.444.777-35", "PF"), "11144477735"),
    ("limpar_documento", ("1234567890", "PF"), "01234567890"),
    ("limpar_documento", (" 11222333000181 ", "PJ"), "11222333000181"),
    ("limpar_documento", ("N/A", "PJ"), None), ("limpar_documento", ("-", "PJ"), None),
    ("limpar_documento", ("ABC123", "PE"), "ABC123"),
    ("limpar_documento", ("123456789012345", "PJ"), None),
    ("converter_numero", ("R$ 1.234,56",), 1234.56), ("converter_numero", ("1,234.56",), 1234.56),
    ("converter_numero", ("1234.56",), 1234.56), ("converter_numero", ("1.234",), 1.234),
    ("converter_numero", ("0,754",), 0.754), ("converter_numero", ("746.815",), 746.815),
    ("converter_numero", ("1.234.567",), 1234567.0), ("converter_numero", ("12,5",), 12.5),
    ("converter_numero", ("1.234.567,89",), 1234567.89), ("converter_numero", ("R$ -12,50",), -12.5),
    ("converter_numero", ("(1.500,00)",), -1500.0), ("converter_numero", ("1.500,00-",), -1500.0),
    ("converter_numero", ("R$ 2.000,00",), 2000.0), ("converter_numero", ("493231.6000",), 493231.6),
    ("converter_numero", ("0",), 0.0), ("converter_numero", ("N/A",), None), ("converter_numero", ("",), None),
    ("converter_data", ("2025-03-10T08:30:00",), date(2025, 3, 10)), ("converter_data", ("10/03/2025",), date(2025, 3, 10)),
    ("converter_data", ("10-03-2025",), date(2025, 3, 10)), ("converter_data", ("2025/03/10",), date(2025, 3, 10)),
    ("converter_data", ("20250310",), date(2025, 3, 10)), ("converter_data", ("10/03/2025 14:20",), date(2025, 3, 10)),
    ("converter_data", ("10.03.2025",), date(2025, 3, 10)), ("converter_data", ("31/02/2025",), None),
    ("converter_data", ("0001-01-01",), None), ("converter_data", ("-",), None), ("converter_data", ("",), None),
]


def testar():
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")        
    except (AttributeError, ValueError):
        pass
    acertos = 0
    for nome, args, esperado in CASOS:
        try:
            obtido = globals()[nome](*args)
            ok = obtido == esperado
        except Exception as erro:                       # funcao com erro
            obtido, ok = f"erro: {type(erro).__name__}", False
        acertos += ok
        if not ok:
            print(f"✘ {nome}{args}  esperado {esperado!r}  obtido {obtido!r}")
    print(f"\n{acertos} de {len(CASOS)} exemplos certos" + ("  ✔ tudo certo, pode ir para a proxima etapa!" if acertos == len(CASOS) else "  -> continue completando"))
    return acertos == len(CASOS)


if __name__ == "__main__":
    raise SystemExit(0 if testar() else 1)
