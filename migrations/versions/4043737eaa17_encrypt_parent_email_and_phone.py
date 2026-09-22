"""encrypt parent email and phone

Revision ID: 4043737eaa17
Revises: d94329389d8b
Create Date: 2026-09-22 08:46:40.863140

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '4043737eaa17'
down_revision = 'd94329389d8b'
branch_labels = None
depends_on = None


def upgrade():
    # Add the new encrypted columns first, then encrypt any existing plaintext data into
    # them (same cryptography.fernet scheme as User.email, keyed by DATA_ENCRYPTION_KEY),
    # then drop the old plaintext columns. Splitting into three steps (rather than a single
    # add+drop) so no plaintext PII is ever silently discarded unencrypted.
    with op.batch_alter_table('parent', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_enc', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('phone_enc', sa.Text(), nullable=True))

    from flask import current_app
    from application.utils import encrypt_mail_password

    conn = op.get_bind()
    key = current_app.config['DATA_ENCRYPTION_KEY']
    parent_table = sa.table('parent',
        sa.column('id', sa.Integer),
        sa.column('email', sa.String),
        sa.column('phone', sa.String),
        sa.column('email_enc', sa.Text),
        sa.column('phone_enc', sa.Text),
    )
    rows = conn.execute(sa.select(parent_table.c.id, parent_table.c.email, parent_table.c.phone)).fetchall()
    for row in rows:
        if not row.email and not row.phone:
            continue
        conn.execute(
            parent_table.update().where(parent_table.c.id == row.id).values(
                email_enc=encrypt_mail_password(row.email, key) if row.email else None,
                phone_enc=encrypt_mail_password(row.phone, key) if row.phone else None,
            )
        )

    with op.batch_alter_table('parent', schema=None) as batch_op:
        batch_op.drop_column('email')
        batch_op.drop_column('phone')


def downgrade():
    # Note: this does not decrypt data back into the restored plaintext columns — a
    # downgrade after this migration loses the email/phone values, not just their encryption.
    with op.batch_alter_table('parent', schema=None) as batch_op:
        batch_op.add_column(sa.Column('phone', mysql.VARCHAR(length=20), nullable=True))
        batch_op.add_column(sa.Column('email', mysql.VARCHAR(length=120), nullable=True))
        batch_op.drop_column('phone_enc')
        batch_op.drop_column('email_enc')
