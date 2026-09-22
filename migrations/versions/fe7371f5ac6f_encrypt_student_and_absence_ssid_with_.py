"""encrypt student and absence ssid with blind index

Revision ID: fe7371f5ac6f
Revises: f44af3eb58f7
Create Date: 2026-09-22 10:09:22.580366

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'fe7371f5ac6f'
down_revision = 'f44af3eb58f7'
branch_labels = None
depends_on = None


def _encrypt_ssid_column(conn, table_name, key, secret_key):
    """Encrypt every distinct plaintext ssid value once (not once per row — a table like
    Absence has many rows per real SSID), then apply the (enc, hash) pair to every row
    sharing that value via one bulk executemany update instead of one UPDATE per row."""
    from application.utils import encrypt_mail_password, hash_ssid

    table = sa.table(table_name,
        sa.column('id', sa.Integer),
        sa.column('ssid', sa.String),
        sa.column('ssid_enc', sa.Text),
        sa.column('ssid_hash', sa.String),
    )
    rows = conn.execute(sa.select(table.c.id, table.c.ssid)).fetchall()

    value_cache = {}  # plaintext ssid -> (ssid_enc, ssid_hash)
    updates = []
    for row in rows:
        value = row.ssid
        if not value:
            continue
        if value not in value_cache:
            value_cache[value] = (encrypt_mail_password(value, key), hash_ssid(value, secret_key))
        enc, h = value_cache[value]
        updates.append({'_id': row.id, 'ssid_enc': enc, 'ssid_hash': h})

    if updates:
        conn.execute(
            table.update().where(table.c.id == sa.bindparam('_id')),
            updates,
        )


def upgrade():
    # Add the new encrypted + blind-index columns, encrypt/hash existing plaintext into
    # them, then drop the old plaintext columns — same three-step approach as the other
    # encryption migrations, so no plaintext PII is ever silently discarded unencrypted.
    with op.batch_alter_table('absence', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ssid_enc', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('ssid_hash', sa.String(length=64), nullable=True))

    with op.batch_alter_table('student', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ssid_enc', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('ssid_hash', sa.String(length=64), nullable=True))

    from flask import current_app
    conn = op.get_bind()
    key = current_app.config['DATA_ENCRYPTION_KEY']
    secret_key = current_app.config['SECRET_KEY']
    _encrypt_ssid_column(conn, 'student', key, secret_key)
    _encrypt_ssid_column(conn, 'absence', key, secret_key)

    with op.batch_alter_table('absence', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_absence_ssid'))
        batch_op.drop_index(batch_op.f('ix_absence_schoolyr_ssid'))
        batch_op.create_index('ix_absence_schoolyr_ssid', ['school_yr', 'ssid_hash'], unique=False)
        batch_op.create_index(batch_op.f('ix_absence_ssid_hash'), ['ssid_hash'], unique=False)
        batch_op.drop_column('ssid')

    with op.batch_alter_table('student', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_student_ssid'))
        batch_op.create_index(batch_op.f('ix_student_ssid_hash'), ['ssid_hash'], unique=False)
        batch_op.drop_column('ssid')


def downgrade():
    # Note: this does not decrypt data back into the restored plaintext columns — a
    # downgrade after this migration loses the ssid values, not just their encryption.
    with op.batch_alter_table('student', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ssid', mysql.VARCHAR(length=20), nullable=True))
        batch_op.drop_index(batch_op.f('ix_student_ssid_hash'))
        batch_op.create_index(batch_op.f('ix_student_ssid'), ['ssid'], unique=False)
        batch_op.drop_column('ssid_hash')
        batch_op.drop_column('ssid_enc')

    with op.batch_alter_table('absence', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ssid', mysql.VARCHAR(length=20), nullable=True))
        batch_op.drop_index(batch_op.f('ix_absence_ssid_hash'))
        batch_op.drop_index('ix_absence_schoolyr_ssid')
        batch_op.create_index(batch_op.f('ix_absence_schoolyr_ssid'), ['school_yr', 'ssid'], unique=False)
        batch_op.create_index(batch_op.f('ix_absence_ssid'), ['ssid'], unique=False)
        batch_op.drop_column('ssid_hash')
        batch_op.drop_column('ssid_enc')
