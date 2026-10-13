BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Application de la migration  -> 0001

CREATE TABLE contributions (
    id SERIAL NOT NULL,
    entite VARCHAR(20) NOT NULL,
    operation VARCHAR(20) NOT NULL,
    cible_id INTEGER,
    version_cible INTEGER,
    donnees JSONB NOT NULL,
    empreinte VARCHAR(64) NOT NULL,
    statut VARCHAR(20) NOT NULL,
    motif TEXT NOT NULL,
    cree_le TIMESTAMP WITH TIME ZONE NOT NULL,
    traite_le TIMESTAMP WITH TIME ZONE,
    resultat_id INTEGER,
    PRIMARY KEY (id),
    CONSTRAINT ck_contribution_entite CHECK (entite IN ('source','compte','contenu','tag')),
    CONSTRAINT ck_contribution_operation CHECK (operation IN ('ajout','modification')),
    CONSTRAINT ck_contribution_statut CHECK (statut IN ('en_attente','validee','refusee','fusionnee'))
);

CREATE INDEX ix_contributions_empreinte ON contributions (empreinte);

CREATE INDEX ix_contributions_statut ON contributions (statut);

CREATE UNIQUE INDEX uq_contribution_attente ON contributions (empreinte) WHERE statut = 'en_attente';

CREATE TABLE defis (
    jeton VARCHAR(64) NOT NULL,
    reponse_hachee VARCHAR(64) NOT NULL,
    cree_le TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (jeton)
);

CREATE INDEX ix_defis_cree_le ON defis (cree_le);

CREATE TABLE plateformes (
    id SERIAL NOT NULL,
    nom VARCHAR(100) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (nom)
);

CREATE TABLE quotas (
    nom VARCHAR(40) NOT NULL,
    debut TIMESTAMP WITH TIME ZONE NOT NULL,
    nombre INTEGER NOT NULL,
    PRIMARY KEY (nom)
);

CREATE TABLE tags (
    nom VARCHAR(150) NOT NULL,
    cle VARCHAR(150) NOT NULL,
    nature VARCHAR(40) NOT NULL,
    description TEXT NOT NULL,
    parent_id INTEGER,
    id SERIAL NOT NULL,
    version INTEGER NOT NULL,
    cree_le TIMESTAMP WITH TIME ZONE NOT NULL,
    modifie_le TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_tag_nature CHECK (nature IN ('thematique','discours','qualification','categorie','mot_cle')),
    CONSTRAINT ck_tag_parent CHECK (parent_id IS NULL OR parent_id != id),
    FOREIGN KEY(parent_id) REFERENCES tags (id) ON DELETE RESTRICT,
    CONSTRAINT uq_tag_cle_nature UNIQUE (cle, nature)
);

CREATE INDEX ix_tags_parent_id ON tags (parent_id);

CREATE TABLE historique (
    id SERIAL NOT NULL,
    contribution_id INTEGER,
    entite VARCHAR(20) NOT NULL,
    entite_id INTEGER,
    action VARCHAR(30) NOT NULL,
    avant JSONB,
    apres JSONB,
    motif TEXT NOT NULL,
    cree_le TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(contribution_id) REFERENCES contributions (id) ON DELETE RESTRICT
);

CREATE INDEX ix_historique_contribution_id ON historique (contribution_id);

CREATE INDEX ix_historique_entite_id ON historique (entite_id);

CREATE TABLE sources (
    nom VARCHAR(300) NOT NULL,
    description TEXT NOT NULL,
    url VARCHAR(2048) NOT NULL,
    url_canonique VARCHAR(2048) NOT NULL,
    pays VARCHAR(100) NOT NULL,
    langue VARCHAR(100) NOT NULL,
    plateforme_id INTEGER NOT NULL,
    id SERIAL NOT NULL,
    version INTEGER NOT NULL,
    cree_le TIMESTAMP WITH TIME ZONE NOT NULL,
    modifie_le TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(plateforme_id) REFERENCES plateformes (id) ON DELETE RESTRICT,
    UNIQUE (url_canonique)
);

CREATE INDEX ix_sources_langue ON sources (langue);

CREATE INDEX ix_sources_nom ON sources (nom);

CREATE INDEX ix_sources_pays ON sources (pays);

CREATE INDEX ix_sources_plateforme_id ON sources (plateforme_id);

CREATE TABLE comptes (
    plateforme_id INTEGER NOT NULL,
    pseudonyme VARCHAR(300) NOT NULL,
    identifiant VARCHAR(300) NOT NULL,
    url VARCHAR(2048) NOT NULL,
    url_canonique VARCHAR(2048) NOT NULL,
    source_id INTEGER NOT NULL,
    id SERIAL NOT NULL,
    version INTEGER NOT NULL,
    cree_le TIMESTAMP WITH TIME ZONE NOT NULL,
    modifie_le TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(plateforme_id) REFERENCES plateformes (id) ON DELETE RESTRICT,
    FOREIGN KEY(source_id) REFERENCES sources (id) ON DELETE RESTRICT,
    UNIQUE (url_canonique)
);

CREATE INDEX ix_comptes_plateforme_id ON comptes (plateforme_id);

CREATE INDEX ix_comptes_pseudonyme ON comptes (pseudonyme);

CREATE INDEX ix_comptes_source_id ON comptes (source_id);

CREATE TABLE source_tags (
    source_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (source_id, tag_id),
    FOREIGN KEY(source_id) REFERENCES sources (id) ON DELETE CASCADE,
    FOREIGN KEY(tag_id) REFERENCES tags (id) ON DELETE RESTRICT
);

