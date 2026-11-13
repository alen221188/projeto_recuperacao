-- 02_perguntas.sql - as 10 perguntas de negocio da Controladoria.
-- Em cada pergunta o comentario traz o valor esperado da prova real (anexo 8).
-- Para ver os resultados sem o pgAdmin: python -m src.conferir_sql
--
-- Regras usadas nas consultas:
--  * percentual = soma / soma (nunca media de percentuais)
--  * economia so conta item comparavel (comparavel = 1)
--  * NULLIF no denominador, porque Credenciamento nao tem item comparavel
--  * volume = soma de valor_total_homologado de todos os itens


-- P1 - Economia global: qual o % e o valor nominal economizado pelo governo?
-- Esperado: economia R$ 992.861.686,95 | 14,46% | 5.457 itens comparaveis
SELECT
    SUM(CASE WHEN comparavel = 1 THEN valor_total_estimado ELSE 0 END)                    AS estimado_comparavel,
    SUM(CASE WHEN comparavel = 1 THEN valor_total_homologado ELSE 0 END)                  AS homologado_comparavel,
    SUM(economia_valor)                                                                   AS economia_rs,
    ROUND(100.0 * SUM(economia_valor)
          / NULLIF(SUM(CASE WHEN comparavel = 1 THEN valor_total_estimado ELSE 0 END), 0), 2) AS economia_pct,
    SUM(comparavel)                                                                       AS itens_comparaveis,
    COUNT(*)                                                                              AS itens_total,
    SUM(valor_total_homologado)                                                           AS volume_homologado
FROM fato_item_contratado;


-- P2 - Fornecedores: quem sao os 10 maiores em volume e quanto do total concentram?
-- A subconsulta no denominador traz o volume total.
SELECT
    RANK() OVER (ORDER BY SUM(f.valor_total_homologado) DESC)                             AS ranking,
    d.nome_fornecedor,
    d.ni_fornecedor,
    SUM(f.valor_total_homologado)                                                         AS volume,
    ROUND(100.0 * SUM(f.valor_total_homologado)
          / (SELECT SUM(valor_total_homologado) FROM fato_item_contratado), 2)            AS pct_do_total
FROM fato_item_contratado f
JOIN dim_fornecedor d ON d.sk_fornecedor = f.sk_fornecedor
GROUP BY d.sk_fornecedor, d.nome_fornecedor, d.ni_fornecedor
ORDER BY volume DESC
LIMIT 10;

-- P2 (complemento) - concentracao dos 10 maiores somados (soma / soma)
SELECT ROUND(100.0 * SUM(volume) / (SELECT SUM(valor_total_homologado) FROM fato_item_contratado), 2) AS pct_top10_fornecedores
FROM (
    SELECT SUM(valor_total_homologado) AS volume
    FROM fato_item_contratado
    GROUP BY sk_fornecedor
    ORDER BY volume DESC
    LIMIT 10
) AS top10;


-- P3 - Modalidades: qual economiza mais (desagio) e qual concentra mais volume?
-- Credenciamento (id 12) fica com economia vazia: nenhum item dele e comparavel (e esperado).
SELECT
    m.modalidade_id,
    m.nome_modalidade,
    COUNT(*)                                                                              AS itens,
    SUM(f.valor_total_homologado)                                                         AS volume,
    ROUND(100.0 * SUM(f.valor_total_homologado)
          / (SELECT SUM(valor_total_homologado) FROM fato_item_contratado), 2)            AS pct_do_volume,
    SUM(f.economia_valor)                                                                 AS economia_rs,
    ROUND(100.0 * SUM(f.economia_valor)
          / NULLIF(SUM(CASE WHEN f.comparavel = 1 THEN f.valor_total_estimado ELSE 0 END), 0), 2) AS economia_pct
FROM fato_item_contratado f
JOIN dim_modalidade m ON m.sk_modalidade = f.sk_modalidade
GROUP BY m.modalidade_id, m.nome_modalidade
ORDER BY volume DESC;


-- P4 - Ciclo: duracao media (dias) entre publicacao e homologacao, por orgao (nome padronizado).
-- COUNT(dias_ciclo) conta so itens com ciclo; o HAVING deixa so orgaos com 5 ou mais.
-- Geral (esperado): media 48,1 | maximo 611 | 5.896 itens com ciclo | 230 sem ciclo
SELECT
    o.nome_orgao,
    COUNT(f.dias_ciclo)                 AS itens_com_ciclo,
    ROUND(AVG(f.dias_ciclo), 1)         AS ciclo_medio_dias,
    MAX(f.dias_ciclo)                   AS ciclo_maximo_dias
FROM fato_item_contratado f
JOIN dim_orgao o ON o.sk_orgao = f.sk_orgao
GROUP BY o.nome_orgao
HAVING COUNT(f.dias_ciclo) >= 5
ORDER BY ciclo_medio_dias DESC;

