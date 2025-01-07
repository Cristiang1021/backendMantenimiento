import base64
import io
import smtplib
import matplotlib
matplotlib.use('Agg')  # Establecer el backend a 'Agg' para evitar problemas de GUI

import traceback
from datetime import datetime, timedelta
from email.mime.text import MIMEText

from flask import jsonify, request, send_file, make_response, render_template
import pdfkit
from sqlalchemy import func, or_
from sqlalchemy.sql import case
from werkzeug.security import check_password_hash, generate_password_hash
import matplotlib.pyplot as plt

from app import app, db
from app.auth import blacklist
from app.models import Usuario, Rol, Contacto, Herramienta, Maquinaria, Mantenimiento, Acceso, HistorialEstado, Titulo, \
    mantenimiento_herramienta, ConfiguracionNotificaciones, Notificacion
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app import mail  # Importa la instancia de Flask-Mail
from flask_mail import Message  # Importa Message para enviar correos


# Ruta protegida para usuarios autenticados
@app.route('/protected', methods=['GET'])
@jwt_required()  # Protección de la ruta
def protected():
    current_user = get_jwt_identity()  # Obtener la identidad del usuario desde el token JWT
    return jsonify({
        "message": f"Tienes acceso a esta ruta porque estás autenticado como: {current_user['rol']}"
    })


@app.route('/usuarios', methods=['GET'])
@jwt_required()
def obtener_usuarios():
    jti = get_jwt()["jti"]
    if jti in blacklist:
        return jsonify({"mensaje": "Token revocado. No autorizado."}), 401

    # Aquí la lógica de obtener los usuarios
    usuarios = Usuario.query.all()
    resultado = [{
        "id_usuario": usuario.id_usuario,
        "nombres": usuario.nombres,
        "apellidos": usuario.apellidos,
        "cedula": usuario.cedula,
        "telefono": usuario.telefono,
        "email": usuario.email,
        "rol": usuario.rol.nombre,
        "estado_usuario": usuario.estado_usuario
    } for usuario in usuarios]
    return jsonify(resultado), 200



# Eliminar un usuario
@app.route('/usuarios/<int:id_usuario>', methods=['DELETE'])
@jwt_required()
def eliminar_usuario(id_usuario):
    usuario = Usuario.query.get_or_404(id_usuario)
    db.session.delete(usuario)
    db.session.commit()

    return jsonify({"mensaje": "Usuario eliminado con éxito."}), 200


# Activar un usuario
@app.route('/usuarios/<int:id_usuario>/activar', methods=['PUT'])
@jwt_required()
def activar_usuario(id_usuario):
    usuario = Usuario.query.get_or_404(id_usuario)
    usuario.estado_usuario = 'activo'
    db.session.commit()
    return jsonify({"mensaje": "Usuario activado con éxito."}), 200


# Ruta para obtener un usuario por su cédula
@app.route('/usuarios/cedula/<cedula>', methods=['GET'])
@jwt_required()
def obtener_usuario_por_cedula(cedula):
    usuario = Usuario.query.filter_by(cedula=cedula).first_or_404()
    foto_perfil_base64 = base64.b64encode(usuario.foto).decode('utf-8') if usuario.foto else None

    return jsonify({
        "nombres": usuario.nombres,
        "apellidos": usuario.apellidos,
        "cedula": usuario.cedula,
        "telefono": usuario.telefono,
        "email": usuario.email,
        "genero": usuario.genero,
        "rol": usuario.rol.nombre,
        "estado_usuario": usuario.estado_usuario,
        "fecha_registro": usuario.fecha_registro.strftime("%Y-%m-%d"),
        'foto_perfil': foto_perfil_base64
    })


# Ruta para editar un usuario por su cédula
@app.route('/usuarios/cedula/<cedula>', methods=['PUT'])
@jwt_required()
def editar_usuario_por_cedula(cedula):
    usuario = Usuario.query.filter_by(cedula=cedula).first_or_404()
    data = request.form

    usuario.nombres = data.get('nombres', usuario.nombres)
    usuario.apellidos = data.get('apellidos', usuario.apellidos)
    usuario.telefono = data.get('telefono', usuario.telefono)
    usuario.email = data.get('email', usuario.email)
    usuario.genero = data.get('genero', usuario.genero)
    usuario.estado_usuario = data.get('estado_usuario', usuario.estado_usuario)

    # Buscar el rol
    rol = Rol.query.filter_by(nombre=data.get('rol')).first()
    if rol:
        usuario.id_rol = rol.id_rol

    # Actualizar el título del usuario
    id_titulo = data.get('id_titulo', None)
    if id_titulo:
        usuario.id_titulo = id_titulo

    # Actualizar foto si está presente
    if 'foto_perfil' in request.files:
        usuario.foto_perfil = request.files['foto_perfil'].read()

    db.session.commit()
    return jsonify({"mensaje": "Usuario actualizado con éxito."}), 200


# Ruta para agregar contacto a un usuario
@app.route('/usuarios/<cedula>/contacto', methods=['POST'])
@jwt_required()
def agregar_contacto(cedula):
    usuario = Usuario.query.filter_by(cedula=cedula).first_or_404()

    data = request.get_json()

    # Validar que todos los campos necesarios están presentes
    required_fields = ['nombre', 'direccion', 'celular', 'email', 'parentesco']
    for field in required_fields:
        if field not in data or not data.get(field):
            return jsonify({"mensaje": f"El campo {field} es requerido."}), 400

    # Crear un nuevo contacto
    nuevo_contacto = Contacto(
        id_usuario=usuario.id_usuario,
        nombre=data.get('nombre'),
        direccion=data.get('direccion'),
        convencional=data.get('convencional'),
        celular=data.get('celular'),
        email=data.get('email'),
        parentesco=data.get('parentesco')
    )

    db.session.add(nuevo_contacto)
    db.session.commit()

    return jsonify({"mensaje": "Contacto agregado exitosamente."}), 201

####### TITULOS #######
# Obtener todos los títulos
@app.route('/titulos', methods=['GET'])
@jwt_required()
def obtener_titulos():
    titulos = Titulo.query.all()
    titulos_data = [{'id_titulo': t.id_titulo, 'nombre': t.nombre} for t in titulos]
    return jsonify(titulos_data), 200

# Crear un nuevo título
@app.route('/titulo', methods=['POST'])
@jwt_required()
def crear_titulo():
    data = request.get_json()
    if not data or not data.get('nombre'):
        return jsonify({'mensaje': 'El nombre del título es obligatorio'}), 400

    nuevo_titulo = Titulo(nombre=data['nombre'])
    db.session.add(nuevo_titulo)
    db.session.commit()
    return jsonify({'mensaje': 'Título creado exitosamente'}), 201

# Actualizar un título
@app.route('/titulo/<int:id_titulo>', methods=['PUT'])
@jwt_required()
def actualizar_titulo(id_titulo):
    titulo = Titulo.query.get_or_404(id_titulo)
    data = request.get_json()

    if not data or not data.get('nombre'):
        return jsonify({'mensaje': 'El nombre del título es obligatorio'}), 400

    titulo.nombre = data['nombre']
    db.session.commit()
    return jsonify({'mensaje': 'Título actualizado exitosamente'}), 200

# Eliminar un título
@app.route('/titulo/<int:id_titulo>', methods=['DELETE'])
@jwt_required()
def eliminar_titulo(id_titulo):
    titulo = Titulo.query.get_or_404(id_titulo)
    db.session.delete(titulo)
    db.session.commit()
    return jsonify({'mensaje': 'Título eliminado exitosamente'}), 200



