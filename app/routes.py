import os
from flask import Blueprint, json, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_manager
from app import db, login_manager
from app.models import Equipo, Usuario, Rol, Permiso, RolPermiso
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import threading
from app.models import Equipo, Usuario, Rol, Permiso, RolPermiso
from app.models import Equipo, Usuario, Rol, Permiso, RolPermiso, Inventario, ItemInventario




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

def procesar_excel(archivo_bytes, app):
    with app.app_context():
        try:
            import io
            print("🔄 Iniciando importación...")
            df = pd.read_excel(io.BytesIO(archivo_bytes), engine='openpyxl')
            total = len(df)
            print(f"📋 Total filas: {total}")
            
            chunk_size = 500
            for i in range(0, total, chunk_size):
                chunk = df.iloc[i:i + chunk_size]
                for _, fila in chunk.iterrows():
                    serial = limpiar(fila.get('serial', ''))
                    if not serial:
                        continue
                    equipo = Equipo.query.filter_by(serial=serial).first()
                    if not equipo:
                        equipo = Equipo()
                    equipo.serial          = serial
                    equipo.codigo_producto = limpiar(fila.get('coD_PRODUCTO', ''))
                    equipo.propietario     = limpiar(fila.get('nombrE_PROPIETARIO', ''))
                    equipo.descripcion     = limpiar(fila.get('nombrE_PRODUCTO', ''))
                    equipo.marca           = limpiar(fila.get('nombrE_MARCA', ''))
                    equipo.referencia      = limpiar(fila.get('referencia', ''))
                    equipo.activo_placa    = limpiar(fila.get('numerO_ACTIVO', ''))
                    equipo.mac             = limpiar(fila.get('mac', ''))
                    equipo.estado          = limpiar(fila.get('estado', ''))
                    equipo.localizacion    = limpiar(fila.get('localizacion', ''))
                    equipo.bodega          = limpiar(fila.get('nombrE_BODEGA', ''))
                    equipo.centro_costos   = limpiar(fila.get('centrodecostos', ''))
                    equipo.codigo_bodega   = limpiar(fila.get('coD_BODEGA', ''))
                    db.session.add(equipo)
                db.session.commit()
                print(f"✅ Procesadas {min(i + chunk_size, total)}/{total} filas")
            print("✅ Importación completada")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error en importación: {e}")

@main.route('/importar', methods=['GET', 'POST'])
@login_required
@requiere_permiso('importar_excel')
def importar():
    if request.method == 'POST':
        archivo = request.files['archivo']
        if archivo:
            archivo_bytes = archivo.read()
            from flask import current_app
            app = current_app._get_current_object()
            hilo = threading.Thread(target=procesar_excel, args=(archivo_bytes, app))
            hilo.daemon = True
            hilo.start()
            flash('Importación iniciada ⏳ El inventario se actualizará en unos minutos.', 'success')
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

# ==================== MÓDULO DE INVENTARIOS ====================

@main.route('/inventarios')
@login_required
@requiere_permiso('gestionar_inventario')
def inventarios():
    inventarios = Inventario.query.order_by(Inventario.fecha.desc()).all()
    return render_template('inventarios.html', inventarios=inventarios)

