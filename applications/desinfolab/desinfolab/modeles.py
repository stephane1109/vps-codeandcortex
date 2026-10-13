"""Les tables documentaires ne contiennent que les fiches validées."""

from datetime import datetime, timezone
from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def maintenant():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


DOCUMENT = JSON().with_variant(JSONB(), "postgresql")
source_tags = Table(
    "source_tags",
    Base.metadata,
    Column("source_id", ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="RESTRICT"), primary_key=True),
)
contenu_tags = Table(
    "contenu_tags",
    Base.metadata,
    Column("contenu_id", ForeignKey("contenus.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="RESTRICT"), primary_key=True),
)


class Fiche:
    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(default=1)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)
    modifie_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=maintenant, onupdate=maintenant
    )


class Plateforme(Base):
    __tablename__ = "plateformes"
    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(100), unique=True)


class Tag(Fiche, Base):
    __tablename__ = "tags"
    nom: Mapped[str] = mapped_column(String(150))
    cle: Mapped[str] = mapped_column(String(150))
    nature: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text, default="")
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("tags.id", ondelete="RESTRICT"), index=True)
    __table_args__ = (
        UniqueConstraint("cle", "nature", name="uq_tag_cle_nature"),
        CheckConstraint("parent_id IS NULL OR parent_id != id", name="ck_tag_parent"),
        CheckConstraint(
            "nature IN ('thematique','discours','qualification','categorie','mot_cle')", name="ck_tag_nature"
        ),
    )


class Source(Fiche, Base):
    __tablename__ = "sources"
    nom: Mapped[str] = mapped_column(String(300), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(2048))
    url_canonique: Mapped[str] = mapped_column(String(2048), unique=True)
    pays: Mapped[str] = mapped_column(String(100), default="", index=True)
    langue: Mapped[str] = mapped_column(String(100), default="", index=True)
    plateforme_id: Mapped[int] = mapped_column(ForeignKey("plateformes.id", ondelete="RESTRICT"), index=True)
    plateforme: Mapped[Plateforme] = relationship(lazy="selectin")
    tags: Mapped[list[Tag]] = relationship(secondary=source_tags, lazy="selectin")
    comptes: Mapped[list["Compte"]] = relationship(back_populates="source")
    contenus: Mapped[list["Contenu"]] = relationship(back_populates="source")


class Compte(Fiche, Base):
    __tablename__ = "comptes"
    plateforme_id: Mapped[int] = mapped_column(ForeignKey("plateformes.id", ondelete="RESTRICT"), index=True)
    pseudonyme: Mapped[str] = mapped_column(String(300), index=True)
    identifiant: Mapped[str] = mapped_column(String(300), default="")
    url: Mapped[str] = mapped_column(String(2048))
    url_canonique: Mapped[str] = mapped_column(String(2048), unique=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="RESTRICT"), index=True)
    source: Mapped[Source] = relationship(back_populates="comptes")
    plateforme: Mapped[Plateforme] = relationship(lazy="selectin")
    contenus: Mapped[list["Contenu"]] = relationship(back_populates="compte")


class Contenu(Fiche, Base):
    __tablename__ = "contenus"
    titre: Mapped[str] = mapped_column(String(300), index=True)
    url: Mapped[str] = mapped_column(String(2048))
    url_canonique: Mapped[str] = mapped_column(String(2048), unique=True)
    date: Mapped[datetime | None] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    type_media: Mapped[str] = mapped_column(String(40), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="RESTRICT"), index=True)
    compte_id: Mapped[int | None] = mapped_column(ForeignKey("comptes.id", ondelete="RESTRICT"), index=True)
    plateforme_id: Mapped[int] = mapped_column(ForeignKey("plateformes.id", ondelete="RESTRICT"), index=True)
    source: Mapped[Source] = relationship(back_populates="contenus")
    compte: Mapped[Compte | None] = relationship(back_populates="contenus")
    plateforme: Mapped[Plateforme] = relationship(lazy="selectin")
    tags: Mapped[list[Tag]] = relationship(secondary=contenu_tags, lazy="selectin")
    __table_args__ = (
        CheckConstraint(
            "type_media IN ('video','article','publication','podcast','audio','pdf','autre')", name="ck_media"
        ),
    )


class Reference(Base):
    __tablename__ = "references"
    id: Mapped[int] = mapped_column(primary_key=True)
    titre: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(2048))
    type_reference: Mapped[str] = mapped_column(String(40))
    citation: Mapped[str] = mapped_column(Text, default="")
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    compte_id: Mapped[int | None] = mapped_column(ForeignKey("comptes.id", ondelete="CASCADE"), index=True)
    contenu_id: Mapped[int | None] = mapped_column(ForeignKey("contenus.id", ondelete="CASCADE"), index=True)
    tag_id: Mapped[int | None] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), index=True)
    qualification_tag_id: Mapped[int | None] = mapped_column(
        ForeignKey("tags.id", ondelete="RESTRICT"), index=True
    )
    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN source_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN compte_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN contenu_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN tag_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_reference_proprietaire",
        ),
    )


class Contribution(Base):
    __tablename__ = "contributions"
    id: Mapped[int] = mapped_column(primary_key=True)
    entite: Mapped[str] = mapped_column(String(20))
    operation: Mapped[str] = mapped_column(String(20))
    cible_id: Mapped[int | None] = mapped_column(Integer)
    version_cible: Mapped[int | None] = mapped_column(Integer)
    donnees: Mapped[dict] = mapped_column(DOCUMENT)
    empreinte: Mapped[str] = mapped_column(String(64), index=True)
    statut: Mapped[str] = mapped_column(String(20), default="en_attente", index=True)
    motif: Mapped[str] = mapped_column(Text, default="")
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)
    traite_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resultat_id: Mapped[int | None] = mapped_column(Integer)
    __table_args__ = (
        CheckConstraint("entite IN ('source','compte','contenu','tag')", name="ck_contribution_entite"),
        CheckConstraint("operation IN ('ajout','modification')", name="ck_contribution_operation"),
        CheckConstraint(
            "statut IN ('en_attente','validee','refusee','fusionnee')", name="ck_contribution_statut"
        ),
        Index(
            "uq_contribution_attente",
            "empreinte",
            unique=True,
            postgresql_where=(statut == "en_attente"),
            sqlite_where=(statut == "en_attente"),
        ),
    )


class Historique(Base):
    __tablename__ = "historique"
    id: Mapped[int] = mapped_column(primary_key=True)
    contribution_id: Mapped[int | None] = mapped_column(
        ForeignKey("contributions.id", ondelete="RESTRICT"), index=True
    )
    entite: Mapped[str] = mapped_column(String(20))
    entite_id: Mapped[int | None] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(30))
    avant: Mapped[dict | None] = mapped_column(DOCUMENT)
    apres: Mapped[dict | None] = mapped_column(DOCUMENT)
    motif: Mapped[str] = mapped_column(Text, default="")
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)


class Quota(Base):
    """Compteurs globaux ; aucune IP, identité ou empreinte de navigateur."""

    __tablename__ = "quotas"
    nom: Mapped[str] = mapped_column(String(40), primary_key=True)
    debut: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)
    nombre: Mapped[int] = mapped_column(default=0)


class Defi(Base):
    """Jeton aléatoire à usage unique, sans lien avec une contribution."""

    __tablename__ = "defis"
    jeton: Mapped[str] = mapped_column(String(64), primary_key=True)
    reponse_hachee: Mapped[str] = mapped_column(String(64))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant, index=True)