################# HERRAMIENTAS #######################
# Obtener todas las herramientas
@app.route('/herramientas', methods=['GET'])
@jwt_required()
def obtener_herramientas():
    herramientas = Herramienta.query.all()
    resultado = [{
        'id_herramienta': herramienta.id_herramienta,
        'nombre': herramienta.nombre,
        'tipo': herramienta.tipo,
        'descripcion': herramienta.descripcion,
        'cantidad': herramienta.cantidad,
        'h_imagen': base64.b64encode(herramienta.h_imagen).decode('utf-8') if herramienta.h_imagen else None
    } for herramienta in herramientas]
    return jsonify(resultado), 200

# Obtener las herramientas asociadas a un mantenimiento específico
@app.route('/mantenimientos/<int:id_mantenimiento>/herramientas', methods=['GET'])
@jwt_required()
def obtener_herramientas_mantenimiento(id_mantenimiento):
    herramientas = db.session.query(mantenimiento_herramienta).filter_by(id_mantenimiento=id_mantenimiento).all()

    resultado = [{
        'id_herramienta': herramienta.id_herramienta,
        'cantidad_usada': herramienta.cantidad_usada,
    } for herramienta in herramientas]

    return jsonify(resultado), 200


# Crear una nueva herramienta
@app.route('/herramientas', methods=['POST'])
@jwt_required()
def crear_herramienta():
    data = request.form
    nueva_herramienta = Herramienta(
        nombre=data['nombre'],
        tipo=data['tipo'],
        descripcion=data.get('descripcion', None),
        cantidad=data['cantidad'],
        h_imagen=request.files['h_imagen'].read() if 'h_imagen' in request.files else None
    )
    db.session.add(nueva_herramienta)
    db.session.commit()
    return jsonify({"mensaje": "Herramienta creada exitosamente"}), 201

# Actualizar herramienta
@app.route('/herramientas/<int:id_herramienta>', methods=['PUT'])
@jwt_required()
def actualizar_herramienta(id_herramienta):
    herramienta = Herramienta.query.get_or_404(id_herramienta)
    data = request.form
    herramienta.nombre = data['nombre']
    herramienta.tipo = data['tipo']
    herramienta.descripcion = data.get('descripcion', herramienta.descripcion)
    herramienta.cantidad = data['cantidad']
    if 'h_imagen' in request.files:
        herramienta.h_imagen = request.files['h_imagen'].read()

    db.session.commit()
    return jsonify({"mensaje": "Herramienta actualizada con éxito"}), 200

# Eliminar herramienta
@app.route('/herramientas/<int:id_herramienta>', methods=['DELETE'])
@jwt_required()
def eliminar_herramienta(id_herramienta):
    herramienta = Herramienta.query.get_or_404(id_herramienta)
    db.session.delete(herramienta)
    db.session.commit()
    return jsonify({"mensaje": "Herramienta eliminada con éxito"}), 200

# Obtener una herramienta específica por ID
@app.route('/herramientas/<int:id_herramienta>', methods=['GET'])
@jwt_required()
def obtener_herramienta(id_herramienta):
    herramienta = Herramienta.query.get(id_herramienta)
    if not herramienta:
        return jsonify({"mensaje": "Herramienta no encontrada"}), 404

    # Convertir la imagen de bytes a base64 para enviarla al frontend
    imagen_base64 = base64.b64encode(herramienta.h_imagen).decode('utf-8') if herramienta.h_imagen else None

    herramienta_data = {
        "id_herramienta": herramienta.id_herramienta,
        "nombre": herramienta.nombre,
        "tipo": herramienta.tipo,
        "descripcion": herramienta.descripcion,
        "cantidad": herramienta.cantidad,
        "h_imagen": imagen_base64  # Imagen en formato base64
    }
    return jsonify(herramienta_data), 200

################# MAQUINARIAS #######################

# Obtener todas las maquinarias
@app.route('/maquinarias', methods=['GET'])
@jwt_required()
def obtener_maquinarias():
    maquinarias = Maquinaria.query.all()
    resultado = [{
        'id_maquinaria': maquina.id_maquinaria,
        'nombre': maquina.nombre,
        'numero_serie': maquina.numero_serie,
        'modelo': maquina.modelo,
        'descripcion': maquina.descripcion,
        # Convertir la imagen en base64 si existe
        'm_imagen': base64.b64encode(maquina.m_imagen).decode('utf-8') if maquina.m_imagen else None
    } for maquina in maquinarias]
    return jsonify(resultado), 200

# Crear una nueva maquinaria
@app.route('/maquinaria', methods=['POST'])
@jwt_required()
def crear_maquinaria():
    data = request.form
    nueva_maquinaria = Maquinaria(
        nombre=data['nombre'],
        numero_serie=data['numero_serie'],
        modelo=data['modelo'],
        descripcion=data.get('descripcion', None),
        m_imagen=request.files['m_imagen'].read() if 'm_imagen' in request.files else None
    )
    db.session.add(nueva_maquinaria)
    db.session.commit()
    return jsonify({"mensaje": "Maquinaria creada exitosamente"}), 201

# Actualizar una maquinaria
@app.route('/maquinaria/<int:id_maquinaria>', methods=['PUT'])
@jwt_required()
def actualizar_maquinaria(id_maquinaria):
    maquina = Maquinaria.query.get_or_404(id_maquinaria)
    data = request.form
    maquina.nombre = data['nombre']
    maquina.numero_serie = data['numero_serie']
    maquina.modelo = data['modelo']
    maquina.descripcion = data.get('descripcion', maquina.descripcion)
    if 'm_imagen' in request.files:
        maquina.m_imagen = request.files['m_imagen'].read()  # Leer la nueva imagen si fue cargada

    db.session.commit()
    return jsonify({"mensaje": "Maquinaria actualizada con éxito"}), 200

# Eliminar una maquinaria
@app.route('/maquinaria/<int:id_maquinaria>', methods=['DELETE'])
@jwt_required()
def eliminar_maquinaria(id_maquinaria):
    maquina = Maquinaria.query.get_or_404(id_maquinaria)
    db.session.delete(maquina)
    db.session.commit()
    return jsonify({"mensaje": "Maquinaria eliminada con éxito"}), 200

# Obtener una maquinaria por su ID
@app.route('/maquinaria/<int:id_maquinaria>', methods=['GET'])
@jwt_required()
def obtener_maquinaria(id_maquinaria):
    maquina = Maquinaria.query.get_or_404(id_maquinaria)
    return jsonify({
        'id_maquinaria': maquina.id_maquinaria,
        'nombre': maquina.nombre,
        'numero_serie': maquina.numero_serie,
        'modelo': maquina.modelo,
        'descripcion': maquina.descripcion,
        # Convertir la imagen de bytes a base64 si existe
        'm_imagen': base64.b64encode(maquina.m_imagen).decode() if maquina.m_imagen else None,
        'created_at': maquina.created_at
    }), 200


################# MANTENIMIENTOS #######################

@app.route('/mantenimientos/<int:id_mantenimiento>/herramientas', methods=['POST'])
@jwt_required()
def agregar_herramientas_mantenimiento(id_mantenimiento):
    mantenimiento = Mantenimiento.query.get_or_404(id_mantenimiento)
    data = request.get_json()

    # Eliminar las herramientas existentes para ese mantenimiento
    db.session.execute(
        mantenimiento_herramienta.delete().where(mantenimiento_herramienta.c.id_mantenimiento == id_mantenimiento))

    # Añadir las nuevas herramientas con su cantidad
    herramientas = data.get("herramientas", [])
    for herramienta in herramientas:
        id_herramienta = herramienta["id_herramienta"]
        cantidad_usada = herramienta["cantidad_usada"]

        db.session.execute(mantenimiento_herramienta.insert().values(
            id_mantenimiento=id_mantenimiento,
            id_herramienta=id_herramienta,
            cantidad_usada=cantidad_usada
        ))

    db.session.commit()

    return jsonify({"mensaje": "Herramientas actualizadas correctamente"}), 200



