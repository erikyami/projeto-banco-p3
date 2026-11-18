CREATE DATABASE IF NOT EXISTS eventos_db;
USE eventos_db;

CREATE TABLE usuario (
    id_usuario INT AUTO_INCREMENT PRIMARY KEY,
    cpf CHAR(11) UNIQUE NOT NULL,
    nome VARCHAR(150) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    senha_hash VARCHAR(255) NOT NULL,
    perfil VARCHAR(50) DEFAULT 'APOIO',
    status ENUM('ATIVO', 'INATIVO', 'PENDENTE') DEFAULT 'PENDENTE',
    data_cadastro DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE participante (
    id_participante INT AUTO_INCREMENT PRIMARY KEY,
    cpf CHAR(11) UNIQUE NOT NULL,
    nome VARCHAR(150) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    senha_hash VARCHAR(255) NOT NULL,
    telefone VARCHAR(20)
);

CREATE TABLE palestrante (
    id_palestrante INT AUTO_INCREMENT PRIMARY KEY,
    cpf CHAR(11) UNIQUE NOT NULL,
    nome VARCHAR(150) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    senha_hash VARCHAR(255) NOT NULL,
    telefone VARCHAR(20),
    curriculo TEXT
);

CREATE TABLE evento (
    id_evento INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE,
    nome VARCHAR(180) NOT NULL,
    descricao TEXT,
    data_inicio DATE,
    data_fim DATE,
    local VARCHAR(180),
    status ENUM('ATIVO', 'CANCELADO', 'FINALIZADO') DEFAULT 'ATIVO'
);

CREATE TABLE atividade (
    id_atividade INT AUTO_INCREMENT PRIMARY KEY,
    id_evento INT NOT NULL,
    tipo VARCHAR(80),
    nome VARCHAR(180) NOT NULL,
    descricao TEXT,
    data_atividade DATE,
    data_fim DATE,
    hora_inicio TIME,
    hora_fim TIME,
    carga_horaria DECIMAL(5,2),
    limite_vagas INT,
    frequencia_minima DECIMAL(5,2) DEFAULT 75.00,
    exige_conclusao TINYINT(1) DEFAULT 0,
    status VARCHAR(50) DEFAULT 'AGENDADA',
    FOREIGN KEY (id_evento) REFERENCES evento(id_evento)
);

CREATE TABLE atividade_palestrante (
    id_atividade INT NOT NULL,
    id_palestrante INT NOT NULL,
    PRIMARY KEY (id_atividade, id_palestrante),
    FOREIGN KEY (id_atividade) REFERENCES atividade(id_atividade),
    FOREIGN KEY (id_palestrante) REFERENCES palestrante(id_palestrante)
);

CREATE TABLE inscricao (
    id_inscricao INT AUTO_INCREMENT PRIMARY KEY,
    id_participante INT NOT NULL,
    id_evento INT NOT NULL,
    numero VARCHAR(50) UNIQUE,
    data_inscricao DATETIME DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'CONFIRMADA',
    UNIQUE (id_participante, id_evento),
    FOREIGN KEY (id_participante) REFERENCES participante(id_participante),
    FOREIGN KEY (id_evento) REFERENCES evento(id_evento)
);

CREATE TABLE participacao_atividade (
    id_participacao INT AUTO_INCREMENT PRIMARY KEY,
    id_inscricao INT NOT NULL,
    id_atividade INT NOT NULL,
    data_inscricao DATETIME DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'CONFIRMADA',
    UNIQUE (id_inscricao, id_atividade),
    FOREIGN KEY (id_inscricao) REFERENCES inscricao(id_inscricao),
    FOREIGN KEY (id_atividade) REFERENCES atividade(id_atividade)
);

-- Tabela ajustada para permitir chamada em múltiplos dias com auditoria de quem gerou e removeu
CREATE TABLE presenca (
    id_presenca INT AUTO_INCREMENT PRIMARY KEY,
    id_participacao INT NOT NULL,
    id_usuario INT NOT NULL,
    id_usuario_remocao INT NULL,
    data_aula DATE NOT NULL,
    presente TINYINT(1) DEFAULT 0,
    data_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
    data_remocao DATETIME NULL,
    UNIQUE (id_participacao, data_aula),
    FOREIGN KEY (id_participacao) REFERENCES participacao_atividade(id_participacao),
    FOREIGN KEY (id_usuario) REFERENCES usuario(id_usuario),
    FOREIGN KEY (id_usuario_remocao) REFERENCES usuario(id_usuario)
);

CREATE TABLE log_presenca (
    id_log INT AUTO_INCREMENT PRIMARY KEY,
    id_participacao INT NOT NULL,
    id_usuario INT NOT NULL,
    acao ENUM('GERADA', 'REMOVIDA') NOT NULL,
    data_aula DATE NOT NULL,
    data_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_participacao) REFERENCES participacao_atividade(id_participacao),
    FOREIGN KEY (id_usuario) REFERENCES usuario(id_usuario)
);

