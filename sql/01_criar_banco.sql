-- 01_criar_banco.sql - cria o Star Schema (1 fato + 4 dimensoes) no PostgreSQL.
-- O banco e recriado pelo Python (banco.recriar_banco); este script so cria as tabelas.
--
-- Resumo da modelagem:
--  * grao da fato: um item de contratacao (numero_controle_pncp + numero_item)
--  * toda tabela tem chave primaria substituta (sk_...); a chave natural fica como UNIQUE
--  * dinheiro em DECIMAL, nunca FLOAT (FLOAT arredonda errado e a soma nao fecha)
--  * os CHECK sao a segunda barreira, depois do Python
--  * o calendario nao e tabela do banco: e criado em DAX no Power BI

-- ---------------------------------- DIMENSOES ----------------------------------------

-- Quem comprou: uma linha por CNPJ de orgao (o mesmo orgao pode ter varios CNPJ)
CREATE TABLE dim_orgao (
    sk_orgao    INTEGER      PRIMARY KEY,
    cnpj_orgao  VARCHAR(14)  NOT NULL UNIQUE,     -- chave natural (14 digitos)
    nome_orgao  VARCHAR(300) NOT NULL,            -- nome padronizado
    poder       VARCHAR(20)  NOT NULL             -- Executivo, Legislativo, Judiciário ou Não informado
);

-- Quem vendeu: uma linha por CNPJ/CPF de fornecedor
CREATE TABLE dim_fornecedor (
    sk_fornecedor   INTEGER      PRIMARY KEY,
    ni_fornecedor   VARCHAR(30)  NOT NULL UNIQUE, -- CNPJ, CPF ou documento de estrangeiro
    nome_fornecedor VARCHAR(300),
    tipo_pessoa     VARCHAR(2),                   -- PJ, PF ou PE
    porte           VARCHAR(15)  NOT NULL
        CHECK (porte IN ('ME', 'EPP', 'Demais', 'Não informado'))
);

-- Como comprou: uma linha por modalidade
CREATE TABLE dim_modalidade (
    sk_modalidade   INTEGER      PRIMARY KEY,
    modalidade_id   INTEGER      NOT NULL UNIQUE,
    nome_modalidade VARCHAR(60)  NOT NULL
);

-- Onde: uma linha por UF (a regiao foi criada no Python)
CREATE TABLE dim_localidade (
    sk_localidade INTEGER      PRIMARY KEY,
    uf_sigla      VARCHAR(2)   NOT NULL UNIQUE,
    uf_nome       VARCHAR(40)  NOT NULL,
    regiao        VARCHAR(20)  NOT NULL
);

-- ------------------------------------ FATO -------------------------------------------

CREATE TABLE fato_item_contratado (
    sk_fato                   SERIAL        PRIMARY KEY,
    numero_controle_pncp      VARCHAR(60)   NOT NULL,
    numero_item               INTEGER       NOT NULL,

    sk_orgao                  INTEGER       NOT NULL REFERENCES dim_orgao (sk_orgao),
    sk_fornecedor             INTEGER       NOT NULL REFERENCES dim_fornecedor (sk_fornecedor),
    sk_modalidade             INTEGER       NOT NULL REFERENCES dim_modalidade (sk_modalidade),
    sk_localidade             INTEGER       NOT NULL REFERENCES dim_localidade (sk_localidade),

    data_publicacao           DATE,
    data_homologacao          DATE,                          -- NULL quando homologou antes de publicar

    descricao_item            TEXT,
    perfil_gasto              VARCHAR(20)   NOT NULL
        CHECK (perfil_gasto IN ('Bens', 'Serviços', 'Obras e engenharia')),

    quantidade                DECIMAL(18,4) NOT NULL CHECK (quantidade > 0),
    valor_unitario_estimado   DECIMAL(18,4) NOT NULL CHECK (valor_unitario_estimado >= 0),
    valor_total_estimado      DECIMAL(18,2) NOT NULL CHECK (valor_total_estimado >= 0),
    valor_unitario_homologado DECIMAL(18,4) NOT NULL CHECK (valor_unitario_homologado >= 0),
    valor_total_homologado    DECIMAL(18,2) NOT NULL CHECK (valor_total_homologado >= 0),

    comparavel                SMALLINT      NOT NULL CHECK (comparavel IN (0, 1)),
    economia_valor            DECIMAL(18,2),                 -- NULL nos itens nao comparaveis
    dias_ciclo                INTEGER,                       -- NULL quando nao ha ciclo

    -- o mesmo item nao pode entrar duas vezes
    CONSTRAINT uq_fato_item UNIQUE (numero_controle_pncp, numero_item),
    -- economia so existe em item comparavel e o ciclo nao pode ser negativo
    CONSTRAINT ck_economia_so_comparavel CHECK (comparavel = 1 OR economia_valor IS NULL),
    CONSTRAINT ck_ciclo_nao_negativo CHECK (dias_ciclo IS NULL OR dias_ciclo >= 0)
);

-- Indices nas chaves estrangeiras e na data de publicacao
CREATE INDEX ix_fato_orgao        ON fato_item_contratado (sk_orgao);
CREATE INDEX ix_fato_fornecedor   ON fato_item_contratado (sk_fornecedor);
CREATE INDEX ix_fato_modalidade   ON fato_item_contratado (sk_modalidade);
CREATE INDEX ix_fato_localidade   ON fato_item_contratado (sk_localidade);
CREATE INDEX ix_fato_publicacao   ON fato_item_contratado (data_publicacao);
