from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

from sqlalchemy.dialects.postgresql import ENUM

from app import db

# Modelo de Titulos
class Titulo(db.Model):
    __tablename__ = 'titulos'
    id_titulo = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)  # Ej: Dr., Sr., Sra., Ing., etc.

    # Relación con la tabla usuarios
    usuarios = db.relationship('Usuario', backref='titulo', lazy=True)

# Modelo de Usuarios
class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id_usuario = db.Column(db.Integer, primary_key=True)
    nombres = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(50), nullable=False)
    cedula = db.Column(db.String(10), unique=True, nullable=False)
    email = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)  # Contraseña hasheada
    genero = db.Column(db.String(10), nullable=False)
    telefono = db.Column(db.String(15), nullable=False)  # Número de WhatsApp
    foto = db.Column(db.LargeBinary, nullable=True)  # Foto como bytes
    id_rol = db.Column(db.Integer, db.ForeignKey('roles.id_rol'), nullable=False)  # Relación con la tabla de roles
    estado_usuario = db.Column(db.String(50), nullable=False, default='inactivo')  # Estado del usuario
    fecha_registro = db.Column(db.DateTime, default=db.func.now())
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relación con la tabla Titulos
    id_titulo = db.Column(db.Integer, db.ForeignKey('titulos.id_titulo'),nullable=True)  # Relación con la tabla de títulos

    mantenimientos = db.relationship('Mantenimiento', backref='usuario', lazy=True)


# Modelo de Maquinaria
class Maquinaria(db.Model):
    __tablename__ = 'maquinaria'
    id_maquinaria = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    numero_serie = db.Column(db.String(255), nullable=False, unique=True)
    modelo = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.String(255), nullable=True)
    m_imagen = db.Column(db.LargeBinary, nullable=True)  # Imagen de la maquinaria como bytes
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    mantenimientos = db.relationship('Mantenimiento', backref='maquinaria', lazy=True)


# Tabla intermedia para la relación muchos a muchos entre Herramienta y Mantenimiento
mantenimiento_herramienta = db.Table('mantenimiento_herramienta',
    db.Column('id_mantenimiento', db.Integer, db.ForeignKey('mantenimientos.id_mantenimiento'), primary_key=True),
    db.Column('id_herramienta', db.Integer, db.ForeignKey('herramientas.id_herramienta'), primary_key=True),
    db.Column('cantidad_usada', db.Integer, nullable=False),  # Cantidad de herramientas usadas en el mantenimiento
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
)


# Modelo de Mantenimiento
class Mantenimiento(db.Model):
    __tablename__ = 'mantenimientos'
    id_mantenimiento = db.Column(db.Integer, primary_key=True)
    id_maquinaria = db.Column(db.Integer, db.ForeignKey('maquinaria.id_maquinaria'), nullable=False)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=False)  # Usuario operario
    tipo_mantenimiento = db.Column(db.String(100), nullable=False)
    fecha_mantenimiento = db.Column(db.DateTime, nullable=False)  # Fecha del próximo mantenimiento
    proxima_fecha = db.Column(db.DateTime, nullable=False)  # Fecha calculada automáticamente
    frecuencia = db.Column(db.Integer, nullable=False)  # Frecuencia en días
    descripcion = db.Column(db.Text, nullable=True)  # Actividades o detalles del mantenimiento
    tiempo_requerido = db.Column(db.Integer, nullable=False)  # Tiempo requerido en horas
    estado_actual = db.Column(db.String(50), nullable=False, default="pendiente")  # Estado actual del mantenimiento
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relación con el historial de estados
    historial_estados = db.relationship('HistorialEstado', backref='mantenimiento', lazy=True)

    # Relación muchos a muchos con herramientas
    herramientas = db.relationship('Herramienta', secondary=mantenimiento_herramienta, backref=db.backref('mantenimientos', lazy=True))

    def calcular_proxima_fecha(self):
        """Calcula la próxima fecha de mantenimiento basada en la frecuencia."""
        self.proxima_fecha = self.fecha_mantenimiento + timedelta(days=self.frecuencia)

    def enviar_notificacion(self):
        """Envía una notificación al operario si el mantenimiento está cercano."""
        dias_restantes = (self.fecha_mantenimiento - datetime.now()).days
        if dias_restantes <= 2:  # Puedes cambiar el umbral dinámicamente desde el admin
            # Aquí se debería implementar la lógica de envío de notificaciones
            pass



