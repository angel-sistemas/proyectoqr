import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_manager
from app import db, login_manager
from app.models import Equipo, Usuario, Rol, Permiso, RolPermiso
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash



main = Blueprint('main', __name__)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))

from functools import wraps
def requiere_permiso(permiso):
    def decorador(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('main.login'))
            if not current_user.tiene_permiso(permiso):
                flash('No tiene permiso para acceder a esta sección.', 'error')
                return redirect(url_for('main.login'))
            return f(*args, **kwargs)
        return wrapper
    return decorador


@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email_usuario = request.form.get('email')
        password_usuario = request.form.get('password')
        
        usuario = Usuario.query.filter_by(email=email_usuario, activo=True).first()
        
        if usuario is None:
            flash('Email o contraseña incorrectos.', 'error')
            return render_template('login.html')
        
        if check_password_hash(usuario.password_hash, password_usuario):
            login_user(usuario)
            return redirect(url_for('main.index'))
        
        flash('Email o contraseña incorrectos.', 'error')
    
    return render_template('login.html')

@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))

@main.route('/')
@login_required
@requiere_permiso('consultar_equipos')
def index():
    pagina = request.args.get('pagina', 1, type=int)
    por_pagina = request.args.get('por_pagina', 50, type=int)
    busqueda = request.args.get('busqueda', '')
    bodega = request.args.get('bodega', '')
    marca = request.args.get('marca', '')

    query = Equipo.query
    if busqueda:
        query = query.filter(
            db.or_(
                Equipo.serial.ilike(f'%{busqueda}%'),
                Equipo.descripcion.ilike(f'%{busqueda}%')
            )
        )
    if bodega:
        query = query.filter(
            db.or_(
                Equipo.bodega.ilike(f'%{bodega}%'),
                Equipo.codigo_bodega.ilike(f'%{bodega}%')
            )
        )
    if marca:
        query = query.filter(Equipo.marca == marca)
    total = query.count()

    if por_pagina == 0:
        equipos = query.all()
        paginas = 1
        pagina = 1
    else:
        paginacion = query.paginate(page=pagina, per_page=por_pagina, error_out=False)
        equipos = paginacion.items
        paginas = paginacion.pages

    bodegas = db.session.query(Equipo.bodega).distinct().order_by(Equipo.bodega).all()
    marcas = db.session.query(Equipo.marca).distinct().order_by(Equipo.marca).all()

    return render_template('index.html',
        equipos=equipos,
        total=total,
        pagina=pagina,
        paginas=paginas,
        por_pagina=por_pagina,
        busqueda=busqueda,
        bodega=bodega,
        marca=marca,
        bodegas=bodegas,
        marcas=marcas
    )

def limpiar(valor):
    v = str(valor).strip()
    if v.lower() in ('nan', 'none', '', 'nat'):
        return ''
    return v

@main.route('/importar', methods=['GET', 'POST'])
@login_required
@requiere_permiso('importar_excel')
def importar():
    if request.method == 'POST':
        archivo = request.files['archivo']
        if archivo:
            df = pd.read_excel(archivo, engine='openpyxl')
            for _, fila in df.iterrows():
                equipo = Equipo.query.filter_by(
                    serial=str(fila.get('serial', ''))
                ).first()

                if not equipo:
                    equipo = Equipo()

                equipo.serial             = str(fila.get('serial', ''))
                equipo.codigo_producto    = str(fila.get('coD_PRODUCTO', ''))
                equipo.propietario        = str(fila.get('nombrE_PROPIETARIO', ''))
                equipo.descripcion        = str(fila.get('nombrE_PRODUCTO', ''))
                equipo.marca              = str(fila.get('nombrE_MARCA', ''))
                equipo.referencia         = str(fila.get('referencia', ''))
                equipo.activo_placa       = str(fila.get('numerO_ACTIVO', ''))
                equipo.mac                = str(fila.get('mac', ''))
                equipo.estado             = str(fila.get('estado', ''))
                equipo.localizacion       = str(fila.get('localizacion', ''))
                equipo.bodega             = str(fila.get('nombrE_BODEGA', ''))
                equipo.centro_costos      = str(fila.get('centrodecostos', ''))
                equipo.codigo_bodega      = str(fila.get('coD_BODEGA'))

                db.session.add(equipo)

            db.session.commit()
            flash('Importacion exitosa ✅', 'succes')
            return redirect(url_for('main.index'))
            
    return render_template('importar.html')