@main.route('/inventario/nuevo', methods=['GET', 'POST'])
@login_required
@requiere_permiso('gestionar_inventario')
def nuevo_inventario():
    bodegas = db.session.query(Equipo.bodega).distinct().order_by(Equipo.bodega).all()
    bodegas = [b[0] for b in bodegas if b[0]]
    
    if request.method == 'POST':
        tipo        = request.form.get('tipo')
        bodega      = request.form.get('bodega')
        localizacion = request.form.get('localizacion', '')
        responsable = request.form.get('responsable')
        observaciones = request.form.get('observaciones', '')

        inventario = Inventario()
        inventario.tipo          = tipo
        inventario.bodega        = bodega
        inventario.localizacion  = localizacion
        inventario.responsable   = responsable
        inventario.ejecutado_por = current_user.nombre
        inventario.observaciones = observaciones
        inventario.estado        = 'en_proceso'

        db.session.add(inventario)
        db.session.commit()

        # Cargar equipos esperados según tipo
        if tipo == 'general':
            equipos = Equipo.query.filter_by(bodega=bodega).all()
        else:
            equipos = Equipo.query.filter_by(bodega=bodega, localizacion=localizacion).all()

        for equipo in equipos:
            item = ItemInventario()
            item.inventario_id = inventario.id
            item.serial        = equipo.serial
            item.encontrado    = False
            item.esperado      = True
            db.session.add(item)

        db.session.commit()
        flash(f'Inventario creado con {len(equipos)} equipos esperados.', 'success')
        return redirect(url_for('main.ejecutar_inventario', id=inventario.id))

    import json
    bodegas_json = json.dumps(bodegas)

    return render_template('nuevo_inventario.html', bodegas=bodegas, bodegas_json=bodegas_json)

@main.route('/inventario/<int:id>/ejecutar', methods=['GET', 'POST'])
@login_required
@requiere_permiso('gestionar_inventario')
def ejecutar_inventario(id):
    inventario = Inventario.query.get_or_404(id)
    
    if request.method == 'POST':
        serial = request.form.get('serial', '').strip().upper()
        if serial:
            item = ItemInventario.query.filter_by(
                inventario_id=id, serial=serial
            ).first()
            if item:
                item.encontrado = True
                db.session.commit()
                return {'status': 'ok', 'mensaje': f'Serial {serial} encontrado ✅'}
            else:
                # Serial no esperado - sobrante
                nuevo = ItemInventario()
                nuevo.inventario_id = id
                nuevo.serial        = serial
                nuevo.encontrado    = True
                nuevo.esperado      = False
                db.session.add(nuevo)
                db.session.commit()
                return {'status': 'sobrante', 'mensaje': f'Serial {serial} no estaba en la lista ⚠️'}

    items = ItemInventario.query.filter_by(inventario_id=id).all()
    encontrados = sum(1 for i in items if i.encontrado and i.esperado)
    faltantes   = sum(1 for i in items if not i.encontrado and i.esperado)
    sobrantes   = sum(1 for i in items if i.encontrado and not i.esperado)

    return render_template('ejecutar_inventario.html',
                           inventario=inventario,
                           items=items,
                           encontrados=encontrados,
                           faltantes=faltantes,
                           sobrantes=sobrantes)

@main.route('/inventario/<int:id>/finalizar', methods=['POST'])
@login_required
@requiere_permiso('gestionar_inventario')
def finalizar_inventario(id):
    inventario = Inventario.query.get_or_404(id)
    inventario.estado = 'finalizado'
    db.session.commit()
    flash('Inventario finalizado ✅', 'success')
    return redirect(url_for('main.reporte_inventario', id=id))

@main.route('/inventario/<int:id>/reporte')
@login_required
@requiere_permiso('gestionar_inventario')
def reporte_inventario(id):
    inventario = Inventario.query.get_or_404(id)
    items = ItemInventario.query.filter_by(inventario_id=id).all()
    encontrados = [i for i in items if i.encontrado and i.esperado]
    faltantes   = [i for i in items if not i.encontrado and i.esperado]
    sobrantes   = [i for i in items if i.encontrado and not i.esperado]
    return render_template('reporte_inventario.html',
                           inventario=inventario,
                           encontrados=encontrados,
                           faltantes=faltantes,
                           sobrantes=sobrantes)

@main.route('/api/localizaciones')
@login_required
def api_localizaciones():
    bodega = request.args.get('bodega', '')
    locs = db.session.query(Equipo.localizacion).filter_by(bodega=bodega).distinct().order_by(Equipo.localizacion).all()
    locs = [l[0] for l in locs if l[0]]
    return {'localizaciones': locs}