-- P4 (complemento) - numeros gerais do ciclo
SELECT
    ROUND(AVG(dias_ciclo), 1)           AS ciclo_medio_dias,
    MAX(dias_ciclo)                     AS ciclo_maximo_dias,
    COUNT(dias_ciclo)                   AS itens_com_ciclo,
    COUNT(*) - COUNT(dias_ciclo)        AS itens_sem_ciclo
FROM fato_item_contratado;


-- P5 - Regional: onde se gasta mais e onde o desconto e melhor (por regiao e por UF).
-- Por regiao:
SELECT
    l.regiao,
    SUM(f.valor_total_homologado)                                                         AS volume,
    ROUND(100.0 * SUM(f.valor_total_homologado)
          / (SELECT SUM(valor_total_homologado) FROM fato_item_contratado), 2)            AS pct_do_volume,
    ROUND(100.0 * SUM(f.economia_valor)
          / NULLIF(SUM(CASE WHEN f.comparavel = 1 THEN f.valor_total_estimado ELSE 0 END), 0), 2) AS economia_pct,
    COUNT(DISTINCT o.cnpj_orgao)                                                          AS unidades_compradoras
FROM fato_item_contratado f
JOIN dim_localidade l ON l.sk_localidade = f.sk_localidade
JOIN dim_orgao o      ON o.sk_orgao = f.sk_orgao
GROUP BY l.regiao
ORDER BY volume DESC;

-- P5 (por UF)
SELECT
    l.uf_sigla,
    l.regiao,
    SUM(f.valor_total_homologado)                                                         AS volume,
    ROUND(100.0 * SUM(f.economia_valor)
          / NULLIF(SUM(CASE WHEN f.comparavel = 1 THEN f.valor_total_estimado ELSE 0 END), 0), 2) AS economia_pct
FROM fato_item_contratado f
JOIN dim_localidade l ON l.sk_localidade = f.sk_localidade
GROUP BY l.uf_sigla, l.regiao
ORDER BY volume DESC;


-- P6 - Perfil do gasto: bens, servicos e obras e engenharia.
-- O perfil e coluna da propria fato (nao precisa de JOIN).
-- Esperado (% do volume): Obras e engenharia 60,8 | Servicos 36,6 | Bens 2,6   (itens: 967 | 1.849 | 3.310)
SELECT
    perfil_gasto,
    COUNT(*)                                                                              AS itens,
    SUM(valor_total_homologado)                                                           AS volume,
    ROUND(100.0 * SUM(valor_total_homologado)
          / (SELECT SUM(valor_total_homologado) FROM fato_item_contratado), 1)            AS pct_do_volume,
    ROUND(SUM(valor_total_homologado) / COUNT(*), 2)                                      AS ticket_medio,
    ROUND(100.0 * SUM(economia_valor)
          / NULLIF(SUM(CASE WHEN comparavel = 1 THEN valor_total_estimado ELSE 0 END), 0), 2) AS economia_pct
FROM fato_item_contratado
GROUP BY perfil_gasto
ORDER BY volume DESC;


-- P7 - Evolucao mensal (pela data de PUBLICACAO): volume, economia e variacao contra o mes anterior.
-- LAG traz o volume do mes anterior (o primeiro mes fica vazio).
-- Esperado: pico jun/2025 R$ 1.719.241.434,54 (21,4%) | menor mai/2025 R$ 227.978.200,52
--           economia % mensal de 8,97% (dez/2025) a 20,49% (ago/2025)
WITH mensal AS (
    SELECT
        DATE_TRUNC('month', data_publicacao)::date                                        AS mes,
        SUM(valor_total_homologado)                                                       AS volume,
        SUM(economia_valor)                                                               AS economia_rs,
        SUM(CASE WHEN comparavel = 1 THEN valor_total_estimado ELSE 0 END)                AS estimado_comparavel
    FROM fato_item_contratado
    GROUP BY DATE_TRUNC('month', data_publicacao)
)
SELECT
    TO_CHAR(mes, 'YYYY-MM')                                                               AS mes,
    volume,
    ROUND(100.0 * volume / SUM(volume) OVER (), 1)                                        AS pct_do_ano,
    LAG(volume) OVER (ORDER BY mes)                                                       AS volume_mes_anterior,
    ROUND(100.0 * (volume - LAG(volume) OVER (ORDER BY mes))
          / NULLIF(LAG(volume) OVER (ORDER BY mes), 0), 1)                                AS variacao_mensal_pct,
    ROUND(100.0 * economia_rs / NULLIF(estimado_comparavel, 0), 2)                        AS economia_pct
FROM mensal
ORDER BY mes;


