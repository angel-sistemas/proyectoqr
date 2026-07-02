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
    rol = db.relationship('Rol', foreign_keys=[rol_id])

    def tiene_permiso(self, permiso_nombre):
        if not self.rol_id:
            return False
    
    # Caché de permisos en el objeto usuario
        if not hasattr(self, '_permisos_cache'):
        # Cargar todos los permisos del rol de una sola vez
            rps = RolPermiso.query.filter_by(rol_id=self.rol_id).all()
            permisos_ids = [rp.permiso_id for rp in rps]
            permisos = Permiso.query.filter(Permiso.id.in_(permisos_ids)).all()
            self._permisos_cache = {p.nombre for p in permisos}
    
        return permiso_nombre in self._permisos_cache

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
    cantidad        = db.Column(db.Integer, default=1)
    observaciones = db.Column(db.Text)

    def _repr_(self):
        return f'<Equipo {self.serial}>'

class Inventario(db.Model):
    __tablename__ = 'inventarios'

    id            = db.Column(db.Integer, primary_key=True)
    tipo          = db.Column(db.String(20))
    bodega        = db.Column(db.String(100))
    localizacion  = db.Column(db.String(100))
    responsable   = db.Column(db.String(100))
    ejecutado_por = db.Column(db.String(100))
    fecha         = db.Column(db.DateTime, default=datetime.now)
    estado        = db.Column(db.String(20), default='en_proceso')
    observaciones = db.Column(db.Text)
    items         = db.relationship('ItemInventario', backref='inventario', lazy=True)

class ItemInventario(db.Model):
    __tablename__ = 'items_inventario'

    id             = db.Column(db.Integer, primary_key=True)
    inventario_id  = db.Column(db.Integer, db.ForeignKey('inventarios.id'))
    serial         = db.Column(db.String(100))
    encontrado     = db.Column(db.Boolean, default=False)
    esperado       = db.Column(db.Boolean, default=True)
    observaciones  = db.Column(db.Text)
    cantidad_encontrada = db.Column(db.Integer, default=0)