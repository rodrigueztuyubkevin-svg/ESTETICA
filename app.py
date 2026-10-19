import os
from datetime import date
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from pymongo import MongoClient
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = 'aura_estetica_secret_key_super_segura'

# ------------------------------------------------------------------
# CONFIGURACIÓN DE MONGODB ATLAS
# ------------------------------------------------------------------
mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/estetica_db")
client = MongoClient(mongo_uri)
db = client.get_database("lumina_studio_db")

def init_db():
    """Inicializa servicios y productos base en MongoDB Atlas."""
    db.servicios.delete_many({"$or": [{"nombre": {"$exists": False}}, {"nombre": ""}, {"precio": {"$exists": False}}]})
    db.productos.delete_many({"$or": [{"nombre": {"$exists": False}}, {"nombre": ""}]})

    if db.servicios.count_documents({}) == 0:
        servicios_iniciales = [
            {
                'nombre': 'Limpieza Facial Profunda',
                'descripcion': 'Tratamiento purificante con exfoliación, extracción e hidratación intensiva para renovar tu piel.',
                'precio': 650.00,
                'duracion_min': 60,
                'tipo': 'servicio',
                'activo': 1,
                'imagen_url': 'https://images.unsplash.com/photo-1570172619644-dfd03ed5d881?auto=format&fit=crop&w=600&q=80'
            },
            {
                'nombre': 'Masaje Relajante Corporal',
                'descripcion': 'Terapia corporal con aceites esenciales diseñada para liberar tensión muscular y reducir el estrés.',
                'precio': 800.00,
                'duracion_min': 50,
                'tipo': 'servicio',
                'activo': 1,
                'imagen_url': 'https://images.unsplash.com/photo-1544161515-4ab6ce6db874?auto=format&fit=crop&w=600&q=80'
            }
        ]
        db.servicios.insert_many(servicios_iniciales)

    if db.productos.count_documents({}) == 0:
        productos_iniciales = [
            {
                'nombre': 'Sérum Facial Hidratante',
                'descripcion': 'Sérum concentrado con ácido hialurónico para una hidratación profunda y restauración cutánea.',
                'precio': 450.00,
                'stock': 15,
                'activo': 1,
                'imagen_url': 'https://images.unsplash.com/photo-1620916566398-39f1143ab7be?auto=format&fit=crop&w=600&q=80'
            },
            {
                'nombre': 'Exfoliante Corporal Botánico',
                'descripcion': 'Exfoliante suave con microcristales orgánicos y aceites esenciales de lavanda.',
                'precio': 380.00,
                'stock': 10,
                'activo': 1,
                'imagen_url': 'https://images.unsplash.com/photo-1556228720-195a672e8a03?auto=format&fit=crop&w=600&q=80'
            }
        ]
        db.productos.insert_many(productos_iniciales)

with app.app_context():
    init_db()

