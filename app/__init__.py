from flask import Flask, jsonify
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_migrate import Migrate

# Inicializa Flask-Mail
mail = Mail()

app = Flask(__name__)
app.config.from_object('app.config.Config')

# Inicializa las extensiones
db = SQLAlchemy(app)
jwt = JWTManager(app)
mail.init_app(app)  # Inicializa Flask-Mail con la aplicación

# Definimos la lista negra a nivel global
blacklist = set()

# Callback para verificar si un token está en la lista negra
@jwt.token_in_blocklist_loader
def check_if_token_in_blacklist(jwt_header, jwt_payload):
    jti = jwt_payload['jti']
    return jti in blacklist  # Verificar si el token está en la lista negra

# Configuración de CORS
#CORS(app, resources={r"/*": {"origins": ["https://mantenimientofrond.ngrok.app", "https://mantenimientofrond.ngrok.app"]}}, supports_credentials=True)
CORS(app, resources={r"/*": {"origins": ["https://mantenimientoapp.vercel.app", "https://mantenimientoapp.vercel.app"]}}, supports_credentials=True)
#CORS(app, resources={r"/*": {"origins": ["http://127.0.0.1:3000", "http://localhost:3000"]}}, supports_credentials=True)
##CORS(app, resources={r"/*": {"origins": ["https://g1zlbnml-3000.use.devtunnels.ms", "https://g1zlbnml-3000.use.devtunnels.ms"]}}, supports_credentials=True)
# Maneja el preflight request y permite CORS
@app.after_request
def after_request(response):
    #response.headers.add("Access-Control-Allow-Credentials", "true")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
    response.headers.add("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
    return response

migrate = Migrate(app, db)

from app import models, auth, routes
