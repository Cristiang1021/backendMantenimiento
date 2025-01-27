import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'alo06015'
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:admin@localhost:5432/bdmantenimiento'
    #SQLALCHEMY_DATABASE_URI ='postgresql://mantenimiento_ehh6_user:VQkwmXGc1WYfhCCyC4ii1MS2AJp4Dmod@dpg-ctuabsbqf0us73f2bh9g-a.ohio-postgres.render.com/mantenimiento_ehh6'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = 'cr102146'
