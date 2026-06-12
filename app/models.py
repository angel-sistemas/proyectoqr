from app import db
from datetime import datetime
from flask_login import UserMixin

class Rol(db.Model):
    __tablename__ = 'roles'
    id       = db.Column(db.Integer, primary_key=True)
    nombre   = db.Column(db.String(50), unique=True, nullable=False)

class Permiso(db.Model):
    __tablename__ = 'permisos'
    id     = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)

class RolPermiso(db.Model):
    __tablename__ = 'rol_permiso'
    rol_id     = db.Column(db.Integer, db.ForeignKey('roles.id'), primary_key=True)
    permiso_id = db.Column(db.Integer, db.ForeignKey('permisos.id'), primary_key=True)

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'

    id            = db.Column(db.Integer, primary_key=True)
    nombre        = db.Column(db.String(100), nullable=False)
    email         = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    rol_id        = db.Column(db.Integer, db.ForeignKey('roles.id'))
    activo        = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=datetime.now)

    def tiene_permiso(self, permiso_nombre):
        if not self.rol_id:
            return False
        permiso = Permiso.query.filter_by(nombre=permiso_nombre).first()
        print(f"buscando permiso: {permiso_nombre}, encontrado: {permiso}")
        if not permiso:
            return False
        rp = RolPermiso.query.filter_by(
            rol_id=self.rol_id,
            permiso_id=permiso.id
        ).first()
        print(f"RolPermiso encontrado: {rp}")
        return rp is not None

class Equipo(db.Model):
    __tablename__ = 'equipos'

    id              = db.Column(db.Integer, primary_key=True)
    codigo_producto = db.Column(db.String(20))
    propietario     = db.Column(db.String(100))
    descripcion     = db.Column(db.String(500))
    marca           = db.Column(db.String(50))
    referencia      = db.Column(db.String(100))
    serial          = db.Column(db.String(100), unique=True, nullable=False)
    activo_placa    = db.Column(db.String(50))
    mac             = db.Column(db.String(50))
    estado          = db.Column(db.String(100))
    localizacion    = db.Column(db.String(100))
    bodega          = db.Column(db.String(100))
    centro_costos   = db.Column(db.String(100))
    codigo_bodega   = db.Column(db.String(20))
    imagen_path     = db.Column(db.String(255))
    updated_at      = db.Column(db.DateTime, default=datetime.now)

    def _repr_(self):
        return f'<Equipo {self.serial}>'