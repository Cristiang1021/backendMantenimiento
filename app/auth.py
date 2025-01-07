from flask import request, jsonify
from app import app, db, blacklist, jwt  # Importamos la lista negra desde `__init__.py`
from app.models import Usuario, Rol, Acceso, Notificacion
from flask_jwt_extended import create_access_token, jwt_required, get_jwt
import bcrypt
from datetime import timedelta, datetime

from app.routes import enviar_notificacion_correo


# Ruta para verificar si la cédula ya existe
@app.route('/check-cedula/<cedula>', methods=['GET'])
def check_cedula(cedula):
    usuario = Usuario.query.filter_by(cedula=cedula).first()
    if usuario:
        return jsonify({"exists": True})
    else:
        return jsonify({"exists": False})


# Ruta para verificar si el correo ya existe
@app.route('/check-mail/<email>', methods=['GET'])
def check_email(email):
    usuario = Usuario.query.filter_by(email=email).first()
    if usuario:
        return jsonify({"exists": True})
    else:
        return jsonify({"exists": False})


# Ruta para registrar un nuevo usuario
@app.route('/register', methods=['POST'])
def register():
    data = request.form

    # Verificar si la cédula o el email ya existen en la base de datos
    if Usuario.query.filter_by(cedula=data['cedula']).first():
        return jsonify({'message': 'La cédula ya está registrada.'}), 400

    if Usuario.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'El correo ya está registrado.'}), 400

    # Generar un hash para la contraseña
    hashed_password = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())

    # Subir foto de perfil si está disponible
    foto = request.files['foto_perfil'].read() if 'foto_perfil' in request.files else None

    # Verificar si es el primer usuario registrado para asignar el rol de administrador
    total_usuarios = Usuario.query.count()

    if total_usuarios == 0:
        rol = Rol.query.filter_by(nombre='administrador').first()
        estado_usuario = 'activo'
    else:
        rol = Rol.query.filter_by(nombre='operario').first()
        estado_usuario = 'pendiente'

    if not rol:
        return jsonify({'message': f'Error: El rol {rol.nombre} no existe en la base de datos.'}), 400

    # Crear el nuevo usuario
    new_user = Usuario(
        nombres=data['nombres'],
        apellidos=data['apellidos'],
        cedula=data['cedula'],
        email=data['email'],
        password=hashed_password.decode('utf-8'),
        genero=data['genero'],
        telefono=data['telefono'],
        id_rol=rol.id_rol,
        foto=foto,
        estado_usuario=estado_usuario
    )
    db.session.add(new_user)
    db.session.commit()

    # Crear notificación
    mensaje = f"Bienvenido {data['nombres']}! Tu cuenta ha sido creada con exito."
    notificacion = Notificacion(
        id_usuario=new_user.id_usuario,
        tipo="correo",
        mensaje=mensaje,
        estado_envio="pendiente"
    )
    db.session.add(notificacion)
    db.session.commit()

    # Enviar correo
    correo_enviado = enviar_notificacion_correo(new_user.email, "Registro Exitoso", mensaje)
    if not correo_enviado:
        print("Error: El correo no pudo ser enviado, pero el registro fue exitoso.")

    if estado_usuario == 'activo':
        return jsonify({'message': 'Usuario registrado y activado exitosamente como administrador.'}), 201
    else:
        return jsonify({'message': 'Usuario registrado exitosamente. Tu cuenta sera activada por un administrador.'}), 201

# Ruta para iniciar sesión
@app.route('/login', methods=['OPTIONS', 'POST'])
def login():
    if request.method == 'OPTIONS':
        response = jsonify({"message": "CORS Preflight Passed"})
        response.headers.add("Access-Control-Allow-Origin", "http://127.0.0.1:3000")
        response.headers.add("Access-Control-Allow-Credentials", "true")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
        response.headers.add("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        return response, 200

    # Manejar POST (login)
    data = request.get_json()
    email_or_cedula = data.get('email_or_cedula')
    password = data.get('password')

    # Buscar el usuario por correo o cédula
    usuario = Usuario.query.filter(
        (Usuario.email == email_or_cedula) | (Usuario.cedula == email_or_cedula)
    ).first()

    if usuario and bcrypt.checkpw(password.encode('utf-8'), usuario.password.encode('utf-8')):
        if usuario.estado_usuario != 'activo':
            return jsonify({"mensaje": "Tu cuenta aún no ha sido activada"}), 403

        # Crear el token de acceso JWT con expiración de 6 horas
        access_token = create_access_token(identity={"id_usuario": usuario.id_usuario, "rol": usuario.id_rol}, expires_delta=timedelta(hours=24))

        # Registrar el acceso en la base de datos
        nuevo_acceso = Acceso(
            id_usuario=usuario.id_usuario,
            acceso_boole=True,  # Indica que el acceso fue exitoso
            fecha_acceso=datetime.utcnow()
        )
        db.session.add(nuevo_acceso)
        db.session.commit()

        return jsonify({
            'mensaje': 'Inicio de sesión exitoso',
            'access_token': access_token,
            'id_usuario': usuario.id_usuario,
            'rol': usuario.id_rol
        }), 200
    else:
        # Registrar intento fallido (opcional)
        return jsonify({"mensaje": "Correo o cédula y/o contraseña incorrectos"}), 401






# Ruta para cerrar sesión
@app.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    jti = get_jwt().get("jti")  # "jti" es el identificador único del JWT
    if not jti:
        return jsonify({"mensaje": "Token no válido o ausente"}), 422
    blacklist.add(jti)  # Añadir el JWT a la lista negra
    return jsonify({"mensaje": "Cierre de sesión exitoso."}), 200


@app.route('/check-auth', methods=['GET'])
def check_auth():
    # Obtener el token desde las cookies o headers
    token = request.cookies.get('access_token')
    if not token:
        return jsonify({"mensaje": "No autorizado"}), 401

    # Decodificar el token (asegúrate de manejar excepciones)
    try:
        decoded_token = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
        return jsonify({
            "id_usuario": decoded_token["id_usuario"],
            "rol": decoded_token["rol"],
        }), 200
    except jwt.ExpiredSignatureError:
        return jsonify({"mensaje": "Token expirado"}), 401
    except Exception as e:
        return jsonify({"mensaje": "Token inválido"}), 401
