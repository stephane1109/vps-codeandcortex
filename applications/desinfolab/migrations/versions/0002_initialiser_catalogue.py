"""Plateformes initiales et compteurs sans identifiants de visiteurs."""

from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    plateformes = [
        "YouTube",
        "TikTok",
        "Facebook",
        "Instagram",
        "X",
        "Telegram",
        "Rumble",
        "Odysee",
        "Site Internet",
        "Blog",
        "Forum",
        "Podcast",
        "Radio",
        "Document PDF",
    ]
    for nom in plateformes:
        op.execute(
            sa.text("INSERT INTO plateformes (nom) VALUES ('" + nom + "') ON CONFLICT (nom) DO NOTHING")
        )
    op.bulk_insert(
        sa.table(
            "quotas",
            sa.column("nom", sa.String),
            sa.column("debut", sa.DateTime(timezone=True)),
            sa.column("nombre", sa.Integer),
        ),
        [
            {"nom": nom, "debut": datetime(2026, 1, 1, tzinfo=timezone.utc), "nombre": 0}
            for nom in ["connexion", "defis", "soumissions", "moderation"]
        ],
    )


def downgrade():
    op.execute("DELETE FROM quotas")
    # Les plateformes peuvent être référencées par des fiches : elles sont conservées jusqu'à 0001 -> base.