# ------------------------------------------------------------------
# DECORADORES DE AUTENTICACIÓN
# ------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash('Debes iniciar sesión para acceder a esta sección.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session or session.get('rol') != 'admin':
            flash('Acceso denegado. Se requieren permisos de administrador.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ------------------------------------------------------------------
# RUTAS PÚBLICAS Y DE AUTENTICACIÓN
# ------------------------------------------------------------------

@app.route('/')
def index():
    servicios_raw = list(db.servicios.find({"activo": 1, "tipo": "servicio"}).limit(6))
    servicios = []
    for s in servicios_raw:
        s['id'] = str(s['_id'])
        servicios.append(s)
    return render_template('index.html', servicios=servicios)

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        email = request.form.get('email', '').strip().lower()
        telefono = request.form.get('telefono', '').strip()
        raw_password = request.form.get('password', '')

        if not nombre or not email or not raw_password:
            flash('Por favor completa todos los campos obligatorios.', 'danger')
            return render_template('registro.html')

        if db.usuarios.find_one({"email": email}):
            flash('El correo electrónico ya está registrado. Intenta iniciar sesión.', 'danger')
        else:
            password_hash = generate_password_hash(raw_password)
            nuevo_usuario = {
                "nombre": nombre,
                "email": email,
                "telefono": telefono,
                "password": password_hash,
                "rol": "cliente"
            }
            resultado = db.usuarios.insert_one(nuevo_usuario)
            
            session['usuario_id'] = str(resultado.inserted_id)
            session['nombre'] = nombre
            session['rol'] = 'cliente'

            flash(f'¡Bienvenido/a, {nombre}! Tu cuenta se ha creado con éxito.', 'success')
            return redirect(url_for('perfil'))

    return render_template('registro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        usuario = db.usuarios.find_one({"email": email})

        if usuario and check_password_hash(usuario['password'], password):
            session['usuario_id'] = str(usuario['_id'])
            session['nombre'] = usuario['nombre']
            session['rol'] = usuario.get('rol', 'cliente')
            flash(f'¡Bienvenido de nuevo, {usuario["nombre"]}!', 'success')
            
            if usuario.get('rol') == 'admin':
                return redirect(url_for('admin_panel'))
            return redirect(url_for('perfil'))
        else:
            flash('Correo o contraseña incorrectos. Intenta de nuevo.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión correctamente.', 'info')
    return redirect(url_for('index'))

# ------------------------------------------------------------------
# RUTAS DE TIENDA, CARRITO Y PAGOS
# ------------------------------------------------------------------

@app.route('/productos')
def ver_productos():
    productos_raw = list(db.productos.find({"activo": 1}))
    productos = []
    for p in productos_raw:
        p['id'] = str(p['_id'])
        productos.append(p)
    return render_template('productos.html', productos=productos)

@app.route('/carrito/agregar/<producto_id>', methods=['POST'])
def agregar_al_carrito(producto_id):
    if 'carrito' not in session:
        session['carrito'] = {}

    carrito = session['carrito']
    prod = db.productos.find_one({"_id": ObjectId(producto_id)})
    if not prod:
        flash('Producto no encontrado.', 'danger')
        return redirect(url_for('ver_productos'))

    cantidad = int(request.form.get('cantidad', 1))

    if producto_id in carrito:
        carrito[producto_id] += cantidad
    else:
        carrito[producto_id] = cantidad

    session['carrito'] = carrito
    session.modified = True
    flash(f'¡{prod["nombre"]} agregado al carrito!', 'success')
    return redirect(url_for('ver_carrito'))

@app.route('/carrito')
def ver_carrito():
    carrito = session.get('carrito', {})
    items = []
    total = 0.0

    for prod_id, cantidad in carrito.items():
        try:
            p = db.productos.find_one({"_id": ObjectId(prod_id)})
            if p:
                subtotal = p['precio'] * cantidad
                total += subtotal
                items.append({
                    'id': str(p['_id']),
                    'nombre': p['nombre'],
                    'precio': p['precio'],
                    'imagen_url': p.get('imagen_url', ''),
                    'cantidad': cantidad,
                    'subtotal': subtotal
                })
        except Exception:
            continue

    return render_template('carrito.html', items=items, total=total)

@app.route('/carrito/eliminar/<producto_id>')
def eliminar_del_carrito(producto_id):
    carrito = session.get('carrito', {})
    if producto_id in carrito:
        del carrito[producto_id]
        session['carrito'] = carrito
        session.modified = True
        flash('Producto eliminado del carrito.', 'info')
    return redirect(url_for('ver_carrito'))

@app.route('/carrito/vaciar')
def vaciar_carrito():
    session['carrito'] = {}
    session.modified = True
    flash('Carrito vaciado.', 'info')
    return redirect(url_for('ver_carrito'))

@app.route('/carrito/pagar', methods=['POST'])
@login_required
def pagar_carrito():
    carrito = session.get('carrito', {})
    if not carrito:
        flash('Tu carrito está vacío.', 'warning')
        return redirect(url_for('ver_carrito'))

    # Descontar stock y registrar pedido
    for prod_id, cantidad in carrito.items():
        try:
            db.productos.update_one(
                {"_id": ObjectId(prod_id)},
                {"$inc": {"stock": -cantidad}}
            )
        except Exception:
            pass

    session['carrito'] = {}
    session.modified = True
    flash('¡Pago procesado con éxito! Tu pedido ha sido registrado en KAD.', 'success')
    return redirect(url_for('ver_productos'))

# ------------------------------------------------------------------
# RUTAS DE CLIENTE: PERFIL Y AGENDAMIENTO
# ------------------------------------------------------------------

@app.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    usuario_id = str(session['usuario_id'])

    if request.method == 'POST':
        alergias = request.form.get('alergias', '')
        condiciones_piel = request.form.get('condiciones_piel', '')
        padecimientos = request.form.get('padecimientos_especiales', '')
        embarazo = 1 if request.form.get('embarazo_lactancia') else 0
        silenciosa = 1 if request.form.get('cita_silenciosa') else 0
        notas = request.form.get('notas_adicionales', '')

        ficha_data = {
            "usuario_id": usuario_id,
            "alergias": alergias,
            "condiciones_piel": condiciones_piel,
            "padecimientos_especiales": padecimientos,
            "embarazo_lactancia": embarazo,
            "cita_silenciosa": silenciosa,
            "notas_adicionales": notas
        }

        db.fichas_salud.update_one(
            {"usuario_id": usuario_id},
            {"$set": ficha_data},
            upsert=True
        )
        flash('Tu ficha médica y preferencias se han guardado con éxito.', 'success')
        return redirect(url_for('perfil'))

    ficha = db.fichas_salud.find_one({"usuario_id": usuario_id})
    citas_raw = list(db.citas.find({"usuario_id": usuario_id}).sort("fecha_hora", -1))
    citas = []
    for c in citas_raw:
        try:
            srv = db.servicios.find_one({"_id": c.get("servicio_id")})
        except Exception:
            srv = None

        c['servicio_nombre'] = srv['nombre'] if srv and 'nombre' in srv else 'Tratamiento Estético'
        c['id'] = str(c['_id'])
        citas.append(c)

    try:
        obj_id = ObjectId(usuario_id)
    except Exception:
        obj_id = usuario_id

    usuario_info = db.usuarios.find_one({"$or": [{"_id": obj_id}, {"_id": usuario_id}]})

    return render_template('perfil.html', usuario=usuario_info, ficha_medica=ficha, citas=citas)

@app.route('/agendar', methods=['GET', 'POST'])
@login_required
def agendar():
    servicios_raw = list(db.servicios.find({"activo": 1, "tipo": "servicio"}))
    servicios = []
    for s in servicios_raw:
        s['id'] = str(s['_id'])
        servicios.append(s)

    especialistas_raw = list(db.especialistas.find({}))
    especialistas = []
    for e in especialistas_raw:
        e['id'] = str(e['_id'])
        especialistas.append(e)

    if request.method == 'POST':
        paso = request.form.get('paso', '1')
        
        if paso == '1':
            servicio_id = request.form.get('servicio_id')
            if not servicio_id:
                flash('Por favor selecciona un servicio para continuar.', 'warning')
                return render_template('agendar.html', paso=1, servicios=servicios, especialistas=especialistas)
            return render_template('agendar.html', paso=2, servicio_id=servicio_id, servicios=servicios, especialistas=especialistas)
        
        elif paso == '2':
            servicio_id = request.form.get('servicio_id')
            especialista_id = request.form.get('especialista_id', '0')
            hoy = date.today().strftime('%Y-%m-%d')
            return render_template('agendar.html', paso=3, servicio_id=servicio_id, especialista_id=especialista_id, hoy=hoy, servicios=servicios, especialistas=especialistas)
        
        elif paso == '3':
            servicio_id = request.form.get('servicio_id')
            especialista_id = request.form.get('especialista_id')
            fecha = request.form.get('fecha')
            hora = request.form.get('hora')
            
            if not fecha or not hora:
                flash('Por favor selecciona una fecha y hora válidas.', 'warning')
                hoy = date.today().strftime('%Y-%m-%d')
                return render_template('agendar.html', paso=3, servicio_id=servicio_id, especialista_id=especialista_id, hoy=hoy, servicios=servicios, especialistas=especialistas)
            
            try:
                srv = db.servicios.find_one({"_id": ObjectId(servicio_id)})
            except Exception:
                srv = db.servicios.find_one({"_id": servicio_id})

            if srv:
                srv['id'] = str(srv['_id'])

            return render_template('agendar.html', paso=4, servicio_id=servicio_id, especialista_id=especialista_id, fecha=fecha, hora=hora, servicio_info=srv, servicios=servicios, especialistas=especialistas)

        elif paso == '4':
            servicio_id = request.form.get('servicio_id')
            especialista_id = request.form.get('especialista_id')
            fecha = request.form.get('fecha')
            hora = request.form.get('hora')
            notas = request.form.get('notas', '')

            fecha_hora = f"{fecha} {hora}"
            
            try:
                serv_obj_id = ObjectId(servicio_id)
            except Exception:
                serv_obj_id = servicio_id

            try:
                esp_obj_id = ObjectId(especialista_id) if especialista_id and especialista_id != '0' else None
            except Exception:
                esp_obj_id = None

            nueva_cita = {
                "usuario_id": str(session['usuario_id']),
                "servicio_id": serv_obj_id,
                "especialista_id": esp_obj_id,
                "fecha_hora": fecha_hora,
                "notas_cliente": notas,
                "estado": "confirmada"
            }

            db.citas.insert_one(nueva_cita)
            flash('¡Tu cita ha sido agendada con éxito!', 'success')
            return redirect(url_for('perfil'))

    return render_template('agendar.html', servicios=servicios, especialistas=especialistas, paso=1)

# ------------------------------------------------------------------
# RUTAS DE ADMINISTRACIÓN (CRUD DE SERVICIOS Y PRODUCTOS)
# ------------------------------------------------------------------

@app.route('/admin')
@admin_required
def admin_panel():
    try:
        citas_raw = list(db.citas.find({}).sort("fecha_hora", 1))
        citas = []
        for c in citas_raw:
            u_id = c.get("usuario_id")
            u = None
            if u_id:
                try:
                    u_obj = ObjectId(u_id) if not isinstance(u_id, ObjectId) else u_id
                    u = db.usuarios.find_one({"$or": [{"_id": u_obj}, {"_id": u_id}]})
                except Exception:
                    u = db.usuarios.find_one({"_id": u_id})

            s = None
            if c.get("servicio_id"):
                try:
                    s_id = ObjectId(c.get("servicio_id")) if not isinstance(c.get("servicio_id"), ObjectId) else c.get("servicio_id")
                    s = db.servicios.find_one({"_id": s_id})
                except Exception:
                    s = db.servicios.find_one({"_id": c.get("servicio_id")})

            citas.append({
                "id": str(c["_id"]),
                "fecha_hora": c.get("fecha_hora", "Sin fecha"),
                "estado": c.get("estado", "pendiente"),
                "cliente_nombre": u["nombre"] if u and "nombre" in u else "Desconocido",
                "telefono": u.get("telefono", "") if u else "",
                "servicio_nombre": s["nombre"] if s and "nombre" in s else "Servicio"
            })

        catalogo_raw = list(db.servicios.find({}).sort([("tipo", 1), ("nombre", 1)]))
        catalogo = []
        for cat in catalogo_raw:
            cat['id'] = str(cat['_id'])
            catalogo.append(cat)

        productos_raw = list(db.productos.find({}).sort("nombre", 1))
        productos = []
        for p in productos_raw:
            p['id'] = str(p['_id'])
            productos.append(p)

        return render_template('admin.html', citas=citas, catalogo=catalogo, productos=productos)
    except Exception as e:
        flash(f'Error al cargar el panel: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/admin/servicio/nuevo', methods=['POST'])
@admin_required
def agregar_servicio():
    nombre = request.form.get('nombre', '').strip()
    descripcion = request.form.get('descripcion', '').strip()
    imagen_url = request.form.get('imagen_url', '').strip()
    try:
        precio = float(request.form.get('precio', 0))
    except ValueError:
        precio = 0.0
    try:
        duracion = int(request.form.get('duracion_min', 30))
    except ValueError:
        duracion = 30

    if nombre:
        nuevo_servicio = {
            "nombre": nombre,
            "descripcion": descripcion,
            "precio": precio,
            "duracion_min": duracion,
            "tipo": "servicio",
            "activo": 1,
            "imagen_url": imagen_url if imagen_url else "https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=600&q=80"
        }
        db.servicios.insert_one(nuevo_servicio)
        flash('Servicio agregado al catálogo correctamente.', 'success')
    else:
        flash('El nombre del servicio es obligatorio.', 'danger')
        
    return redirect(url_for('admin_panel'))

@app.route('/admin/servicio/editar/<servicio_id>', methods=['POST'])
@admin_required
def editar_servicio(servicio_id):
    nombre = request.form.get('nombre', '').strip()
    descripcion = request.form.get('descripcion', '').strip()
    imagen_url = request.form.get('imagen_url', '').strip()
    try:
        precio = float(request.form.get('precio', 0))
        duracion = int(request.form.get('duracion_min', 60))
    except ValueError:
        precio, duracion = 0.0, 60

    db.servicios.update_one(
        {"_id": ObjectId(servicio_id)},
        {"$set": {
            "nombre": nombre,
            "descripcion": descripcion,
            "precio": precio,
            "duracion_min": duracion,
            "imagen_url": imagen_url
        }}
    )
    flash('Servicio actualizado con éxito.', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/servicio/estado/<servicio_id>')
@admin_required
def cambiar_estado_servicio(servicio_id):
    try:
        srv = db.servicios.find_one({"_id": ObjectId(servicio_id)})
        if srv:
            nuevo_estado = 0 if srv.get("activo", 1) == 1 else 1
            db.servicios.update_one({"_id": ObjectId(servicio_id)}, {"$set": {"activo": nuevo_estado}})
            flash('El estado del servicio ha sido actualizado.', 'info')
    except Exception:
        flash('Error al actualizar el servicio.', 'danger')
    return redirect(url_for('admin_panel'))

@app.route('/admin/producto/nuevo', methods=['POST'])
@admin_required
def agregar_producto():
    nombre = request.form.get('nombre', '').strip()
    descripcion = request.form.get('descripcion', '').strip()
    imagen_url = request.form.get('imagen_url', '').strip()
    try:
        precio = float(request.form.get('precio', 0))
        stock = int(request.form.get('stock', 0))
    except ValueError:
        precio, stock = 0.0, 0

    if nombre:
        nuevo_prod = {
            "nombre": nombre,
            "descripcion": descripcion,
            "precio": precio,
            "stock": stock,
            "activo": 1,
            "imagen_url": imagen_url if imagen_url else "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?auto=format&fit=crop&w=600&q=80"
        }
        db.productos.insert_one(nuevo_prod)
        flash('Producto agregado con éxito al catálogo.', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/producto/editar/<producto_id>', methods=['POST'])
@admin_required
def editar_producto(producto_id):
    nombre = request.form.get('nombre', '').strip()
    descripcion = request.form.get('descripcion', '').strip()
    imagen_url = request.form.get('imagen_url', '').strip()
    try:
        precio = float(request.form.get('precio', 0))
        stock = int(request.form.get('stock', 0))
    except ValueError:
        precio, stock = 0.0, 0

    db.productos.update_one(
        {"_id": ObjectId(producto_id)},
        {"$set": {
            "nombre": nombre,
            "descripcion": descripcion,
            "precio": precio,
            "stock": stock,
            "imagen_url": imagen_url
        }}
    )
    flash('Producto actualizado con éxito.', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/producto/estado/<producto_id>')
@admin_required
def cambiar_estado_producto(producto_id):
    p = db.productos.find_one({"_id": ObjectId(producto_id)})
    if p:
        nuevo_estado = 0 if p.get("activo", 1) == 1 else 1
        db.productos.update_one({"_id": ObjectId(producto_id)}, {"$set": {"activo": nuevo_estado}})
        flash('Estado del producto actualizado.', 'info')
    return redirect(url_for('admin_panel'))

@app.route('/admin/cita/<cita_id>/<estado>')
@admin_required
def cambiar_estado_cita(cita_id, estado):
    if estado in ['confirmada', 'cancelada', 'completada']:
        try:
            db.citas.update_one({"_id": ObjectId(cita_id)}, {"$set": {"estado": estado}})
            flash(f'La cita ha sido marcada como {estado}.', 'info')
        except Exception:
            flash('No se pudo actualizar la cita.', 'danger')
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    app.run(debug=True)