CREATE TABLE contenus (
    titre VARCHAR(300) NOT NULL,
    url VARCHAR(2048) NOT NULL,
    url_canonique VARCHAR(2048) NOT NULL,
    date DATE,
    description TEXT NOT NULL,
    type_media VARCHAR(40) NOT NULL,
    source_id INTEGER NOT NULL,
    compte_id INTEGER,
    plateforme_id INTEGER NOT NULL,
    id SERIAL NOT NULL,
    version INTEGER NOT NULL,
    cree_le TIMESTAMP WITH TIME ZONE NOT NULL,
    modifie_le TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_media CHECK (type_media IN ('video','article','publication','podcast','audio','pdf','autre')),
    FOREIGN KEY(compte_id) REFERENCES comptes (id) ON DELETE RESTRICT,
    FOREIGN KEY(plateforme_id) REFERENCES plateformes (id) ON DELETE RESTRICT,
    FOREIGN KEY(source_id) REFERENCES sources (id) ON DELETE RESTRICT,
    UNIQUE (url_canonique)
);

CREATE INDEX ix_contenus_compte_id ON contenus (compte_id);

CREATE INDEX ix_contenus_date ON contenus (date);

CREATE INDEX ix_contenus_plateforme_id ON contenus (plateforme_id);

CREATE INDEX ix_contenus_source_id ON contenus (source_id);

CREATE INDEX ix_contenus_titre ON contenus (titre);

CREATE INDEX ix_contenus_type_media ON contenus (type_media);

CREATE TABLE contenu_tags (
    contenu_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (contenu_id, tag_id),
    FOREIGN KEY(contenu_id) REFERENCES contenus (id) ON DELETE CASCADE,
    FOREIGN KEY(tag_id) REFERENCES tags (id) ON DELETE RESTRICT
);

CREATE TABLE "references" (
    id SERIAL NOT NULL,
    titre VARCHAR(500) NOT NULL,
    url VARCHAR(2048) NOT NULL,
    type_reference VARCHAR(40) NOT NULL,
    citation TEXT NOT NULL,
    source_id INTEGER,
    compte_id INTEGER,
    contenu_id INTEGER,
    tag_id INTEGER,
    qualification_tag_id INTEGER,
    PRIMARY KEY (id),
    CONSTRAINT ck_reference_proprietaire CHECK ((CASE WHEN source_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN compte_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN contenu_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN tag_id IS NOT NULL THEN 1 ELSE 0 END) = 1),
    FOREIGN KEY(compte_id) REFERENCES comptes (id) ON DELETE CASCADE,
    FOREIGN KEY(contenu_id) REFERENCES contenus (id) ON DELETE CASCADE,
    FOREIGN KEY(qualification_tag_id) REFERENCES tags (id) ON DELETE RESTRICT,
    FOREIGN KEY(source_id) REFERENCES sources (id) ON DELETE CASCADE,
    FOREIGN KEY(tag_id) REFERENCES tags (id) ON DELETE CASCADE
);

CREATE INDEX ix_references_compte_id ON "references" (compte_id);

CREATE INDEX ix_references_contenu_id ON "references" (contenu_id);

CREATE INDEX ix_references_qualification_tag_id ON "references" (qualification_tag_id);

CREATE INDEX ix_references_source_id ON "references" (source_id);

CREATE INDEX ix_references_tag_id ON "references" (tag_id);

INSERT INTO alembic_version (version_num) VALUES ('0001') RETURNING alembic_version.version_num;

-- Application de la migration 0001 -> 0002

INSERT INTO plateformes (nom) VALUES ('YouTube') ON CONFLICT (nom) DO NOTHING;

INSERT INTO plateformes (nom) VALUES ('TikTok') ON CONFLICT (nom) DO NOTHING;

INSERT INTO plateformes (nom) VALUES ('Facebook') ON CONFLICT (nom) DO NOTHING;

INSERT INTO plateformes (nom) VALUES ('Instagram') ON CONFLICT (nom) DO NOTHING;

INSERT INTO plateformes (nom) VALUES ('X') ON CONFLICT (nom) DO NOTHING;

INSERT INTO plateformes (nom) VALUES ('Telegram') ON CONFLICT (nom) DO NOTHING;

INSERT INTO plateformes (nom) VALUES ('Rumble') ON CONFLICT (nom) DO NOTHING;

INSERT INTO plateformes (nom) VALUES ('Odysee') ON CONFLICT (nom) DO NOTHING;

INSERT INTO plateformes (nom) VALUES ('Site Internet') ON CONFLICT (nom) DO NOTHING;

INSERT INTO plateformes (nom) VALUES ('Blog') ON CONFLICT (nom) DO NOTHING;

INSERT INTO plateformes (nom) VALUES ('Forum') ON CONFLICT (nom) DO NOTHING;

INSERT INTO plateformes (nom) VALUES ('Podcast') ON CONFLICT (nom) DO NOTHING;

INSERT INTO plateformes (nom) VALUES ('Radio') ON CONFLICT (nom) DO NOTHING;

INSERT INTO plateformes (nom) VALUES ('Document PDF') ON CONFLICT (nom) DO NOTHING;

INSERT INTO quotas (nom, debut, nombre) VALUES ('connexion', '2026-01-01 00:00:00+00:00', 0);

INSERT INTO quotas (nom, debut, nombre) VALUES ('defis', '2026-01-01 00:00:00+00:00', 0);

INSERT INTO quotas (nom, debut, nombre) VALUES ('soumissions', '2026-01-01 00:00:00+00:00', 0);

INSERT INTO quotas (nom, debut, nombre) VALUES ('moderation', '2026-01-01 00:00:00+00:00', 0);

UPDATE alembic_version SET version_num='0002' WHERE alembic_version.version_num = '0001';

COMMIT;