CREATE TABLE certificado (
    id_certificado INT AUTO_INCREMENT PRIMARY KEY,
    tipo_destinatario ENUM('PARTICIPANTE', 'PALESTRANTE') NOT NULL DEFAULT 'PARTICIPANTE',
    id_participacao INT NULL,
    id_palestrante INT NULL,
    id_atividade INT NULL,
    codigo_validacao VARCHAR(80) UNIQUE NOT NULL,
    status ENUM('VALIDO', 'REVOGADO') DEFAULT 'VALIDO',
    data_emissao DATETIME DEFAULT CURRENT_TIMESTAMP,
    carga_horaria DECIMAL(5,2) NOT NULL,
    UNIQUE (id_participacao),
    UNIQUE (id_palestrante, id_atividade),
    FOREIGN KEY (id_participacao) REFERENCES participacao_atividade(id_participacao),
    FOREIGN KEY (id_palestrante) REFERENCES palestrante(id_palestrante),
    FOREIGN KEY (id_atividade) REFERENCES atividade(id_atividade)
);

-- ===================================================================
-- DADOS INICIAIS (SEEDS) PARA TESTES
-- Senha padrão para todos os seeds: "senha123"
-- SHA-256 de "senha123": 55a5e9e78207b4df8699d60886fa070079463547b095d1a05bc719bb4e6cd251
-- ===================================================================

INSERT INTO usuario (cpf, nome, email, senha_hash, perfil, status) VALUES
('11122233344', 'Equipe Apoio 1', 'staff@eventos.ufma.br', '55a5e9e78207b4df8699d60886fa070079463547b095d1a05bc719bb4e6cd251', 'APOIO', 'ATIVO'),
('22233344455', 'Coordenador Geral', 'admin@eventos.ufma.br', '55a5e9e78207b4df8699d60886fa070079463547b095d1a05bc719bb4e6cd251', 'ADMIN', 'ATIVO');

INSERT INTO palestrante (cpf, nome, email, senha_hash, telefone, curriculo) VALUES
('33344455566', 'Dra. Camila Vasconcelos', 'palestrante@eventos.ufma.br', '55a5e9e78207b4df8699d60886fa070079463547b095d1a05bc719bb4e6cd251', '(98) 98765-4321', 'Doutora em Ciência da Computação, pesquisadora de Bancos de Dados e Sistemas Distribuídos.');

INSERT INTO participante (cpf, nome, email, senha_hash, telefone) VALUES
('44455566677', 'Francisco Erik da Silva', 'erik@discente.ufma.br', '55a5e9e78207b4df8699d60886fa070079463547b095d1a05bc719bb4e6cd251', '(98) 98111-2222'),
('55566677788', 'Joao Elivaldo Barros Moraes', 'elivaldo@discente.ufma.br', '55a5e9e78207b4df8699d60886fa070079463547b095d1a05bc719bb4e6cd251', '(98) 98222-3333'),
('66677788899', 'Jose Diomar Machado Costa', 'diomar@discente.ufma.br', '55a5e9e78207b4df8699d60886fa070079463547b095d1a05bc719bb4e6cd251', '(98) 98333-4444');

INSERT INTO evento (codigo, nome, descricao, data_inicio, data_fim, local, status) VALUES
('EVT-BICT-2026', 'Jornada de Tecnologia e Banco de Dados BICT/UFMA', 'Semana acadêmica com palestras, minicursos e mesas redondas sobre modelagem relacional e desenvolvimento web.', '2026-11-20', '2026-11-24', 'Centro Pedagógico Paulo Freire - Campus Bacanga', 'ATIVO');

INSERT INTO atividade (id_evento, tipo, nome, descricao, data_atividade, data_fim, hora_inicio, hora_fim, carga_horaria, limite_vagas, frequencia_minima, exige_conclusao, status) VALUES
(1, 'Minicurso', 'Modelagem Relacional e SQL Avançado', 'Práticas de normalização e consultas de alta performance.', '2026-11-20', '2026-11-22', '14:00:00', '18:00:00', 8.00, 40, 75.00, 0, 'AGENDADA'),
(1, 'Palestra', 'Arquitetura de Dados em Sistemas Modernos', 'Apresentação expositiva sobre modelagem relacional na nuvem.', '2026-11-21', '2026-11-21', '09:00:00', '12:00:00', 3.00, 100, 100.00, 0, 'AGENDADA');

INSERT INTO atividade_palestrante (id_atividade, id_palestrante) VALUES
(1, 1),
(2, 1);

INSERT INTO inscricao (id_participante, id_evento, numero, status) VALUES
(1, 1, 'INS-2026-001', 'CONFIRMADA'),
(2, 1, 'INS-2026-002', 'CONFIRMADA'),
(3, 1, 'INS-2026-003', 'CONFIRMADA');

INSERT INTO participacao_atividade (id_inscricao, id_atividade, status) VALUES
(1, 1, 'CONFIRMADA'),
(2, 1, 'CONFIRMADA'),
(3, 2, 'CONFIRMADA');

-- Presenças em múltiplos dias para a atividade 1 (Minicurso de 2 dias)
INSERT INTO presenca (id_participacao, id_usuario, data_aula, presente) VALUES
(1, 1, '2026-11-20', 1),
(1, 1, '2026-11-21', 1),
(2, 1, '2026-11-20', 1),
(2, 1, '2026-11-21', 0);

-- Certificado de Participante
INSERT INTO certificado (tipo_destinatario, id_participacao, codigo_validacao, status, carga_horaria) VALUES
('PARTICIPANTE', 1, 'CERT-UFMA-2026-BICT01', 'VALIDO', 8.00);

-- Certificado de Palestrante
INSERT INTO certificado (tipo_destinatario, id_palestrante, id_atividade, codigo_validacao, status, carga_horaria) VALUES
('PALESTRANTE', 1, 1, 'CERT-UFMA-2026-PALESTRA01', 'VALIDO', 8.00);
