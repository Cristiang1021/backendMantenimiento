from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

# Revisión ID y anterior
revision = '13250e9fb7b3'
down_revision = '6a2a15edf58b'
branch_labels = None
depends_on = None

# Define el ENUM para tipo_notificacion
tipo_notificacion_enum = ENUM("correo", "whatsapp", "in-app", name="tipo_notificacion", create_type=False)
estado_notificacion_enum = ENUM("pendiente", "enviado", "fallido", name="estado_notificacion", create_type=False)

def upgrade():
    # Crear los tipos ENUM antes de modificar la tabla
    tipo_notificacion_enum.create(op.get_bind(), checkfirst=True)
    estado_notificacion_enum.create(op.get_bind(), checkfirst=True)

    # Modificar la tabla notificaciones
    op.create_table(
        'notificaciones',
        sa.Column('id_notificacion', sa.Integer(), primary_key=True),
        sa.Column('id_usuario', sa.Integer(), sa.ForeignKey('usuarios.id_usuario'), nullable=True),
        sa.Column('id_mantenimiento', sa.Integer(), sa.ForeignKey('mantenimientos.id_mantenimiento'), nullable=True),
        sa.Column('tipo', tipo_notificacion_enum, nullable=False),
        sa.Column('mensaje', sa.Text(), nullable=True),
        sa.Column('estado_envio', estado_notificacion_enum, nullable=False, server_default="pendiente"),
        sa.Column('fecha_envio', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    # Eliminar la tabla notificaciones
    op.drop_table('notificaciones')

    # Eliminar los tipos ENUM
    tipo_notificacion_enum.drop(op.get_bind(), checkfirst=True)
    estado_notificacion_enum.drop(op.get_bind(), checkfirst=True)