@main.route('/inventario/<int:id>/pdf')
@login_required
@requiere_permiso('gestionar_inventario')
def pdf_inventario(id):
    inventario = Inventario.query.get_or_404(id)
    items = ItemInventario.query.filter_by(inventario_id=id).all()
    encontrados = [i for i in items if i.encontrado and i.esperado]
    faltantes   = [i for i in items if not i.encontrado and i.esperado]
    sobrantes   = [i for i in items if i.encontrado and not i.esperado]

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    ancho, alto = letter

    # ENCABEZADO
    c.setFillColorRGB(0, 0.2, 0.4)
    c.rect(0, alto - 80, ancho, 80, fill=True, stroke=False)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(30, alto - 40, "TELEMÁTICA SAS - REPORTE DE INVENTARIO")
    c.setFont("Helvetica", 11)
    tipo_texto = "General" if inventario.tipo == "general" else "Cíclico"
    c.drawString(30, alto - 65, f"{tipo_texto} | {inventario.bodega}")

    # INFORMACIÓN
    c.setFillColorRGB(0, 0, 0)
    y = alto - 110
    c.setFont("Helvetica-Bold", 11)
    c.drawString(30, y, "INFORMACIÓN DEL INVENTARIO")
    c.line(30, y - 5, ancho - 30, y - 5)

    y -= 25
    c.setFont("Helvetica", 10)
    c.drawString(30, y, f"Responsable: {inventario.responsable}")
    c.drawString(300, y, f"Ejecutado por: {inventario.ejecutado_por}")
    y -= 18
    c.drawString(30, y, f"Fecha: {inventario.fecha.strftime('%d/%m/%Y %H:%M')}")
    c.drawString(300, y, f"Estado: {'Finalizado' if inventario.estado == 'finalizado' else 'En proceso'}")
    y -= 18
    if inventario.localizacion:
        c.drawString(30, y, f"Localización: {inventario.localizacion}")
        y -= 18
    if inventario.observaciones:
        c.drawString(30, y, f"Observaciones: {inventario.observaciones}")
        y -= 18

    # RESUMEN
    y -= 15
    c.setFont("Helvetica-Bold", 11)
    c.drawString(30, y, "RESUMEN")
    c.line(30, y - 5, ancho - 30, y - 5)
    y -= 25
    c.setFont("Helvetica", 10)
    c.drawString(30, y, f"Total esperados: {len(encontrados) + len(faltantes)}")
    c.drawString(200, y, f"Encontrados: {len(encontrados)}")
    c.drawString(350, y, f"Faltantes: {len(faltantes)}")
    c.drawString(460, y, f"Sobrantes: {len(sobrantes)}")

    def dibujar_tabla(titulo, items_lista, color_rgb, y_pos):
        if not items_lista:
            return y_pos
        y_pos -= 25
        c.setFont("Helvetica-Bold", 11)
        c.setFillColorRGB(*color_rgb)
        c.drawString(30, y_pos, titulo)
        c.setFillColorRGB(0, 0, 0)
        c.line(30, y_pos - 5, ancho - 30, y_pos - 5)
        y_pos -= 20
        c.setFont("Helvetica", 9)
        for i, item in enumerate(items_lista, 1):
            if y_pos < 50:
                c.showPage()
                y_pos = alto - 50
            c.drawString(30, y_pos, f"{i}.")
            c.drawString(55, y_pos, item.serial)
            y_pos -= 15
        return y_pos

    y = dibujar_tabla(f"FALTANTES ({len(faltantes)})", faltantes, (0.7, 0.1, 0.1), y)
    y = dibujar_tabla(f"SOBRANTES ({len(sobrantes)})", sobrantes, (0.6, 0.4, 0), y)
    y = dibujar_tabla(f"ENCONTRADOS ({len(encontrados)})", encontrados, (0.1, 0.5, 0.2), y)

    c.save()
    buffer.seek(0)
    return send_file(buffer, mimetype='application/pdf',
                     download_name=f'inventario_{inventario.id}_{inventario.bodega}.pdf')