-- P8 - Sobrepreco: itens COMPARAVEIS homologados acima do estimado, quanto soma e onde se concentram.
-- Esperado: 27 itens | R$ 44.440,34   (sem o filtro comparavel = 1 seriam 60 itens)
SELECT COUNT(*)                                                                           AS itens_com_sobrepreco,
       SUM(valor_total_homologado - valor_total_estimado)                                 AS sobrepreco_rs
FROM fato_item_contratado
WHERE comparavel = 1
  AND valor_total_homologado > valor_total_estimado;

-- P8 (por orgao, nome padronizado)
SELECT
    o.nome_orgao,
    COUNT(*)                                                                              AS itens_com_sobrepreco,
    SUM(f.valor_total_homologado - f.valor_total_estimado)                                AS sobrepreco_rs
FROM fato_item_contratado f
JOIN dim_orgao o ON o.sk_orgao = f.sk_orgao
WHERE f.comparavel = 1
  AND f.valor_total_homologado > f.valor_total_estimado
GROUP BY o.nome_orgao
ORDER BY sobrepreco_rs DESC;


-- P9 - Micro e pequenas empresas (MPE = ME + EPP) contra as demais.
-- O CASE junta ME e EPP em MPE. Fornecedores = COUNT(DISTINCT sk_fornecedor).
-- Esperado: MPE 19,87% do volume | 3.820 itens | 1.494 fornecedores | economia MPE 15,97% x demais 13,97%
SELECT
    CASE WHEN d.porte IN ('ME', 'EPP') THEN 'MPE' ELSE 'Demais' END                       AS grupo,
    COUNT(*)                                                                              AS itens_vencidos,
    COUNT(DISTINCT f.sk_fornecedor)                                                       AS fornecedores,
    SUM(f.valor_total_homologado)                                                         AS volume,
    ROUND(100.0 * SUM(f.valor_total_homologado)
          / (SELECT SUM(valor_total_homologado) FROM fato_item_contratado), 2)            AS pct_do_volume,
    ROUND(100.0 * SUM(f.economia_valor)
          / NULLIF(SUM(CASE WHEN f.comparavel = 1 THEN f.valor_total_estimado ELSE 0 END), 0), 2) AS economia_pct
FROM fato_item_contratado f
JOIN dim_fornecedor d ON d.sk_fornecedor = f.sk_fornecedor
GROUP BY CASE WHEN d.porte IN ('ME', 'EPP') THEN 'MPE' ELSE 'Demais' END
ORDER BY volume DESC;


-- P10 - Orgaos e Poderes: top 10 orgaos em volume e distribuicao por Poder.
-- Agrupa pelo nome do orgao (o mesmo orgao tem varios CNPJ).
-- Esperado: DNIT R$ 2.610.387.744,91 (32,45%) | top 10 = 71,29% (varia um pouco com a padronizacao)
SELECT
    RANK() OVER (ORDER BY SUM(f.valor_total_homologado) DESC)                             AS ranking,
    o.nome_orgao,
    SUM(f.valor_total_homologado)                                                         AS volume,
    ROUND(100.0 * SUM(f.valor_total_homologado)
          / (SELECT SUM(valor_total_homologado) FROM fato_item_contratado), 2)            AS pct_do_total
FROM fato_item_contratado f
JOIN dim_orgao o ON o.sk_orgao = f.sk_orgao
GROUP BY o.nome_orgao
ORDER BY volume DESC
LIMIT 10;

-- P10 (complemento) - concentracao dos 10 maiores orgaos somados
SELECT ROUND(100.0 * SUM(volume) / (SELECT SUM(valor_total_homologado) FROM fato_item_contratado), 2) AS pct_top10_orgaos
FROM (
    SELECT SUM(f.valor_total_homologado) AS volume
    FROM fato_item_contratado f
    JOIN dim_orgao o ON o.sk_orgao = f.sk_orgao
    GROUP BY o.nome_orgao
    ORDER BY volume DESC
    LIMIT 10
) AS top10;

-- P10 (por Poder) - esperado volume: Executivo 97,66% | Judiciario 2,29% | Legislativo 0,05%
--                            economia: Executivo 14,54% | Judiciario 10,74% | Legislativo 21,57%
--                            unidades: 350 | 10 | 3
SELECT
    o.poder,
    SUM(f.valor_total_homologado)                                                         AS volume,
    ROUND(100.0 * SUM(f.valor_total_homologado)
          / (SELECT SUM(valor_total_homologado) FROM fato_item_contratado), 2)            AS pct_do_volume,
    ROUND(100.0 * SUM(f.economia_valor)
          / NULLIF(SUM(CASE WHEN f.comparavel = 1 THEN f.valor_total_estimado ELSE 0 END), 0), 2) AS economia_pct,
    COUNT(DISTINCT o.cnpj_orgao)                                                          AS unidades_compradoras
FROM fato_item_contratado f
JOIN dim_orgao o ON o.sk_orgao = f.sk_orgao
GROUP BY o.poder
ORDER BY volume DESC;