# Modelo de HistorialEstado (Combina estado actual e historial de estados)
class HistorialEstado(db.Model):
    __tablename__ = 'historial_estados'
    id_historial_estado = db.Column(db.Integer, primary_key=True)
    id_mantenimiento = db.Column(db.Integer, db.ForeignKey('mantenimientos.id_mantenimiento'), nullable=False)
    estado = db.Column(db.String(50), nullable=False)
    observacion = db.Column(db.String(255), nullable=True)
    fecha_estado = db.Column(db.DateTime, default=db.func.now())
    es_estado_actual = db.Column(db.Boolean, nullable=False, default=False)  # Indica si es el estado actual
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# Modelo de Herramientas
class Herramienta(db.Model):
    __tablename__ = 'herramientas'
    id_herramienta = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    descripcion = db.Column(db.String(255), nullable=True)
    cantidad = db.Column(db.Integer, nullable=False)
    h_imagen = db.Column(db.LargeBinary, nullable=True)  # Imagen de la herramienta como bytes
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# Modelo de Accesos
class Acceso(db.Model):
    __tablename__ = 'accesos'
    id_acceso = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=False)
    acceso_boole = db.Column(db.Boolean, nullable=False)
    fecha_acceso = db.Column(db.DateTime, default=db.func.now())
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# Modelo de Notificaciones
class Notificacion(db.Model):
    __tablename__ = 'notificaciones'
    id_notificacion = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=True)  # Usuario destinatario
    id_mantenimiento = db.Column(db.Integer, db.ForeignKey('mantenimientos.id_mantenimiento'), nullable=True)
    tipo = db.Column(ENUM("correo", "whatsapp", "in-app", name="tipo_notificacion"), nullable=False)  # "correo", "whatsapp", "in-app"
    mensaje = db.Column(db.Text, nullable=True)  # Mensaje asociado a la notificación
    estado_envio = db.Column(ENUM("pendiente", "enviado", "fallido", name="estado_notificacion"), nullable=False, default="pendiente")  # "pendiente", "enviado", "fallido"
    fecha_envio = db.Column(db.DateTime, default=None)  # Fecha de envío
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    usuario = db.relationship('Usuario', backref='notificaciones', lazy=True)  # Relación con el usuario
    mantenimiento = db.relationship('Mantenimiento', backref='notificaciones', lazy=True)


# Modelo de Roles
class Rol(db.Model):
    __tablename__ = 'roles'
    id_rol = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relación uno a muchos con Usuario
    usuarios = db.relationship('Usuario', backref='rol', lazy=True)


class Contacto(db.Model):
    __tablename__ = 'contactos'
    id_contacto = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    direccion = db.Column(db.String(255), nullable=False)
    convencional = db.Column(db.String(15), nullable=True)  # Teléfono convencional
    celular = db.Column(db.String(15), nullable=False)  # Número de celular
    email = db.Column(db.String(100), nullable=False)
    parentesco = db.Column(db.String(50), nullable=False)  # Relación con el usuario (amigo, familiar, etc.)

    usuario = db.relationship('Usuario', backref='contactos', lazy=True)

# Configuracion Notificaciones
class ConfiguracionNotificaciones(db.Model):
    __tablename__ = 'configuraciones_notificaciones'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), nullable=False)  # Correo electrónico remitente
    smtp_server = db.Column(db.String(100), nullable=False)  # Servidor SMTP
    smtp_port = db.Column(db.Integer, nullable=False)  # Puerto SMTP
    smtp_password = db.Column(db.String(255), nullable=False)  # Contraseña o token SMTP
    created_at = db.Column(db.DateTime, default=db.func.now())



