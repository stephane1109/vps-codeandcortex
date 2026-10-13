"""Schema initial et contraintes documentaires

Révision : 0001
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "contributions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entite", sa.String(length=20), nullable=False),
        sa.Column("operation", sa.String(length=20), nullable=False),
        sa.Column("cible_id", sa.Integer(), nullable=True),
        sa.Column("version_cible", sa.Integer(), nullable=True),
        sa.Column(
            "donnees",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("empreinte", sa.String(length=64), nullable=False),
        sa.Column("statut", sa.String(length=20), nullable=False),
        sa.Column("motif", sa.Text(), nullable=False),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("traite_le", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resultat_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("entite IN ('source','compte','contenu','tag')", name="ck_contribution_entite"),
        sa.CheckConstraint("operation IN ('ajout','modification')", name="ck_contribution_operation"),
        sa.CheckConstraint(
            "statut IN ('en_attente','validee','refusee','fusionnee')", name="ck_contribution_statut"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_contributions_empreinte"), "contributions", ["empreinte"], unique=False)
    op.create_index(op.f("ix_contributions_statut"), "contributions", ["statut"], unique=False)
    op.create_index(
        "uq_contribution_attente",
        "contributions",
        ["empreinte"],
        unique=True,
        postgresql_where=sa.text("statut = 'en_attente'"),
        sqlite_where=sa.text("statut = 'en_attente'"),
    )
    op.create_table(
        "defis",
        sa.Column("jeton", sa.String(length=64), nullable=False),
        sa.Column("reponse_hachee", sa.String(length=64), nullable=False),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("jeton"),
    )
    op.create_index(op.f("ix_defis_cree_le"), "defis", ["cree_le"], unique=False)
    op.create_table(
        "plateformes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nom", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nom"),
    )
    op.create_table(
        "quotas",
        sa.Column("nom", sa.String(length=40), nullable=False),
        sa.Column("debut", sa.DateTime(timezone=True), nullable=False),
        sa.Column("nombre", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("nom"),
    )
    op.create_table(
        "tags",
        sa.Column("nom", sa.String(length=150), nullable=False),
        sa.Column("cle", sa.String(length=150), nullable=False),
        sa.Column("nature", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modifie_le", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "nature IN ('thematique','discours','qualification','categorie','mot_cle')", name="ck_tag_nature"
        ),
        sa.CheckConstraint("parent_id IS NULL OR parent_id != id", name="ck_tag_parent"),
        sa.ForeignKeyConstraint(["parent_id"], ["tags.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cle", "nature", name="uq_tag_cle_nature"),
    )
    op.create_index(op.f("ix_tags_parent_id"), "tags", ["parent_id"], unique=False)
    op.create_table(
        "historique",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contribution_id", sa.Integer(), nullable=True),
        sa.Column("entite", sa.String(length=20), nullable=False),
        sa.Column("entite_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column(
            "avant",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "apres",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.Column("motif", sa.Text(), nullable=False),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["contribution_id"], ["contributions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_historique_contribution_id"), "historique", ["contribution_id"], unique=False)
    op.create_index(op.f("ix_historique_entite_id"), "historique", ["entite_id"], unique=False)
    op.create_table(
        "sources",
        sa.Column("nom", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("url_canonique", sa.String(length=2048), nullable=False),
        sa.Column("pays", sa.String(length=100), nullable=False),
        sa.Column("langue", sa.String(length=100), nullable=False),
        sa.Column("plateforme_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modifie_le", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plateforme_id"], ["plateformes.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url_canonique"),
    )
    op.create_index(op.f("ix_sources_langue"), "sources", ["langue"], unique=False)
    op.create_index(op.f("ix_sources_nom"), "sources", ["nom"], unique=False)
    op.create_index(op.f("ix_sources_pays"), "sources", ["pays"], unique=False)
    op.create_index(op.f("ix_sources_plateforme_id"), "sources", ["plateforme_id"], unique=False)
    op.create_table(
        "comptes",
        sa.Column("plateforme_id", sa.Integer(), nullable=False),
        sa.Column("pseudonyme", sa.String(length=300), nullable=False),
        sa.Column("identifiant", sa.String(length=300), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("url_canonique", sa.String(length=2048), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modifie_le", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plateforme_id"], ["plateformes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url_canonique"),
    )
    op.create_index(op.f("ix_comptes_plateforme_id"), "comptes", ["plateforme_id"], unique=False)
    op.create_index(op.f("ix_comptes_pseudonyme"), "comptes", ["pseudonyme"], unique=False)
    op.create_index(op.f("ix_comptes_source_id"), "comptes", ["source_id"], unique=False)
    op.create_table(
        "source_tags",
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("source_id", "tag_id"),
    )
    op.create_table(
        "contenus",
        sa.Column("titre", sa.String(length=300), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("url_canonique", sa.String(length=2048), nullable=False),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("type_media", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("compte_id", sa.Integer(), nullable=True),
        sa.Column("plateforme_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modifie_le", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "type_media IN ('video','article','publication','podcast','audio','pdf','autre')", name="ck_media"
        ),
        sa.ForeignKeyConstraint(["compte_id"], ["comptes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["plateforme_id"], ["plateformes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url_canonique"),
    )
    op.create_index(op.f("ix_contenus_compte_id"), "contenus", ["compte_id"], unique=False)
    op.create_index(op.f("ix_contenus_date"), "contenus", ["date"], unique=False)
    op.create_index(op.f("ix_contenus_plateforme_id"), "contenus", ["plateforme_id"], unique=False)
    op.create_index(op.f("ix_contenus_source_id"), "contenus", ["source_id"], unique=False)
    op.create_index(op.f("ix_contenus_titre"), "contenus", ["titre"], unique=False)
    op.create_index(op.f("ix_contenus_type_media"), "contenus", ["type_media"], unique=False)
    op.create_table(
        "contenu_tags",
        sa.Column("contenu_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["contenu_id"], ["contenus.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("contenu_id", "tag_id"),
    )
    op.create_table(
        "references",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("titre", sa.String(length=500), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("type_reference", sa.String(length=40), nullable=False),
        sa.Column("citation", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("compte_id", sa.Integer(), nullable=True),
        sa.Column("contenu_id", sa.Integer(), nullable=True),
        sa.Column("tag_id", sa.Integer(), nullable=True),
        sa.Column("qualification_tag_id", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "(CASE WHEN source_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN compte_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN contenu_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN tag_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_reference_proprietaire",
        ),
        sa.ForeignKeyConstraint(["compte_id"], ["comptes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contenu_id"], ["contenus.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["qualification_tag_id"], ["tags.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_references_compte_id"), "references", ["compte_id"], unique=False)
    op.create_index(op.f("ix_references_contenu_id"), "references", ["contenu_id"], unique=False)
    op.create_index(
        op.f("ix_references_qualification_tag_id"), "references", ["qualification_tag_id"], unique=False
    )
    op.create_index(op.f("ix_references_source_id"), "references", ["source_id"], unique=False)
    op.create_index(op.f("ix_references_tag_id"), "references", ["tag_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_references_tag_id"), table_name="references")
    op.drop_index(op.f("ix_references_source_id"), table_name="references")
    op.drop_index(op.f("ix_references_qualification_tag_id"), table_name="references")
    op.drop_index(op.f("ix_references_contenu_id"), table_name="references")
    op.drop_index(op.f("ix_references_compte_id"), table_name="references")
    op.drop_table("references")
    op.drop_table("contenu_tags")
    op.drop_index(op.f("ix_contenus_type_media"), table_name="contenus")
    op.drop_index(op.f("ix_contenus_titre"), table_name="contenus")
    op.drop_index(op.f("ix_contenus_source_id"), table_name="contenus")
    op.drop_index(op.f("ix_contenus_plateforme_id"), table_name="contenus")
    op.drop_index(op.f("ix_contenus_date"), table_name="contenus")
    op.drop_index(op.f("ix_contenus_compte_id"), table_name="contenus")
    op.drop_table("contenus")
    op.drop_table("source_tags")
    op.drop_index(op.f("ix_comptes_source_id"), table_name="comptes")
    op.drop_index(op.f("ix_comptes_pseudonyme"), table_name="comptes")
    op.drop_index(op.f("ix_comptes_plateforme_id"), table_name="comptes")
    op.drop_table("comptes")
    op.drop_index(op.f("ix_sources_plateforme_id"), table_name="sources")
    op.drop_index(op.f("ix_sources_pays"), table_name="sources")
    op.drop_index(op.f("ix_sources_nom"), table_name="sources")
    op.drop_index(op.f("ix_sources_langue"), table_name="sources")
    op.drop_table("sources")
    op.drop_index(op.f("ix_historique_entite_id"), table_name="historique")
    op.drop_index(op.f("ix_historique_contribution_id"), table_name="historique")
    op.drop_table("historique")
    op.drop_index(op.f("ix_tags_parent_id"), table_name="tags")
    op.drop_table("tags")
    op.drop_table("quotas")
    op.drop_table("plateformes")
    op.drop_index(op.f("ix_defis_cree_le"), table_name="defis")
    op.drop_table("defis")
    op.drop_index(
        "uq_contribution_attente",
        table_name="contributions",
        postgresql_where=sa.text("statut = 'en_attente'"),
        sqlite_where=sa.text("statut = 'en_attente'"),
    )
    op.drop_index(op.f("ix_contributions_statut"), table_name="contributions")
    op.drop_index(op.f("ix_contributions_empreinte"), table_name="contributions")
    op.drop_table("contributions")
