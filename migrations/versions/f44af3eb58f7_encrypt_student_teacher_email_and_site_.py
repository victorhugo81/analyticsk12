"""encrypt student teacher email and site principal contact

Revision ID: f44af3eb58f7
Revises: 4043737eaa17
Create Date: 2026-09-22 09:22:44.113494

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'f44af3eb58f7'
down_revision = '4043737eaa17'
branch_labels = None
depends_on = None


def _encrypt_column(conn, table_name, id_col, plain_col, enc_col, key):
    from application.utils import encrypt_mail_password

    table = sa.table(table_name,
        sa.column(id_col, sa.Integer),
        sa.column(plain_col, sa.String),
        sa.column(enc_col, sa.Text),
    )
    rows = conn.execute(sa.select(getattr(table.c, id_col), getattr(table.c, plain_col))).fetchall()
    for row in rows:
        value = row[1]
        if not value:
            continue
        conn.execute(
            table.update().where(getattr(table.c, id_col) == row[0])
                 .values(**{enc_col: encrypt_mail_password(value, key)})
        )


def upgrade():
    # Add the new encrypted columns, encrypt existing plaintext into them, then drop the
    # old plaintext columns — same three-step approach as the Parent email/phone migration,
    # so no plaintext PII is ever silently discarded unencrypted.
    with op.batch_alter_table('site', schema=None) as batch_op:
        batch_op.add_column(sa.Column('principal_email_enc', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('principal_phone_enc', sa.Text(), nullable=True))

    with op.batch_alter_table('student', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_enc', sa.Text(), nullable=True))

    with op.batch_alter_table('teacher', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_enc', sa.Text(), nullable=True))

    from flask import current_app
    conn = op.get_bind()
    key = current_app.config['DATA_ENCRYPTION_KEY']
    _encrypt_column(conn, 'site',    'id', 'principal_email', 'principal_email_enc', key)
    _encrypt_column(conn, 'site',    'id', 'principal_phone', 'principal_phone_enc', key)
    _encrypt_column(conn, 'student', 'id', 'email',           'email_enc',           key)
    _encrypt_column(conn, 'teacher', 'id', 'email',           'email_enc',           key)

    with op.batch_alter_table('site', schema=None) as batch_op:
        batch_op.drop_column('principal_email')
        batch_op.drop_column('principal_phone')

    with op.batch_alter_table('student', schema=None) as batch_op:
        batch_op.drop_column('email')

    with op.batch_alter_table('teacher', schema=None) as batch_op:
        batch_op.drop_column('email')


def downgrade():
    # Note: this does not decrypt data back into the restored plaintext columns — a
    # downgrade after this migration loses the email/phone values, not just their encryption.
    with op.batch_alter_table('teacher', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email', mysql.VARCHAR(length=120), nullable=True))
        batch_op.drop_column('email_enc')

    with op.batch_alter_table('student', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email', mysql.VARCHAR(length=120), nullable=True))
        batch_op.drop_column('email_enc')

    with op.batch_alter_table('site', schema=None) as batch_op:
        batch_op.add_column(sa.Column('principal_phone', mysql.VARCHAR(length=20), nullable=True))
        batch_op.add_column(sa.Column('principal_email', mysql.VARCHAR(length=120), nullable=True))
        batch_op.drop_column('principal_phone_enc')
        batch_op.drop_column('principal_email_enc')