# Obtener todos los mantenimientos con los nombres de la maquinaria y del operario
@app.route('/mantenimientos', methods=['GET'])
@jwt_required()
def obtener_mantenimientos():
    mantenimientos = Mantenimiento.query.join(Maquinaria, Mantenimiento.id_maquinaria == Maquinaria.id_maquinaria) \
                                        .join(Usuario, Mantenimiento.id_usuario == Usuario.id_usuario) \
                                        .add_columns(Mantenimiento.id_mantenimiento, Mantenimiento.tipo_mantenimiento,
                                                     Mantenimiento.fecha_mantenimiento, Mantenimiento.proxima_fecha,
                                                     Mantenimiento.frecuencia, Mantenimiento.descripcion,
                                                     Mantenimiento.estado_actual, Mantenimiento.tiempo_requerido,
                                                     Maquinaria.nombre.label("nombre_maquinaria"),
                                                     Maquinaria.m_imagen.label("imagen_maquinaria"),
                                                     Usuario.nombres.label("nombre_operario"),
                                                     Usuario.apellidos.label("apellido_operario"),
                                                     Usuario.foto.label("imagen_operario")) \
                                        .all()

    resultado = [{
        'id_mantenimiento': mantenimiento.id_mantenimiento,
        'tipo_mantenimiento': mantenimiento.tipo_mantenimiento,
        'fecha_mantenimiento': mantenimiento.fecha_mantenimiento.strftime('%Y-%m-%d'),
        'proxima_fecha': mantenimiento.proxima_fecha.strftime('%Y-%m-%d'),
        'frecuencia': mantenimiento.frecuencia,
        'descripcion': mantenimiento.descripcion,
        'estado_actual': mantenimiento.estado_actual,
        'tiempo_requerido': mantenimiento.tiempo_requerido,
        'nombre_maquinaria': mantenimiento.nombre_maquinaria,
        'imagen_maquinaria': base64.b64encode(mantenimiento.imagen_maquinaria).decode('utf-8') if mantenimiento.imagen_maquinaria else None,
        'nombre_usuario': f"{mantenimiento.nombre_operario} {mantenimiento.apellido_operario}",
        'imagen_usuario': base64.b64encode(mantenimiento.imagen_operario).decode('utf-8') if mantenimiento.imagen_operario else None,
    } for mantenimiento in mantenimientos]

    return jsonify(resultado), 200

