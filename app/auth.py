import random
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import request, jsonify
from app import app, db, blacklist, jwt  # Importamos la lista negra desde `__init__.py`
from app.models import Usuario, Rol, Acceso, Notificacion, CodigoRecuperacion, ConfiguracionNotificaciones
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
        estado_usuario = 'Activo'
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

    if estado_usuario == 'activo' or estado_usuario == 'Activo':
        return jsonify({'message': 'Usuario registrado y activado exitosamente como administrador.'}), 201
    else:
        return jsonify({'message': 'Usuario registrado exitosamente. Tu cuenta sera activada por un administrador.'}), 201

# Ruta para iniciar sesión
@app.route('/login', methods=['OPTIONS', 'POST'])
def login():
    if request.method == 'OPTIONS':
        response = jsonify({"message": "CORS Preflight Passed"})
        #response.headers.add("Access-Control-Allow-Origin", "https://mantenimientofrond.ngrok.app")
        response.headers.add("Access-Control-Allow-Origin", "http://127.0.0.1:3000")
        #response.headers.add("Access-Control-Allow-Origin", "https://mantenimientoapp.vercel.app")
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
        if usuario.estado_usuario != 'Activo':
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


## RECUPERAR LA CONTRASEÑA


# Enviar correo con HTML (sin tildes) usando la configuracion SMTP de la base de datos
def enviar_codigo_recuperacion_por_correo(destinatario, codigo):
    config = ConfiguracionNotificaciones.query.first()
    if not config:
        print("No hay configuracion SMTP.")
        return False

    try:
        # Cuerpo HTML sin tildes
        mensaje = f"""
        <!DOCTYPE html>
        <html lang=\"es\">
        <head>
            <meta charset=\"UTF-8\">
            <style>
                body {{ font-family: Arial, sans-serif; background-color: #f9f9f9; padding: 20px; }}
                .container {{ background-color: #fff; padding: 20px; border-radius: 8px; max-width: 600px; margin: auto; }}
                h2 {{ color: #0056b3; }}
                .codigo {{ font-size: 1.5em; font-weight: bold; background-color: #eee; padding: 10px; border-radius: 5px; text-align: center; }}
                .footer {{ font-size: 0.8em; color: #888; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class=\"container\">
                <h2>Recuperacion de contrasena</h2>
                <p>Has solicitado recuperar el acceso a tu cuenta en <strong>Ingema 3R</strong>.</p>
                <p>Utiliza el siguiente codigo de verificacion. Tiene una validez de 10 minutos:</p>
                <div class=\"codigo\">{codigo}</div>
                <p>Si no solicitaste este cambio, puedes ignorar este mensaje.</p>
                <p class=\"footer\">Este correo fue generado automaticamente. No respondas a este mensaje.</p>
            </div>
        </body>
        </html>
        """

        msg = MIMEMultipart()
        msg["From"] = config.email
        msg["To"] = destinatario
        msg["Subject"] = "Codigo de recuperacion de contrasena"
        msg.attach(MIMEText(mensaje, "html", "utf-8"))

        server = smtplib.SMTP(config.smtp_server, config.smtp_port)
        server.starttls()
        server.login(config.email, config.smtp_password)
        server.sendmail(config.email, destinatario, msg.as_string())
        server.quit()

        return True
    except Exception as e:
        print("Error al enviar el correo de recuperacion:", str(e))
        return False

# Ruta para enviar el codigo de recuperacion
@app.route('/enviar-codigo-recuperacion', methods=['POST'])
def enviar_codigo():
    data = request.get_json()
    identificador = data.get("email")  # puede ser correo o cédula

    if not identificador:
        return jsonify({
            "mensaje": "Por favor, ingrese su correo electrónico o número de cédula."
        }), 400

    # Buscar por correo o cédula
    usuario = Usuario.query.filter(
        (Usuario.email == identificador) | (Usuario.cedula == identificador)
    ).first()

    if not usuario:
        return jsonify({
            "mensaje": "No se encontró ningún usuario registrado con las credenciales ingresadas."
        }), 404

    codigo = str(random.randint(100000, 999999))
    expiracion = datetime.utcnow() + timedelta(minutes=10)

    try:
        # Eliminar códigos anteriores y guardar nuevo
        CodigoRecuperacion.query.filter_by(email=usuario.email).delete()
        nuevo_codigo = CodigoRecuperacion(
            email=usuario.email,
            codigo=codigo,
            expiracion=expiracion
        )
        db.session.add(nuevo_codigo)
        db.session.commit()
    except Exception as e:
        print("Error en DB al guardar código:", e)
        return jsonify({
            "mensaje": "Se produjo un error interno al generar el código de recuperación. Intente nuevamente más tarde o contacte al soporte técnico."
        }), 500

    enviado = enviar_codigo_recuperacion_por_correo(usuario.email, codigo)
    if not enviado:
        return jsonify({
            "mensaje": "No se pudo enviar el código de verificación en este momento. Por favor, intente nuevamente más tarde."
        }), 500

    return jsonify({
        "mensaje": "Hemos enviado un código de verificación a su correo electrónico. Por favor, revise su bandeja de entrada o carpeta de spam."
    }), 200



# Ruta para verificar el codigo y cambiar la contrasena
@app.route('/verificar-codigo-recuperacion', methods=['POST'])
def verificar_codigo_recuperacion():
    import bcrypt

    data = request.get_json()
    identificador = data.get("email")  # puede ser correo o cédula
    codigo = data.get("codigo")
    nueva_password = data.get("nueva_password")  # Puede ser None si solo se valida el código

    if not identificador or not codigo:
        return jsonify({
            "mensaje": "Debe ingresar su correo o cédula y el código de verificación."
        }), 400

    # Buscar usuario por correo o cédula
    usuario = Usuario.query.filter(
        (Usuario.email == identificador) | (Usuario.cedula == identificador)
    ).first()

    if not usuario:
        return jsonify({
            "mensaje": "No se encontró ningún usuario registrado con las credenciales ingresadas."
        }), 404

    # Validar el código asociado al correo real del usuario
    registro = CodigoRecuperacion.query.filter_by(email=usuario.email, codigo=codigo).first()

    if not registro or registro.expiracion < datetime.utcnow():
        return jsonify({
            "mensaje": "El código ingresado no es válido o ha expirado. Solicite uno nuevo e intente nuevamente."
        }), 400

    # Si no se ha enviado una nueva contraseña, solo se está validando el código
    if not nueva_password:
        return jsonify({
            "mensaje": "Código verificado correctamente. Puede proceder a establecer una nueva contraseña."
        }), 200

    # Cambiar la contraseña
    usuario.password = bcrypt.hashpw(nueva_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    db.session.delete(registro)
    db.session.commit()

    return jsonify({
        "mensaje": "La contraseña se ha actualizado correctamente. Ahora puede iniciar sesión con sus nuevas credenciales."
    }), 200