@main.route('/equipo/<serial>')
@login_required
@requiere_permiso('ver_equipo')
def ver_equipo(serial):
    equipo = Equipo.query.filter_by(serial=serial).first_or_404()
    return render_template('equipo.html', equipo=equipo)

import qrcode
import io
from flask import send_file

@main.route('/qr/<serial>')
@login_required
@requiere_permiso('ver_equipo')
def generar_qr(serial):
    equipo = Equipo.query.filter_by(serial=serial).first_or_404()

    from flask import request as flask_request
    host = flask_request.host
    url_completa = f'http://{host}/equipo/{serial}'
    url_serial = serial

    qr_completo = qrcode.make(url_completa)
    qr_serial = qrcode.make(url_serial)

    import os
    carpeta_qr = os.path.join(os.getcwd(), 'static', 'qr')
    os.makedirs(carpeta_qr, exist_ok=True)
    qr_completo.save(os.path.join(carpeta_qr, f'completo_{serial}.png'))
    qr_serial.save(os.path.join(carpeta_qr, f'serial_{serial}.png'))

    return render_template('qr.html', equipo=equipo, serial=serial)

@main.route('/serial/<serial>')
@login_required
@requiere_permiso('escanar_qr')
def ver_serial(serial):
    equipo = Equipo.query.filter_by(serial=serial).first_or_404()
    return render_template('serial.html', equipo=equipo)

import requests as http_requests

@main.route('/imprimir')
@login_required
@requiere_permiso('generar_pdf')
def imprimir():
    return render_template('imprimir.html')

@main.route('/buscar-imagen/<serial>')
@login_required
@requiere_permiso('ver_equipo')
def buscar_imagen(serial):
    equipo = Equipo.query.filter_by(serial=serial).first_or_404()
    
    query = f"{equipo.marca} {equipo.referencia}"
    
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            resultados = list(ddgs.images(query, max_results=1))
            print(" q   uery:", query)
            print("Resultados:", resultados)
        
        if resultados:
            imagen_url = resultados[0]['image']
            img_response = http_requests.get(imagen_url, timeout=10)
            
            if img_response.status_code == 200:
                nombre_archivo = f"{serial}.jpg"
                os.makedirs(os.path.join(os.getcwd(), 'static', 'img', 'equipos'), exist_ok=True)
                ruta = os.path.join(os.getcwd(), 'static', 'img', 'equipos', nombre_archivo)
                with open(ruta, 'wb') as f:
                    f.write(img_response.content)
                equipo.imagen_path = nombre_archivo
                db.session.commit()
                return jsonify({'status': 'ok', 'imagen': nombre_archivo})
    except Exception as e:
        print("Error:", e)
        return jsonify({'status': 'error', 'mensaje': str(e)})
    
    return jsonify({'status': 'no_encontrada'})