# Crear un nuevo mantenimiento
@app.route('/mantenimientos', methods=['POST'])
@jwt_required()
def crear_mantenimiento():
    data = request.get_json()
    herramientas = data.get('herramientas', [])

    nuevo_mantenimiento = Mantenimiento(
        id_maquinaria=int(data['id_maquinaria']),
        id_usuario=int(data['id_usuario']),
        tipo_mantenimiento=data['tipo_mantenimiento'],
        fecha_mantenimiento=datetime.strptime(data['fecha_mantenimiento'], '%Y-%m-%d'),
        frecuencia=int(data['frecuencia']),
        descripcion=data.get('descripcion', ''),
        tiempo_requerido=int(data['tiempo_requerido']),
    )
    nuevo_mantenimiento.calcular_proxima_fecha()
    db.session.add(nuevo_mantenimiento)
    db.session.commit()

    # Añadir herramientas al mantenimiento
    for herramienta in herramientas:
        db.session.execute(mantenimiento_herramienta.insert().values(
            id_mantenimiento=nuevo_mantenimiento.id_mantenimiento,
            id_herramienta=herramienta['id_herramienta'],
            cantidad_usada=herramienta['cantidad_usada']
        ))
    db.session.commit()

    # Crear notificación
    operario = Usuario.query.get(data['id_usuario'])
    mensaje = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                background-color: #f4f4f4;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                background-color: #fff;
                padding: 20px;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
                max-width: 600px;
                margin: auto;
            }}
            h2 {{
                color: #0056b3;
                margin-bottom: 20px;
            }}
            .details {{
                margin: 20px 0;
            }}
            .footer {{
                margin-top: 20px;
                font-size: 0.9em;
                color: #777;
            }}
            .notice {{
                font-size: 0.8em;
                color: #999;
                margin-top: 15px;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Estimado/a {operario.nombres},</h2>
            <p>El departamento administrativo de <strong>Ingema 3R</strong> se complace en informarle que ha sido asignado/a a un nuevo mantenimiento programado. A continuacion, se presentan los detalles del mantenimiento:</p>
            <div class="details">
                <p><strong>Tipo de mantenimiento:</strong> {nuevo_mantenimiento.tipo_mantenimiento}</p>
                <p><strong>Maquinaria:</strong> {nuevo_mantenimiento.maquinaria.nombre}</p>
                <p><strong>Fecha programada:</strong> {nuevo_mantenimiento.fecha_mantenimiento.strftime('%d/%m/%Y')}</p>
                <p><strong>Frecuencia:</strong> Cada {nuevo_mantenimiento.frecuencia} dias</p>
                <p><strong>Tiempo requerido:</strong> {nuevo_mantenimiento.tiempo_requerido} horas</p>
                <p><strong>Descripcion:</strong> {nuevo_mantenimiento.descripcion}</p>
            </div>
            <p>Agradecemos su atencion y le solicitamos que se prepare adecuadamente para llevar a cabo este mantenimiento en la fecha indicada. Su profesionalismo y compromiso son fundamentales para el exito de nuestras operaciones.</p>
            <p class="footer">Atentamente,<br>El equipo administrativo de Ingema 3R</p>
            <p class="notice">Nota: Las tildes han sido omitidas intencionalmente para evitar conflictos de codificacion en el correo electronico.</p>
        </div>
    </body>
    </html>
    """
    notificacion = Notificacion(
        id_usuario=operario.id_usuario,
        id_mantenimiento=nuevo_mantenimiento.id_mantenimiento,
        tipo="correo",
        mensaje=mensaje,
        estado_envio="pendiente"
    )
    db.session.add(notificacion)
    db.session.commit()

    # Enviar correo
    enviar_notificacion_correo(operario.email, "Nuevo Mantenimiento Asignado", mensaje)

    return jsonify({"mensaje": "Mantenimiento creado exitosamente"}), 201


# Actualizar un mantenimiento existente
@app.route('/mantenimientos/<int:id_mantenimiento>', methods=['PUT'])
@jwt_required()
def actualizar_mantenimiento(id_mantenimiento):
    mantenimiento = Mantenimiento.query.get_or_404(id_mantenimiento)
    data = request.get_json()  # Cambia request.form por request.get_json()
    herramientas = data.get('herramientas', [])  # Herramientas y sus cantidades

    if 'id_maquinaria' in data and data['id_maquinaria']:
        mantenimiento.id_maquinaria = int(data['id_maquinaria'])

    if 'id_usuario' in data and data['id_usuario']:
        mantenimiento.id_usuario = int(data['id_usuario'])

    mantenimiento.tipo_mantenimiento = data['tipo_mantenimiento']
    mantenimiento.fecha_mantenimiento = datetime.strptime(data['fecha_mantenimiento'], '%Y-%m-%d')
    mantenimiento.frecuencia = int(data['frecuencia'])
    mantenimiento.descripcion = data.get('descripcion', mantenimiento.descripcion)
    mantenimiento.tiempo_requerido = int(data['tiempo_requerido'])

    mantenimiento.calcular_proxima_fecha()
    db.session.commit()

    # Actualizar herramientas
    db.session.execute(mantenimiento_herramienta.delete().where(
        mantenimiento_herramienta.c.id_mantenimiento == id_mantenimiento
    ))

    for herramienta in herramientas:
        db.session.execute(mantenimiento_herramienta.insert().values(
            id_mantenimiento=id_mantenimiento,
            id_herramienta=herramienta['id_herramienta'],
            cantidad_usada=herramienta['cantidad_usada']
        ))
    db.session.commit()

    return jsonify({"mensaje": "Mantenimiento actualizado con éxito"}), 200

# Actualizar el estado de un mantenimiento existente (notificación)
@app.route('/mantenimientos/<int:id_mantenimiento>/estado', methods=['POST'])
@jwt_required()
def cambiar_estado_mantenimiento(id_mantenimiento):
    data = request.get_json()
    nuevo_estado = data['estado']
    observacion = data.get('observacion', '')

    mantenimiento = Mantenimiento.query.get_or_404(id_mantenimiento)
    mantenimiento.estado_actual = nuevo_estado

    # Crear entrada en el historial
    historial = HistorialEstado(
        id_mantenimiento=id_mantenimiento,
        estado=nuevo_estado,
        observacion=observacion,
        es_estado_actual=True
    )
    db.session.add(historial)
    db.session.commit()

    # Crear notificación para el administrador
    mensaje = f"El mantenimiento {mantenimiento.id_mantenimiento} cambió a estado {nuevo_estado}."
    notificacion = Notificacion(
        id_usuario=None,  # Administrador no tiene id fijo
        id_mantenimiento=id_mantenimiento,
        tipo="correo",
        mensaje=mensaje,
        estado_envio="pendiente"
    )
    db.session.add(notificacion)
    db.session.commit()

    # Enviar correo al administrador
    admin_email = "admin@empresa.com"  # Cambia por el correo real del administrador
    enviar_notificacion_correo(admin_email, "Cambio de Estado en Mantenimiento", mensaje)

    return jsonify({"message": "Estado actualizado correctamente"}), 200



# Obtener un mantenimiento por su ID
@app.route('/mantenimientos/<int:id_mantenimiento>', methods=['GET'])
@jwt_required()
def obtener_mantenimiento(id_mantenimiento):
    mantenimiento = Mantenimiento.query.get_or_404(id_mantenimiento)
    maquinaria = Maquinaria.query.get(mantenimiento.id_maquinaria)
    operario = Usuario.query.get(mantenimiento.id_usuario)

    return jsonify({
        'id_mantenimiento': mantenimiento.id_mantenimiento,
        'id_maquinaria': mantenimiento.id_maquinaria,
        'nombre_maquinaria': maquinaria.nombre if maquinaria else None,
        'id_usuario': mantenimiento.id_usuario,
        'nombre_usuario': f"{operario.nombres} {operario.apellidos}" if operario else None,
        'tipo_mantenimiento': mantenimiento.tipo_mantenimiento,
        'fecha_mantenimiento': mantenimiento.fecha_mantenimiento.strftime('%Y-%m-%d'),
        'proxima_fecha': mantenimiento.proxima_fecha.strftime('%Y-%m-%d'),
        'frecuencia': mantenimiento.frecuencia,
        'descripcion': mantenimiento.descripcion,
        'tiempo_requerido': mantenimiento.tiempo_requerido,
        'estado_actual': mantenimiento.estado_actual,
    }), 200

# Eliminar un mantenimiento
@app.route('/mantenimientos/<int:id_mantenimiento>', methods=['DELETE'])
@jwt_required()
def eliminar_mantenimiento(id_mantenimiento):
    mantenimiento = Mantenimiento.query.get_or_404(id_mantenimiento)
    db.session.delete(mantenimiento)
    db.session.commit()
    return jsonify({"mensaje": "Mantenimiento eliminado con éxito"}), 200

################# OPERARIO #######################

# Ruta para obtener los mantenimientos asignados al operario
@app.route('/api/operario/dashboard', methods=['GET'])
@jwt_required()
def obtener_mantenimientos_operario():
    identidad = get_jwt_identity()
    id_usuario = identidad['id_usuario']
    print(f"ID de usuario: {id_usuario}")
    # Obtener el usuario
    usuario = Usuario.query.get(id_usuario)

    if not usuario:
        return jsonify({'mensaje': 'Usuario no encontrado'}), 404

    # Obtener mantenimientos asignados al operario
    mantenimientos = Mantenimiento.query.filter_by(id_usuario=id_usuario).all()

    # Obtener la fecha actual
    fecha_actual = datetime.utcnow()

    # Filtrar mantenimientos para los próximos 5 días
    fecha_limite = fecha_actual + timedelta(days=5)
    mantenimientos_proximos = [m for m in mantenimientos if fecha_actual.date() <= m.fecha_mantenimiento.date() <= fecha_limite.date()]
    print(f"Fecha actual: {fecha_actual}, Fecha límite: {fecha_limite}")

    # Calcular el resumen de tareas semanales (completadas y pendientes)
    tareas_completadas = len([m for m in mantenimientos if m.estado_actual == "Completado"])
    tareas_pendientes = len([m for m in mantenimientos if m.estado_actual == "pendiente"])
    tareas_en_progreso = len([m for m in mantenimientos if m.estado_actual == "En progreso"])
    tareas_canceladas = len([m for m in mantenimientos if m.estado_actual == "Cancelado"])

    # Rendimiento semanal: Obtener tareas completadas en los últimos 7 días
    semana_anterior = fecha_actual - timedelta(days=7)
    mantenimientos_semanales = Mantenimiento.query.filter(
        Mantenimiento.id_usuario == id_usuario,
        Mantenimiento.fecha_mantenimiento >= semana_anterior,
        Mantenimiento.fecha_mantenimiento <= fecha_actual
    ).all()

    rendimiento_semanal = []
    for i in range(7):
        dia = semana_anterior + timedelta(days=i)
        completadas = len([m for m in mantenimientos_semanales if m.fecha_mantenimiento.date() == dia.date() and m.estado_actual == 'Completado'])
        rendimiento_semanal.append({
            'day': dia.strftime('%a'),  # Abreviatura del día de la semana
            'completadas': completadas
        })

    # Preparar la respuesta con la foto del usuario
    foto_usuario = None
    if usuario.foto:
        foto_usuario = base64.b64encode(usuario.foto).decode('utf-8') if usuario.foto else None

    mantenimientos_data = [{
        'id_mantenimiento': m.id_mantenimiento,
        'tipo_mantenimiento': m.tipo_mantenimiento,
        'maquinaria': m.maquinaria.nombre,
        'fecha_mantenimiento': m.fecha_mantenimiento.strftime('%Y-%m-%d'),  # Formato de fecha sin hora
        'estado_actual': m.estado_actual,
        'tiempo_requerido': m.tiempo_requerido,  # Añadir tiempo requerido
        'descripcion': m.descripcion,
    } for m in mantenimientos_proximos]  # Mostrar solo mantenimientos próximos


    return jsonify({
        'usuario': {
            'nombre': f'{usuario.nombres} {usuario.apellidos}',
            'email': usuario.email,
            'foto': foto_usuario  # Foto o null si no tiene
        },
        'resumen': {
            'tareas_completadas': tareas_completadas,
            'tareas_pendientes': tareas_pendientes,
            'tareas_en_progreso': tareas_en_progreso,
            'tareas_canceladas': tareas_canceladas,
        },
        'rendimiento_semanal': rendimiento_semanal,
        'mantenimientos': mantenimientos_data
    }), 200

################# PERFIL DE USUARIO #######################
# Ruta para obtener el perfil del usuario
@app.route('/api/operario/perfil', methods=['GET'])
@jwt_required()
def obtener_perfil_operario():
    identidad = get_jwt_identity()
    id_usuario = identidad['id_usuario']

    # Obtener el usuario
    usuario = Usuario.query.get(id_usuario)

    if not usuario:
        return jsonify({'mensaje': 'Usuario no encontrado'}), 404

    # Obtener el título del usuario
    titulo = Titulo.query.get(usuario.id_titulo)  # Obtener título relacionado si existe

    # Preparar la respuesta con la información del usuario
    foto_usuario = None
    if usuario.foto:
        foto_usuario = base64.b64encode(usuario.foto).decode('utf-8')  # Codificar la imagen en base64

    return jsonify({
        'nombre': f'{usuario.nombres} {usuario.apellidos}',
        'email': usuario.email,
        'foto': foto_usuario,
        'telefono': usuario.telefono,
        'cedula': usuario.cedula,
        'genero': usuario.genero,
        'titulo': titulo.nombre if titulo else 'Sin título'
    }), 200

# Ruta para actualizar la contraseña del usuario
@app.route('/api/operario/cambiar-contrasena', methods=['PUT'])
@jwt_required()
def cambiar_contrasena_operario():
    identidad = get_jwt_identity()
    id_usuario = identidad['id_usuario']
    data = request.get_json()

    usuario = Usuario.query.get(id_usuario)

    if not usuario:
        return jsonify({'mensaje': 'Usuario no encontrado'}), 404

    # Validar contraseña actual
    if not usuario.password or not check_password_hash(usuario.password, data['contrasena_actual']):
        return jsonify({'mensaje': 'La contraseña actual es incorrecta o no existe'}), 400

    # Validar nueva contraseña
    nueva_contrasena = data['nueva_contrasena']
    if len(nueva_contrasena) < 8 or not any(c.isdigit() for c in nueva_contrasena) or not any(c.isalpha() for c in nueva_contrasena):
        return jsonify({'mensaje': 'La nueva contraseña no cumple con los requisitos'}), 400

    # Actualizar contraseña
    usuario.password = generate_password_hash(nueva_contrasena)
    db.session.commit()

    return jsonify({'mensaje': 'Contraseña actualizada con éxito'}), 200


# Ruta para actualizar el perfil del operario
@app.route('/api/operario/perfil', methods=['PUT'])
@jwt_required()
def actualizar_perfil_operario():
    identidad = get_jwt_identity()
    id_usuario = identidad['id_usuario']

    usuario = Usuario.query.get(id_usuario)
    data = request.get_json()

    if not usuario:
        return jsonify({'mensaje': 'Usuario no encontrado'}), 404

    # Validar y actualizar datos del usuario
    if 'email' in data and data['email'] != usuario.email:
        if Usuario.query.filter_by(email=data['email']).first():
            return jsonify({'mensaje': 'El correo ya está en uso'}), 400

    usuario.nombres = data.get('nombres', usuario.nombres)
    usuario.apellidos = data.get('apellidos', usuario.apellidos)
    usuario.email = data.get('email', usuario.email)
    usuario.telefono = data.get('telefono', usuario.telefono)
    db.session.commit()

    return jsonify({'mensaje': 'Perfil actualizado con éxito'}), 200


# Ruta para obtener el contacto de emergencia del usuario
@app.route('/api/operario/contacto', methods=['GET'])
@jwt_required()
def obtener_contacto_operario():
    identidad = get_jwt_identity()
    id_usuario = identidad['id_usuario']

    contacto = Contacto.query.filter_by(id_usuario=id_usuario).first()

    if not contacto:
        return jsonify({'mensaje': 'Contacto no encontrado'}), 404

    return jsonify({
        'nombre': contacto.nombre,
        'direccion': contacto.direccion,
        'celular': contacto.celular,
        'convencional': contacto.convencional,
        'email': contacto.email,
        'parentesco': contacto.parentesco
    }), 200

# Ruta para actualizar el contacto de emergencia
@app.route('/api/operario/contacto', methods=['PUT'])
@jwt_required()
def actualizar_contacto_operario():
    identidad = get_jwt_identity()
    id_usuario = identidad['id_usuario']

    contacto = Contacto.query.filter_by(id_usuario=id_usuario).first()
    data = request.get_json()

    if not contacto:
        return jsonify({'mensaje': 'Contacto no encontrado'}), 404

    # Actualizar los datos del contacto
    contacto.nombre = data.get('nombre', contacto.nombre)
    contacto.direccion = data.get('direccion', contacto.direccion)
    contacto.celular = data.get('celular', contacto.celular)
    contacto.convencional = data.get('convencional', contacto.convencional)
    contacto.email = data.get('email', contacto.email)
    contacto.parentesco = data.get('parentesco', contacto.parentesco)

    db.session.commit()

    return jsonify({'mensaje': 'Contacto actualizado con éxito'}), 200


############### DETALLES #############

# Ruta para obtener los mantenimientos del usuario logueado
@app.route('/mantenimientos/usuario', methods=['GET'])
@jwt_required()
def obtener_mantenimientos_usuario():
    identidad = get_jwt_identity()
    id_usuario = identidad['id_usuario']

    # Obtener los mantenimientos del usuario logueado
    mantenimientos = Mantenimiento.query.filter_by(id_usuario=id_usuario).all()

    mantenimientos_data = []
    for mantenimiento in mantenimientos:
        maquina = Maquinaria.query.get(mantenimiento.id_maquinaria)
        mantenimientos_data.append({
            'id_mantenimiento': mantenimiento.id_mantenimiento,
            'maquina': maquina.nombre if maquina else 'Desconocida',
            'tipo_mantenimiento': mantenimiento.tipo_mantenimiento,
            'fecha_programada': mantenimiento.fecha_mantenimiento,
            'estado': mantenimiento.estado_actual,
        })

    return jsonify({'mantenimientos': mantenimientos_data}), 200


# Ruta para obtener los detalles de un mantenimiento específico
@app.route('/managment/<int:id_mantenimiento>', methods=['GET'])
@jwt_required()
def obtener_mantenimiento_unitario(id_mantenimiento):
    mantenimiento = Mantenimiento.query.get_or_404(id_mantenimiento)
    maquinaria = Maquinaria.query.get(mantenimiento.id_maquinaria)

    # Obtener herramientas asociadas al mantenimiento
    herramientas = db.session.query(Herramienta, mantenimiento_herramienta.c.cantidad_usada) \
        .join(mantenimiento_herramienta, Herramienta.id_herramienta == mantenimiento_herramienta.c.id_herramienta) \
        .filter(mantenimiento_herramienta.c.id_mantenimiento == mantenimiento.id_mantenimiento) \
        .all()

    herramientas_data = [
        {
            "id_herramienta": h.id_herramienta,
            "nombre": h.nombre,
            "cantidad_usada": cantidad_usada
        }
        for h, cantidad_usada in herramientas
    ]

    # Buscar el último mantenimiento completado para esta maquinaria
    ultimo_historial = HistorialEstado.query \
        .join(Mantenimiento, Mantenimiento.id_mantenimiento == HistorialEstado.id_mantenimiento) \
        .filter(Mantenimiento.id_maquinaria == maquinaria.id_maquinaria,
                HistorialEstado.estado.ilike('%completado%')) \
        .order_by(HistorialEstado.fecha_estado.desc()) \
        .first()

    ultima_revision = ultimo_historial.fecha_estado.strftime('%Y-%m-%d') if ultimo_historial else None

    # Convertir imagen de la maquinaria a base64 si existe
    imagen_maquinaria = base64.b64encode(maquinaria.m_imagen).decode('utf-8') if maquinaria.m_imagen else None

    return jsonify({
        "mantenimiento": {
            "id_mantenimiento": mantenimiento.id_mantenimiento,
            "tipo_mantenimiento": mantenimiento.tipo_mantenimiento,
            "fecha_mantenimiento": mantenimiento.fecha_mantenimiento,
            "tiempo_requerido": mantenimiento.tiempo_requerido,
            "estado_actual": mantenimiento.estado_actual,
            "descripcion": mantenimiento.descripcion,
            "herramientas": herramientas_data,
        },
        "maquinaria": {
            "nombre": maquinaria.nombre,
            "modelo": maquinaria.modelo,
            "numero_serie": maquinaria.numero_serie,
            "ultima_revision": ultima_revision,
            "descripcion": maquinaria.descripcion,
            "imagen": imagen_maquinaria  # Se agrega la imagen en base64
        }
    })

# Ruta para actualizar el estado y observaciones de un mantenimiento específico
@app.route('/managment/<int:id_mantenimiento>/actualizar-estado', methods=['POST'])
@jwt_required()
def actualizar_estado_mantenimiento(id_mantenimiento):
    mantenimiento = Mantenimiento.query.get_or_404(id_mantenimiento)

    # Obtener el nuevo estado y la observación desde el request
    data = request.get_json()
    nuevo_estado = data.get('estado', None)
    observacion = data.get('observacion', "")

    # Validación básica para asegurarse de que se envíe un estado
    if not nuevo_estado:
        return jsonify({"error": "El estado es requerido"}), 400

    # Actualizar el estado actual del mantenimiento
    mantenimiento.estado_actual = nuevo_estado

    # Desactivar el estado actual en el historial de estados
    HistorialEstado.query.filter_by(id_mantenimiento=id_mantenimiento, es_estado_actual=True).update({
        'es_estado_actual': False
    })

    # Añadir un nuevo registro al historial de estados con el nuevo estado y observaciones
    nuevo_historial = HistorialEstado(
        id_mantenimiento=id_mantenimiento,
        estado=nuevo_estado,
        observacion=observacion,
        es_estado_actual=True,  # Este será el nuevo estado actual
        fecha_estado=datetime.utcnow()
    )
    db.session.add(nuevo_historial)

    try:
        db.session.commit()
        return jsonify({"message": "Estado y observaciones actualizados correctamente", "estado": nuevo_estado}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500



#### HISTORIAL DE MANTENIMIENTOS ###
# Ruta para obtener el historial de mantenimientos del usuario logueado
@app.route('/api/operario/historial', methods=['GET'])
@jwt_required()
def obtener_historial_operario():
    identidad = get_jwt_identity()
    id_usuario = identidad['id_usuario']  # Asegúrate de que el token contiene el 'id_usuario'

    try:
        # Obtener los mantenimientos realizados por el usuario logueado
        mantenimientos = Mantenimiento.query.filter_by(id_usuario=id_usuario).all()

        # Construir la respuesta con los detalles de cada mantenimiento
        historial_data = []
        for mantenimiento in mantenimientos:
            maquinaria = Maquinaria.query.get(mantenimiento.id_maquinaria)

            historial_data.append({
                'id_mantenimiento': mantenimiento.id_mantenimiento,
                'maquina': maquinaria.nombre if maquinaria else 'Desconocida',
                'tipo_mantenimiento': mantenimiento.tipo_mantenimiento,
                'fecha_programada': mantenimiento.fecha_mantenimiento.strftime('%d/%m/%Y'),
                'duracion': f"{mantenimiento.tiempo_requerido} horas",
                'estado': mantenimiento.estado_actual,
                'observaciones': mantenimiento.descripcion,
            })

        return jsonify({'historial': historial_data}), 200

    except Exception as e:
        # Registro del error para depuración
        print("ERROR en /api/operario/historial:", str(e))
        return jsonify({'error': 'Error al obtener el historial de mantenimientos'}), 500



### CALENDARIO ####

@app.route('/api/operario/calendario', methods=['GET'])
@jwt_required()
def obtener_calendario_operario():
    try:
        # Obtener el ID del operario logueado
        identidad = get_jwt_identity()
        id_usuario = identidad['id_usuario']

        # Filtrar los mantenimientos del operario
        mantenimientos = Mantenimiento.query.filter_by(id_usuario=id_usuario).all()

        # Formatear los datos para el calendario
        eventos = []
        for mantenimiento in mantenimientos:
            maquina = Maquinaria.query.get(mantenimiento.id_maquinaria)
            eventos.append({
                "id": mantenimiento.id_mantenimiento,
                "maquina": maquina.nombre if maquina else "Desconocida",
                "tipo": mantenimiento.tipo_mantenimiento,
                "fecha": mantenimiento.fecha_mantenimiento.isoformat(),
                "duracion": mantenimiento.tiempo_requerido * 60,  # En minutos
                "estado": mantenimiento.estado_actual,
                "descripcion": mantenimiento.descripcion
            })

        return jsonify(eventos), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

####################### FUNCIÓN PARA ENVIAR NOTIFICACIÓN ########################################
def enviar_notificacion_correo(destinatario, asunto, mensaje):
    try:
        config = ConfiguracionNotificaciones.query.first()
        if not config:
            raise ValueError("No se encontró la configuración de correo.")

        # Configuración SMTP
        server = smtplib.SMTP(config.smtp_server, config.smtp_port)
        server.starttls()
        server.login(config.email, config.smtp_password)

        # Crear el mensaje con codificación UTF-8
        msg = MIMEText(mensaje, "html", "utf-8")
        msg["Subject"] = asunto
        msg["From"] = config.email
        msg["To"] = destinatario

        # Enviar el correo
        server.sendmail(config.email, destinatario, msg.as_string())
        server.quit()

        return True
    except Exception as e:
        print(f"Error al enviar correo: {e}")
        return False


###############################################################

########## NOTIFICACIONES ##########

# Ruta para obtener la configuración
@app.route('/api/admin/config-notificaciones', methods=['GET'])
def get_config_notificaciones():
    config = ConfiguracionNotificaciones.query.first()
    if config:
        return jsonify({
            "email": config.email,
            "smtp_server": config.smtp_server,
            "smtp_port": config.smtp_port
        })
    return jsonify({"message": "No hay configuración encontrada"}), 404

# Ruta para actualizar o crear la configuración
@app.route('/api/admin/config-notificaciones', methods=['POST'])
def set_config_notificaciones():
    data = request.json
    email = data.get('email')
    smtp_server = data.get('smtp_server')
    smtp_port = data.get('smtp_port')
    smtp_password = data.get('smtp_password')

    config = ConfiguracionNotificaciones.query.first()
    if not config:
        config = ConfiguracionNotificaciones(
            email=email,
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            smtp_password=smtp_password
        )
    else:
        config.email = email
        config.smtp_server = smtp_server
        config.smtp_port = smtp_port
        config.smtp_password = smtp_password

    db.session.add(config)
    db.session.commit()
    return jsonify({"message": "Configuración actualizada correctamente"}), 200


@app.route('/api/admin/test-email', methods=['POST'])
def test_email():
    import traceback

    data = request.json
    recipient = data.get('recipient')

    config = ConfiguracionNotificaciones.query.first()
    if not config:
        return jsonify({"message": "No hay configuración encontrada. Por favor, configura primero el sistema."}), 404

    if not recipient:
        recipient = config.email

    try:
        # Configura el servidor SMTP
        print(f"Intentando enviar correo usando: {config.smtp_server}:{config.smtp_port}")
        print(f"Usuario: {config.email}")
        print(f"Destinatario: {recipient}")

        server = smtplib.SMTP(config.smtp_server, config.smtp_port)
        server.starttls()
        server.login(config.email, config.smtp_password)

        # Crea el mensaje
        msg = MIMEText(f"Este es un correo de prueba enviado desde {config.email}.")
        msg["Subject"] = "Correo de Prueba"
        msg["From"] = config.email
        msg["To"] = recipient

        # Envía el correo
        server.sendmail(config.email, recipient, msg.as_string())
        server.quit()

        return jsonify({"message": f"Correo de prueba enviado correctamente a {recipient}."}), 200

    except Exception as e:
        print("Error al enviar el correo:", traceback.format_exc())
        return jsonify({"message": f"Error al enviar el correo: {str(e)}"}), 500


@app.route('/notificaciones', methods=['GET'])
@jwt_required()
def obtener_notificaciones():
    usuario_actual = get_jwt_identity()
    notificaciones = Notificacion.query.filter_by(id_usuario=usuario_actual).order_by(Notificacion.created_at.desc()).all()

    return jsonify([
        {
            "id": notificacion.id_notificacion,
            "mensaje": notificacion.mensaje,
            "tipo": notificacion.tipo,
            "estado_envio": notificacion.estado_envio,
            "fecha_envio": notificacion.fecha_envio,
            "created_at": notificacion.created_at
        }
        for notificacion in notificaciones
    ])

@app.route('/notificaciones/<int:id_notificacion>', methods=['PUT'])
@jwt_required()
def marcar_notificacion_como_leida(id_notificacion):
    notificacion = Notificacion.query.get_or_404(id_notificacion)
    notificacion.estado_envio = "leído"
    db.session.commit()
    return jsonify({"message": "Notificación marcada como leída."}), 200


######## ADMIN DASHBOARD Y REPORTES ########
@app.route("/api/admin/estadisticas", methods=["GET"])
@jwt_required()
def obtener_estadisticas():
    try:
        print("Ruta: /api/admin/estadisticas - Iniciando cálculo de estadísticas...")

        total_mantenimientos = Mantenimiento.query.count()
        mantenimientos_pendientes = Mantenimiento.query.filter(Mantenimiento.estado_actual.ilike("pendiente")).count()
        total_operarios = Usuario.query.filter(Usuario.id_rol == 2).count()
        total_maquinas = Maquinaria.query.count()
        mantenimientos_completados = Mantenimiento.query.filter(Mantenimiento.estado_actual.ilike("completado")).count()

        eficiencia_general = 0
        if total_mantenimientos > 0:
            eficiencia_general = (mantenimientos_completados / total_mantenimientos) * 100


        return jsonify({
            "total_mantenimientos": total_mantenimientos,
            "mantenimientos_pendientes": mantenimientos_pendientes,
            "total_operarios": total_operarios,
            "total_maquinas": total_maquinas,
            "eficiencia_general": round(eficiencia_general, 2)
        }), 200
    except Exception as e:
        print("Error en /api/admin/estadisticas:", e)
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/mantenimientos-por-mes", methods=["GET"])
@jwt_required()
def obtener_mantenimientos_por_mes():
    try:
        print("Ruta: /api/admin/mantenimientos-por-mes - Obteniendo mantenimientos agrupados por mes...")

        mantenimientos = db.session.query(
            func.extract('month', Mantenimiento.fecha_mantenimiento).label("mes"),
            func.count(Mantenimiento.id_mantenimiento).filter(Mantenimiento.tipo_mantenimiento.ilike("Preventivo")).label("preventivos"),
            func.count(Mantenimiento.id_mantenimiento).filter(Mantenimiento.tipo_mantenimiento.ilike("Correctivo")).label("correctivos"),
            func.count(Mantenimiento.id_mantenimiento).filter(Mantenimiento.tipo_mantenimiento.ilike("Predictivo")).label("predictivos")
        ).group_by(func.extract('month', Mantenimiento.fecha_mantenimiento)).order_by(func.extract('month', Mantenimiento.fecha_mantenimiento)).all()

        data = [{"mes": int(m[0]), "preventivos": m[1], "correctivos": m[2], "predictivos": m[3]} for m in mantenimientos]


        return jsonify(data), 200
    except Exception as e:
        print("Error en /api/admin/mantenimientos-por-mes:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/estado-mantenimientos", methods=["GET"])
@jwt_required()
def obtener_estado_mantenimientos():
    try:
        print("Ruta: /api/admin/estado-mantenimientos - Obteniendo estado de mantenimientos...")

        completados = Mantenimiento.query.filter(Mantenimiento.estado_actual.ilike("completado")).count()
        en_progreso = Mantenimiento.query.filter(Mantenimiento.estado_actual.ilike("en progreso")).count()
        pendientes = Mantenimiento.query.filter(Mantenimiento.estado_actual.ilike("pendiente")).count()
        cancelados = Mantenimiento.query.filter(Mantenimiento.estado_actual.ilike("cancelado")).count()

        data = [
            {"name": "Completados", "value": completados, "color": "#22c55e"},
            {"name": "En Progreso", "value": en_progreso, "color": "#3b82f6"},
            {"name": "Pendientes", "value": pendientes, "color": "#f97316"},
            {"name": "Cancelados", "value": cancelados, "color": "#ef4444"}
        ]


        return jsonify(data), 200
    except Exception as e:
        print("Error en /api/admin/estado-mantenimientos:", e)
        return jsonify({"error": str(e)}), 500



@app.route("/api/admin/proximos-mantenimientos", methods=["GET"])
@jwt_required()
def obtener_proximos_mantenimientos():
    try:
        print("Ruta: /api/admin/proximos-mantenimientos - Obteniendo próximos mantenimientos...")

        pagina = int(request.args.get('pagina', 1))
        limite = 5
        offset = (pagina - 1) * limite

        fecha_actual = datetime.now()
        fecha_limite = fecha_actual + timedelta(days=7)

        mantenimientos = Mantenimiento.query.filter(
            Mantenimiento.fecha_mantenimiento.between(fecha_actual, fecha_limite)
        ).order_by(Mantenimiento.fecha_mantenimiento.asc()).offset(offset).limit(limite).all()

        data = [
            {
                "id": m.id_mantenimiento,
                "maquina": m.maquinaria.nombre,
                "tipo": m.tipo_mantenimiento,
                "fecha": m.fecha_mantenimiento.strftime("%d/%m/%Y"),
                "operario": f"{m.usuario.nombres} {m.usuario.apellidos}"
            }
            for m in mantenimientos
        ]


        return jsonify(data), 200
    except Exception as e:
        print("Error en /api/admin/proximos-mantenimientos:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/operarios-destacados", methods=["GET"])
@jwt_required()
def obtener_operarios_destacados():
    try:
        print("Ruta: /api/admin/operarios-destacados - Obteniendo operarios destacados...")

        pagina = int(request.args.get('pagina', 1))
        limite = 5
        offset = (pagina - 1) * limite

        operarios = db.session.query(
            Usuario.nombres,
            Usuario.apellidos,
            func.count(Mantenimiento.id_mantenimiento).label("total_mantenimientos"),
            (func.count(Mantenimiento.id_mantenimiento).filter(Mantenimiento.estado_actual.ilike("completado")) /
             func.count(Mantenimiento.id_mantenimiento) * 100).label("eficiencia")
        ).join(Mantenimiento, Usuario.id_usuario == Mantenimiento.id_usuario).filter(
            Usuario.id_rol == 2  # Solo operarios (id_rol = 2)
        ).group_by(
            Usuario.nombres, Usuario.apellidos
        ).order_by(func.count(Mantenimiento.id_mantenimiento).desc()).offset(offset).limit(limite).all()

        data = [
            {
                "nombre": f"{o[0]} {o[1]}",
                "mantenimientos": o[2],
                "eficiencia": round(o[3], 2) if o[3] else 0
            }
            for o in operarios
        ]


        return jsonify(data), 200
    except Exception as e:
        print("Error en /api/admin/operarios-destacados:", e)
        return jsonify({"error": str(e)}), 500



@app.route('/api/admin/reporte/<tipo_reporte>', methods=['GET'])
@jwt_required()
def generar_reporte(tipo_reporte):
    try:
        if tipo_reporte == "mantenimientos":
            mantenimientos = db.session.query(
                func.extract('month', Mantenimiento.fecha_mantenimiento).label("mes"),
                func.count(Mantenimiento.id_mantenimiento).filter(Mantenimiento.tipo_mantenimiento.ilike("Preventivo")).label("preventivos"),
                func.count(Mantenimiento.id_mantenimiento).filter(Mantenimiento.tipo_mantenimiento.ilike("Correctivo")).label("correctivos"),
                func.count(Mantenimiento.id_mantenimiento).filter(Mantenimiento.tipo_mantenimiento.ilike("Predictivo")).label("predictivos")
            ).group_by(func.extract('month', Mantenimiento.fecha_mantenimiento)).all()

            contenido = render_template("reporte_mantenimientos.html", mantenimientos=mantenimientos)

        elif tipo_reporte == "personal":
            personal = db.session.query(
                Usuario.id_rol,
                Rol.nombre.label('cargo'),
                func.count(Usuario.id_usuario).label('cantidad'),
                (func.avg(func.count(Mantenimiento.id_mantenimiento).filter(Mantenimiento.estado_actual.ilike("completado"))) /
                 func.avg(func.count(Mantenimiento.id_mantenimiento)) * 100).label('eficiencia')
            ).join(Rol, Usuario.id_rol == Rol.id_rol).join(Mantenimiento, Mantenimiento.id_usuario == Usuario.id_usuario).group_by(Usuario.id_rol, Rol.nombre).all()

            contenido = render_template("reporte_personal.html", personal=personal)

        elif tipo_reporte == "eficiencia":
            eficiencia = db.session.query(
                Maquinaria.id_maquinaria,
                Maquinaria.nombre.label('maquina'),
                func.avg(Mantenimiento.tiempo_requerido).label('eficiencia')
            ).join(Mantenimiento, Maquinaria.id_maquinaria == Mantenimiento.id_maquinaria).group_by(Maquinaria.id_maquinaria, Maquinaria.nombre).all()

            contenido = render_template("reporte_eficiencia.html", eficiencia=eficiencia)

        else:
            return jsonify({"message": "Tipo de reporte no soportado"}), 400

        pdf = pdfkit.from_string(contenido, False)
        response = make_response(pdf)
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = f"inline; filename={tipo_reporte}.pdf"
        return response
    except Exception as e:
        print(f"Error generando el reporte {tipo_reporte}:", e)
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/reporte/mantenimientos', methods=['GET'])
@jwt_required()
def generar_reporte_mantenimientos():
    try:
        print("Generando reporte de mantenimientos...")

        # Obtener los datos dinámicos
        mantenimientos = db.session.query(
            func.extract('month', Mantenimiento.fecha_mantenimiento).label("mes"),
            func.count(Mantenimiento.id_mantenimiento).filter(Mantenimiento.tipo_mantenimiento.ilike("Preventivo")).label("preventivos"),
            func.count(Mantenimiento.id_mantenimiento).filter(Mantenimiento.tipo_mantenimiento.ilike("Correctivo")).label("correctivos"),
            func.count(Mantenimiento.id_mantenimiento).filter(Mantenimiento.tipo_mantenimiento.ilike("Predictivo")).label("predictivos")
        ).group_by(func.extract('month', Mantenimiento.fecha_mantenimiento)).order_by(func.extract('month', Mantenimiento.fecha_mantenimiento)).all()

        # Lista de nombres de meses
        nombres_meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

        datos_mantenimientos = []
        total_mantenimientos = 0
        for mantenimiento in mantenimientos:
            total = (mantenimiento.preventivos or 0) + (mantenimiento.correctivos or 0) + (mantenimiento.predictivos or 0)
            total_mantenimientos += total
            mes_nombre = nombres_meses[int(mantenimiento.mes) - 1]  # Obtener el nombre del mes
            datos_mantenimientos.append({
                "mes": mes_nombre,  # Usar el nombre del mes
                "preventivos": mantenimiento.preventivos or 0,
                "correctivos": mantenimiento.correctivos or 0,
                "predictivos": mantenimiento.predictivos or 0,
                "total": total
            })

        # Evitar división por cero en eficiencia promedio
        eficiencia_promedio = 0
        if total_mantenimientos > 0:
            eficiencia_promedio = round((sum([m["total"] for m in datos_mantenimientos]) / total_mantenimientos) * 100, 2)

        # Generar el gráfico
        meses = [d["mes"] for d in datos_mantenimientos]
        preventivos = [d["preventivos"] for d in datos_mantenimientos]
        correctivos = [d["correctivos"] for d in datos_mantenimientos]
        predictivos = [d["predictivos"] for d in datos_mantenimientos]

        plt.figure(figsize=(10, 6))
        plt.bar(meses, preventivos, label='Preventivos', color='green')
        plt.bar(meses, correctivos, label='Correctivos', color='orange', bottom=preventivos)
        plt.bar(meses, predictivos, label='Predictivos', color='blue', bottom=[i + j for i, j in zip(preventivos, correctivos)])
        plt.title('Mantenimientos por Mes')
        plt.xlabel('Mes')
        plt.ylabel('Cantidad')
        plt.legend()

        # Convertir el gráfico a base64
        img_io = io.BytesIO()
        plt.savefig(img_io, format='png', bbox_inches="tight")
        img_io.seek(0)
        grafico_mantenimientos = "data:image/png;base64," + base64.b64encode(img_io.read()).decode('utf-8')
        plt.close()

        # Renderizar plantilla HTML con el gráfico incluido
        contenido = render_template(
            "reporte_mantenimientos.html",
            mantenimientos=datos_mantenimientos,
            total_mantenimientos=total_mantenimientos,
            eficiencia_promedio =eficiencia_promedio,
            grafico_mantenimientos=grafico_mantenimientos
        )

        # Generar el PDF
        pdf = pdfkit.from_string(contenido, False)
        response = make_response(pdf)
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = "inline; filename=reporte_mantenimientos.pdf"
        return response
    except Exception as e:
        print(f"Error generando el reporte de mantenimientos: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/reporte/personal', methods=['GET'])
@jwt_required()
def generar_reporte_personal():
    try:
        print("Generando reporte de personal...")

        # Query principal
        resultado = db.session.query(
            Titulo.nombre.label("titulo"),
            func.count(Usuario.id_usuario.distinct()).label("cantidad_operarios"),  # Contar usuarios únicos
            func.count(Mantenimiento.id_mantenimiento).label("cantidad_mantenimientos"),
            func.coalesce(
                func.avg(
                    case(
                        (Mantenimiento.estado_actual.ilike("completado"), 1),
                        else_=0
                    )
                ) * 100, 0
            ).label("eficiencia")
        ).join(Usuario, Usuario.id_titulo == Titulo.id_titulo) \
         .outerjoin(Mantenimiento, Mantenimiento.id_usuario == Usuario.id_usuario) \
         .group_by(Titulo.nombre).all()

        # Preparar datos para la plantilla
        data = []
        total_operarios = 0
        total_mantenimientos = 0
        eficiencia_promedio_global = 0

        for row in resultado:
            total_operarios += row.cantidad_operarios
            total_mantenimientos += row.cantidad_mantenimientos
            eficiencia_promedio_global += row.eficiencia
            data.append({
                "titulo": row.titulo,
                "cantidad_operarios": row.cantidad_operarios,
                "cantidad_mantenimientos": row.cantidad_mantenimientos,
                "eficiencia": round(row.eficiencia, 2)
            })

        eficiencia_promedio_global = eficiencia_promedio_global / len(data) if data else 0

        # Verificar si los datos fueron recuperados correctamente
        if not data:
            print("No se encontraron datos para el reporte de personal.")

        # Renderizar el HTML
        contenido = render_template(
            "reporte_personal.html",
            data=data,
            total_operarios=total_operarios,
            total_mantenimientos=total_mantenimientos,
            eficiencia_promedio_global=round(eficiencia_promedio_global, 2)
        )

        # Generar el PDF
        pdf = pdfkit.from_string(contenido, False)
        response = make_response(pdf)
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = "inline; filename=reporte_personal.pdf"
        return response

    except Exception as e:
        print(f"Error generando el reporte de personal: {e}")
        return jsonify({"error": str(e)}), 500