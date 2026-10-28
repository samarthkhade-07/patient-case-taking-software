import os
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import PyMongoError
from backend.config import Config
from backend.common import error
from backend.routes.auth import bp as auth_bp
from backend.routes.patients import bp as patients_bp
from backend.routes.doctors import bp as doctors_bp
from backend.routes.appointments import bp as appointments_bp
from backend.routes.medical_records import bp as records_bp
from backend.routes.notifications import bp as notifications_bp

def create_app(test_config=None, db=None):
 app=Flask(__name__); app.config.from_object(Config)
 if test_config:app.config.update(test_config)
 testing=app.config.get('TESTING',False)
 if not app.config.get('MONGO_URI') and db is None and not testing:raise RuntimeError('MONGO_URI is required to run CareCase')
 secret=app.config.get('JWT_SECRET_KEY')
 if (not secret or len(secret)<32 or 'replace-with' in secret) and not testing:raise RuntimeError('Set JWT_SECRET_KEY to a private random value of at least 32 characters')
 if testing and not secret:app.config['JWT_SECRET_KEY']='test-only-secret-not-for-production-000000'
 if db is None:
  if not app.config.get('MONGO_URI'):raise RuntimeError('MONGO_URI is required unless a test database is injected')
  client=MongoClient(app.config['MONGO_URI'],serverSelectionTimeoutMS=5000,tz_aware=True); database=client[app.config.get('MONGO_DB_NAME','carecase')]; app.extensions['carecase_mongo_client']=client
 else:database=db
 app.extensions['carecase_db']=database
 if not testing:create_indexes(database)
 CORS(app,resources={r'/api/*':{'origins':app.config['FRONTEND_ORIGIN']}}); JWTManager(app)
 for bp in (auth_bp,patients_bp,doctors_bp,appointments_bp,records_bp,notifications_bp):app.register_blueprint(bp)
 @app.get('/api/health')
 def health():
  try:
   if hasattr(database,'command'):database.command('ping')
   return {'success':True,'data':{'status':'ok'}}
  except PyMongoError:return error('Database unavailable',503,'database_unavailable')
 @app.errorhandler(404)
 def not_found(_):return error('Resource not found',404)
 @app.errorhandler(400)
 def bad_request(_):return error('Invalid request',400)
 @app.errorhandler(500)
 def internal(_):return error('Internal server error',500)
 if app.config.get('ENABLE_REMINDER_SCHEDULER') and not testing:
  from backend.services.reminder_service import start_scheduler
  app.extensions['carecase_scheduler']=start_scheduler(app)
 return app

def create_indexes(db):
 db.users.create_index([('email',ASCENDING)],unique=True)
 db.patients.create_index([('user_id',ASCENDING)],unique=True); db.patients.create_index([('name',ASCENDING)])
 db.doctors.create_index([('user_id',ASCENDING)],unique=True); db.doctors.create_index([('name',ASCENDING)])
 db.appointments.create_index([('patient_id',ASCENDING),('start_at',ASCENDING)]); db.appointments.create_index([('doctor_id',ASCENDING),('status',ASCENDING),('start_at',ASCENDING),('end_at',ASCENDING)])
 db.medical_records.create_index([('patient_id',ASCENDING),('created_at',DESCENDING)]); db.medical_records.create_index([('doctor_id',ASCENDING),('patient_id',ASCENDING)])
 db.notifications.create_index([('user_id',ASCENDING),('created_at',DESCENDING)]); db.notifications.create_index([('appointment_id',ASCENDING),('lead_hours',ASCENDING)],unique=True,partialFilterExpression={'lead_hours':{'$exists':True}})
 db.doctor_locks.create_index([('expires_at',ASCENDING)],expireAfterSeconds=0)
if __name__=='__main__':create_app().run(host='0.0.0.0',port=int(os.getenv('PORT','5000')))