@main.route('/pdf-multiple')
@login_required
@requiere_permiso('generar_pdf')
def pdf_multiple():
    seriales = request.args.getlist('seriales')
    
    if not seriales:
        return 'No se proporcionaron seriales', 400
    
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    ancho_hoja, alto_hoja = letter
    
    etiqueta_ancho = 6*cm
    etiqueta_alto = 3*cm
    margen_x = 1*cm
    margen_y = 1*cm
    
    columnas = int((ancho_hoja - 2*margen_x) / etiqueta_ancho)
    filas = int((alto_hoja - 2*margen_y) / etiqueta_alto)
    
    col = 0
    fila = 0
    
    for serial in seriales:
        equipo = Equipo.query.filter_by(serial=serial).first()
        if not equipo:
            continue
        
        # Generar QR si no existen
        carpeta_qr = os.path.join(os.getcwd(), 'static', 'qr')
        qr_completo_path = os.path.join(carpeta_qr, f'completo_{serial}.png')
        qr_serial_path = os.path.join(carpeta_qr, f'serial_{serial}.png')
        
        if not os.path.exists(qr_completo_path):
            from flask import request as flask_request
            host = flask_request.host
            url_completa = f'http://{host}/equipo/{serial}'
            qr = qrcode.make(url_completa)
            qr.save(qr_completo_path)
        
        if not os.path.exists(qr_serial_path):
            qr = qrcode.make(serial)
            qr.save(qr_serial_path)
        
        # Calcular posición de la etiqueta
        x = margen_x + col * etiqueta_ancho
        y = alto_hoja - margen_y - (fila + 1) * etiqueta_alto
        
        # Borde de la etiqueta
        c.setStrokeColorRGB(0.8, 0.8, 0.8)
        c.rect(x, y, etiqueta_ancho, etiqueta_alto)
        
        # Serial
        c.setFont("Helvetica-Bold", 5)
        c.setFillColorRGB(0, 0, 0)
        c.drawString(x + 0.2*cm, y + etiqueta_alto - 0.4*cm, serial[:25])
        
        # Descripción
        c.setFont("Helvetica", 4)
        descripcion = str(equipo.descripcion)[:35] if equipo.descripcion else ''
        c.drawString(x + 0.2*cm, y + etiqueta_alto - 0.7*cm, descripcion)
        
        # QR completo
        if os.path.exists(qr_completo_path):
            c.drawImage(qr_completo_path, x + 0.2*cm, y + 0.4*cm, width=1*cm, height=1*cm)
            c.setFont("Helvetica", 3.5)
            c.drawString(x + 0.2*cm, y + 0.2*cm, "Info")
        
        # QR serial
        if os.path.exists(qr_serial_path):
            c.drawImage(qr_serial_path, x + 1.5*cm, y + 0.4*cm, width=1*cm, height=1*cm)
            c.setFont("Helvetica", 3.5)
            c.drawString(x + 1.5*cm, y + 0.2*cm, "Serial")
        
        # Siguiente posición
        col += 1
        if col >= columnas:
            col = 0
            fila += 1
            if fila >= filas:
                c.showPage()
                fila = 0
    
    c.save()
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name='etiquetas_qr.pdf'
    )

@main.route('/usuarios')
@login_required
@requiere_permiso('gestionar_usuarios')
def lista_usuarios():
    usuarios_data = db.session.execute(
        db.select(Usuario, Rol).join(Rol, Usuario.rol_id == Rol.id)
    ).all()
    
    usuarios = []
    for u, r in usuarios_data:
        usuarios.append({
            'id': u.id,
            'nombre': u.nombre,
            'email': u.email,
            'rol_id': u.rol_id,
            'rol_nombre': r.nombre,
            'activo': u.activo
        })
    
    return render_template('usuarios.html', usuarios=usuarios)

@main.route('/usuarios/nuevo', methods=['GET', 'POST'])
@login_required
@requiere_permiso('gestionar_usuarios')
def nuevo_usuario():
    roles = Rol.query.all()
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        email_u = request.form.get('email')
        password_u = request.form.get('password')
        rol_id = request.form.get('rol_id')
        activo = request.form.get('activo') == '1'
        
        usuario = Usuario(
            nombre=nombre,
            email=email_u,
            password_hash=generate_password_hash(password_u),
            rol_id=rol_id,
            activo=activo
        )
        db.session.add(usuario)
        db.session.commit()
        flash('Usuario creado exitosamente ✅', 'success')
        return redirect(url_for('main.lista_usuarios'))
    
    return render_template('usuario_form.html', usuario=None, roles=roles)

@main.route('/usuarios/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@requiere_permiso('gestionar_usuarios')
def editar_usuario(id):
    usuario = db.session.get(Usuario, id)
    roles = Rol.query.all()
    
    if request.method == 'POST':
        usuario.nombre = request.form.get('nombre')
        usuario.email = request.form.get('email')
        usuario.rol_id = request.form.get('rol_id')
        usuario.activo = request.form.get('activo') == '1'
        
        password_u = request.form.get('password')
        if password_u:
            usuario.password_hash = generate_password_hash(password_u)
        
        db.session.commit()
        flash('Usuario actualizado exitosamente ✅', 'success')
        return redirect(url_for('main.lista_usuarios'))
    
    return render_template('usuario_form.html', usuario=usuario, roles=roles)

@main.route('/usuarios/eliminar/<int:id>')
@login_required
@requiere_permiso('gestionar_usuarios')
def eliminar_usuario(id):
    usuario = db.session.get(Usuario, id)
    db.session.delete(usuario)
    db.session.commit()
    flash('Usuario eliminado ✅', 'success')
    return redirect(url_for('main.lista_usuarios'))

