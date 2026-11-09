import os
from datetime import datetime, date, timedelta, timezone
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from pymongo import MongoClient, ReturnDocument
from bson.objectid import ObjectId
import traceback
import uuid
import random
import string

app = Flask(__name__)
app.secret_key = 'aura_estetica_secret_key_super_segura'

# ------------------------------------------------------------------
# CONFIGURACIÓN DE MONGODB ATLAS
# ------------------------------------------------------------------
mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/estetica_db")
client = MongoClient(mongo_uri)
db = client.get_database("lumina_studio_db")

DURACION_RESERVA_MINUTOS = 5

def ahora_utc():
    # Retornamos la fecha sin zona horaria para que coincida con lo que guarda MongoDB
    return datetime.now(timezone.utc).replace(tzinfo=None)

def obtener_reserva_id():
    if not session.get("reserva_id"):
        session["reserva_id"] = uuid.uuid4().hex
    return session["reserva_id"]

def init_db():
    try:
        db.servicios.delete_many({"$or": [{"nombre": {"$exists": False}}, {"nombre": ""}, {"precio": {"$exists": False}}]})
        db.productos.delete_many({"$or": [{"nombre": {"$exists": False}}, {"nombre": ""}]})

        # Crear índice único para evitar horarios duplicados
        try:
            db.horarios.create_index(
                [("especialista_id", 1), ("fecha", 1), ("hora", 1)],
                unique=True,
                name="horario_unico"
            )
        except Exception as e:
            print("Índice ya creado o error:", e)

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
                }
            ]
            db.productos.insert_many(productos_iniciales)
    except Exception as e:
        print(f"Error en init_db: {e}")

with app.app_context():
    init_db()

# ------------------------------------------------------------------
# GENERADOR DE FOLIO DE TICKET
# ------------------------------------------------------------------
def generar_folio_ticket():
    fecha_str = datetime.now().strftime("%Y%m%d")
    aleatorio = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"KAD-{fecha_str}-{aleatorio}"

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
# RUTAS PÚBLICAS Y AUTENTICACIÓN
# ------------------------------------------------------------------

@app.route('/')
def index():
    try:
        servicios_raw = list(db.servicios.find({"activo": 1, "tipo": "servicio"}).limit(6))
        servicios = []
        for s in servicios_raw:
            s['id'] = str(s['_id'])
            servicios.append(s)
    except Exception:
        servicios = []
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
# RUTAS DE TIENDA Y CARRITO
# ------------------------------------------------------------------

@app.route('/productos')
def ver_productos():
    try:
        productos_raw = list(db.productos.find({"activo": 1}))
        productos = []
        for p in productos_raw:
            p['id'] = str(p['_id'])
            productos.append(p)
    except Exception:
        productos = []
    return render_template('productos.html', productos=productos)

@app.route('/carrito/agregar/<producto_id>', methods=['POST'])
def agregar_al_carrito(producto_id):
    if 'carrito' not in session:
        session['carrito'] = {}

    carrito = session['carrito']
    try:
        prod = db.productos.find_one({"_id": ObjectId(producto_id)})
    except Exception:
        prod = None

    if not prod:
        flash('Producto no encontrado.', 'danger')
        return redirect(url_for('ver_productos'))
        
    if prod.get('stock', 0) <= 0:
        flash('Lo sentimos, este producto está agotado.', 'warning')
        return redirect(url_for('ver_productos'))

    cantidad = int(request.form.get('cantidad', 1))
    
    cantidad_actual_en_carrito = carrito.get(producto_id, 0)
    if cantidad_actual_en_carrito + cantidad > prod.get('stock', 0):
        flash(f'Solo quedan {prod.get("stock")} unidades de {prod["nombre"]}.', 'warning')
        return redirect(url_for('ver_carrito'))

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
                subtotal = float(p['precio']) * int(cantidad)
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

    productos_pedido = []
    total_pedido = 0.0

    for prod_id, cantidad in carrito.items():
        try:
            p = db.productos.find_one({"_id": ObjectId(prod_id)})
            if not p:
                continue
                
            producto_actualizado = db.productos.find_one_and_update(
                {"_id": ObjectId(prod_id), "stock": {"$gte": cantidad}},
                {"$inc": {"stock": -cantidad}},
                return_document=ReturnDocument.AFTER
            )
            
            if producto_actualizado:
                subtotal = float(producto_actualizado['precio']) * int(cantidad)
                total_pedido += subtotal
                productos_pedido.append({
                    "producto_id": str(producto_actualizado['_id']),
                    "nombre": producto_actualizado['nombre'],
                    "precio": producto_actualizado['precio'],
                    "cantidad": cantidad,
                    "subtotal": subtotal
                })
                
                if producto_actualizado.get('stock', 0) <= 0:
                    db.productos.update_one(
                        {"_id": ObjectId(prod_id)},
                        {"$set": {"activo": 0}}
                    )
            else:
                flash(f'No hay suficiente stock de un producto en tu carrito.', 'danger')
                return redirect(url_for('ver_carrito'))
                
        except Exception as e:
            print(f"Error al procesar el pago: {e}")
            flash('Error al procesar el pago.', 'danger')
            return redirect(url_for('ver_carrito'))

    fecha_actual = datetime.now()
    
    nuevo_pedido = {
        "usuario_id": str(session['usuario_id']),
        "cliente_nombre": session.get('nombre', 'Cliente'),
        "productos": productos_pedido,
        "total": total_pedido,
        "estado": "pendiente de preparación",
        "fecha": fecha_actual.strftime('%Y-%m-%d %H:%M')
    }
    resultado_pedido = db.pedidos.insert_one(nuevo_pedido)
    
    nuevo_ticket = {
        "folio": generar_folio_ticket(),
        "pedido_id": str(resultado_pedido.inserted_id),
        "usuario_id": str(session['usuario_id']),
        "cliente_nombre": session.get('nombre', 'Cliente'),
        "productos": productos_pedido,
        "total": total_pedido,
        "fecha_emision": fecha_actual
    }
    db.tickets.insert_one(nuevo_ticket)

    session['carrito'] = {}
    session.modified = True
    flash('¡Pago procesado con éxito! Tu pedido ha sido enviado a preparación. Revisa tu ticket en tu perfil.', 'success')
    return redirect(url_for('perfil'))

# ------------------------------------------------------------------
# RUTAS DE CLIENTE
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
    try:
        citas_raw = list(db.citas.find({"usuario_id": usuario_id}).sort("fecha_hora", -1))
    except Exception:
        citas_raw = []

    citas = []
    for c in citas_raw:
        try:
            srv = db.servicios.find_one({"_id": c.get("servicio_id")})
        except Exception:
            srv = None
        c['servicio_nombre'] = srv['nombre'] if srv and 'nombre' in srv else 'Tratamiento Estético'
        c['id'] = str(c['_id'])
        citas.append(c)

    tickets_raw = list(db.tickets.find({"usuario_id": usuario_id}).sort("fecha_emision", -1))
    tickets = []
    for t in tickets_raw:
        t['id'] = str(t['_id'])
        tickets.append(t)

    try:
        obj_id = ObjectId(usuario_id)
    except Exception:
        obj_id = usuario_id

    usuario_info = db.usuarios.find_one({"$or": [{"_id": obj_id}, {"_id": usuario_id}]})

    return render_template('perfil.html', usuario=usuario_info, ficha_medica=ficha, citas=citas, tickets=tickets)

@app.route('/agendar', methods=['GET', 'POST'])
@login_required
def agendar():
    try:
        servicios_raw = list(db.servicios.find({"activo": 1, "tipo": "servicio"}))
    except Exception:
        servicios_raw = []
    servicios = []
    for s in servicios_raw:
        s['id'] = str(s['_id'])
        servicios.append(s)

    try:
        especialistas_raw = list(db.especialistas.find({"$or": [{"activo": 1}, {"activo": {"$exists": False}}]}))
    except Exception:
        especialistas_raw = []
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
            return redirect(url_for('reservar_horario'))

    return render_template('agendar.html', servicios=servicios, especialistas=especialistas, paso=1)

# ------------------------------------------------------------------
# RESERVA TEMPORAL
# ------------------------------------------------------------------

@app.route('/reservar_horario', methods=['POST'])
@login_required
def reservar_horario():
    especialista_id = request.form.get('especialista_id')
    fecha = request.form.get('fecha')
    hora = request.form.get('hora')
    servicio_id = request.form.get('servicio_id')

    if not (fecha and hora):
        flash('Faltan datos para reservar.', 'danger')
        return redirect(url_for('agendar'))

    esp_obj_id = ObjectId(especialista_id) if especialista_id and especialista_id != '0' else None

    try:
        nuevo_horario = {
            "especialista_id": esp_obj_id,
            "fecha": fecha,
            "hora": hora,
            "estado": "reservado",
            "reserva_id": obtener_reserva_id(),
            "usuario_id": session['usuario_id'],
            "servicio_id": ObjectId(servicio_id),
            "vence_en": ahora_utc() + timedelta(minutes=DURACION_RESERVA_MINUTOS)
        }
        
        resultado = db.horarios.insert_one(nuevo_horario)
        flash('¡Horario apartado por 5 minutos! Por favor, confirma tu cita.', 'success')
        return redirect(url_for('confirmar_reserva', horario_id=str(resultado.inserted_id)))
        
    except Exception as e:
        if "duplicate key error" in str(e).lower():
            horario_existente = db.horarios.find_one({
                "especialista_id": esp_obj_id,
                "fecha": fecha,
                "hora": hora,
                "vence_en": {"$lte": ahora_utc()}
            })
            
            if horario_existente:
                db.horarios.update_one(
                    {"_id": horario_existente["_id"]},
                    {"$set": {
                        "reserva_id": obtener_reserva_id(),
                        "usuario_id": session['usuario_id'],
                        "servicio_id": ObjectId(servicio_id),
                        "vence_en": ahora_utc() + timedelta(minutes=DURACION_RESERVA_MINUTOS)
                    }}
                )
                flash('El horario anterior venció. ¡Lo hemos apartado para ti!', 'success')
                return redirect(url_for('confirmar_reserva', horario_id=str(horario_existente["_id"])))
            else:
                flash('Lo sentimos, otra persona acaba de apartar este horario. Elige otro.', 'danger')
                return redirect(url_for('agendar'))
        else:
            print(f"Error al reservar: {e}")
            flash('Ocurrió un error al procesar tu reserva.', 'danger')
            return redirect(url_for('agendar'))

@app.route('/confirmar_reserva/<horario_id>', methods=['GET', 'POST'])
@login_required
def confirmar_reserva(horario_id):
    horario = db.horarios.find_one({
        "_id": ObjectId(horario_id),
        "reserva_id": obtener_reserva_id()
    })
    
    if not horario:
        flash('La reserva no existe o no te pertenece.', 'danger')
        return redirect(url_for('agendar'))
        
    if horario['vence_en'] <= ahora_utc():
        flash('Tu tiempo de reserva ha expirado. El horario se ha liberado.', 'warning')
        db.horarios.delete_one({"_id": horario["_id"]})
        return redirect(url_for('agendar'))

    if request.method == 'POST':
        notas = request.form.get('notas', '')
        fecha_hora = f"{horario['fecha']} {horario['hora']}"
        
        nueva_cita = {
            "usuario_id": str(session['usuario_id']),
            "servicio_id": horario['servicio_id'],
            "especialista_id": horario['especialista_id'],
            "fecha_hora": fecha_hora,
            "notas_cliente": notas,
            "estado": "confirmada"
        }
        db.citas.insert_one(nueva_cita)
        
        db.horarios.delete_one({"_id": horario["_id"]})
        
        flash('¡Tu cita ha sido confirmada con éxito!', 'success')
        return redirect(url_for('perfil'))

    return render_template('confirmar_reserva.html', horario=horario)

@app.route('/cancelar_reserva/<horario_id>')
@login_required
def cancelar_reserva(horario_id):
    resultado = db.horarios.delete_one({
        "_id": ObjectId(horario_id),
        "reserva_id": obtener_reserva_id()
    })
    
    if resultado.deleted_count > 0:
        flash('Reserva cancelada. El horario está libre de nuevo.', 'info')
    else:
        flash('No se pudo cancelar la reserva.', 'danger')
        
    return redirect(url_for('agendar'))

# ------------------------------------------------------------------
# PANEL DE ADMINISTRACIÓN
# ------------------------------------------------------------------

@app.route('/admin')
@admin_required
def admin_panel():
    try:
        citas = []
        catalogo = []
        productos = []
        pedidos = []
        especialistas = []
        tickets = []

        try:
            for t in db.tickets.find({}).sort("fecha_emision", -1):
                t['id'] = str(t['_id'])
                tickets.append(t)

            for esp in db.especialistas.find({}):
                esp['id'] = str(esp['_id'])
                especialistas.append(esp)

            for c in db.citas.find({}):
                u_id = c.get("usuario_id")
                u = None
                if u_id:
                    try:
                        u_obj = ObjectId(u_id) if not isinstance(u_id, ObjectId) else u_id
                        u = db.usuarios.find_one({"$or": [{"_id": u_obj}, {"_id": u_id}]})
                    except Exception:
                        pass

                s = None
                if c.get("servicio_id"):
                    try:
                        s_id = ObjectId(c.get("servicio_id")) if not isinstance(c.get("servicio_id"), ObjectId) else c.get("servicio_id")
                        s = db.servicios.find_one({"_id": s_id})
                    except Exception:
                        pass
                
                esp_cita = None
                esp_id = c.get("especialista_id")
                if esp_id:
                    try:
                        esp_obj = ObjectId(esp_id) if not isinstance(esp_id, ObjectId) else esp_id
                        esp_cita = db.especialistas.find_one({"_id": esp_obj})
                    except Exception:
                        pass

                citas.append({
                    "id": str(c["_id"]),
                    "fecha_hora": c.get("fecha_hora", "Sin fecha"),
                    "estado": c.get("estado", "pendiente"),
                    "cliente_nombre": u["nombre"] if u and "nombre" in u else "Desconocido",
                    "telefono": u.get("telefono", "") if u else "",
                    "servicio_nombre": s["nombre"] if s and "nombre" in s else "Servicio",
                    "especialista_nombre": esp_cita["nombre"] if esp_cita and "nombre" in esp_cita else "Cualquiera",
                    "notas_cliente": c.get("notas_cliente", "Sin notas")
                })
        except Exception as e:
            print(f"Error procesando citas: {e}")

        try:
            for cat in db.servicios.find({}):
                cat['id'] = str(cat['_id'])
                catalogo.append(cat)
        except Exception as e:
            print(f"Error procesando servicios: {e}")

        try:
            for p in db.productos.find({}):
                p['id'] = str(p['_id'])
                productos.append(p)
        except Exception as e:
            print(f"Error procesando productos: {e}")

        try:
            for ped in db.pedidos.find({}):
                ped['id'] = str(ped['_id'])
                pedidos.append(ped)
        except Exception as e:
            print(f"Error procesando pedidos: {e}")

        return render_template('admin.html', citas=citas, catalogo=catalogo, productos=productos, pedidos=pedidos, especialistas=especialistas, tickets=tickets)
    
    except Exception as e:
        error_msg = traceback.format_exc()
        return f"<h3>Ocurrió un error en el servidor (500):</h3><pre>{error_msg}</pre>", 500

@app.route('/admin/especialista/nuevo', methods=['POST'])
@admin_required
def agregar_especialista():
    nombre = request.form.get('nombre', '').strip()
    especialidad = request.form.get('especialidad', '').strip()
    imagen_url = request.form.get('imagen_url', '').strip()

    if nombre:
        nuevo_especialista = {
            "nombre": nombre,
            "especialidad": especialidad,
            "imagen_url": imagen_url if imagen_url else "https://images.unsplash.com/photo-1595152772835-219674b2a8a6?auto=format&fit=crop&w=600&q=80",
            "activo": 1
        }
        db.especialistas.insert_one(nuevo_especialista)
        flash('Especialista agregado correctamente.', 'success')
    else:
        flash('El nombre del especialista es obligatorio.', 'danger')
    return redirect(url_for('admin_panel'))

@app.route('/admin/especialista/estado/<especialista_id>')
@admin_required
def cambiar_estado_especialista(especialista_id):
    try:
        esp = db.especialistas.find_one({"_id": ObjectId(especialista_id)})
        if esp:
            nuevo_estado = 0 if esp.get("activo", 1) == 1 else 1
            db.especialistas.update_one({"_id": ObjectId(especialista_id)}, {"$set": {"activo": nuevo_estado}})
            flash('Estado del especialista actualizado.', 'info')
    except Exception:
        pass
    return redirect(url_for('admin_panel'))

@app.route('/admin/pedido/estado/<pedido_id>/<estado>')
@admin_required
def cambiar_estado_pedido(pedido_id, estado):
    if estado in ['pendiente de preparación', 'en camino', 'entregado']:
        try:
            db.pedidos.update_one({"_id": ObjectId(pedido_id)}, {"$set": {"estado": estado}})
            flash(f'Estado del pedido actualizado a: {estado}', 'success')
        except Exception as e:
            print(f"Error al cambiar estado: {e}")
            flash('No se pudo actualizar el estado del pedido.', 'danger')
    return redirect(url_for('admin_panel'))

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
        flash('Servicio agregado correctamente.', 'success')
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

    try:
        db.servicios.update_one(
            {"_id": ObjectId(servicio_id)},
            {"$set": {"nombre": nombre, "descripcion": descripcion, "precio": precio, "duracion_min": duracion, "imagen_url": imagen_url}}
        )
        flash('Servicio actualizado con éxito.', 'success')
    except Exception:
        flash('Error al editar el servicio.', 'danger')

    return redirect(url_for('admin_panel'))

@app.route('/admin/servicio/estado/<servicio_id>')
@admin_required
def cambiar_estado_servicio(servicio_id):
    try:
        srv = db.servicios.find_one({"_id": ObjectId(servicio_id)})
        if srv:
            nuevo_estado = 0 if srv.get("activo", 1) == 1 else 1
            db.servicios.update_one({"_id": ObjectId(servicio_id)}, {"$set": {"activo": nuevo_estado}})
            flash('Estado del servicio actualizado.', 'info')
    except Exception:
        pass
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
        estado_activo = 1 if stock > 0 else 0
        nuevo_prod = {
            "nombre": nombre,
            "descripcion": descripcion,
            "precio": precio,
            "stock": stock,
            "activo": estado_activo,
            "imagen_url": imagen_url if imagen_url else "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?auto=format&fit=crop&w=600&q=80"
        }
        db.productos.insert_one(nuevo_prod)
        flash('Producto agregado con éxito.', 'success')
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

    try:
        nuevo_estado = 1 if stock > 0 else 0
        db.productos.update_one(
            {"_id": ObjectId(producto_id)},
            {"$set": {
                "nombre": nombre, 
                "descripcion": descripcion, 
                "precio": precio, 
                "stock": stock, 
                "imagen_url": imagen_url,
                "activo": nuevo_estado
            }}
        )
        flash('Producto actualizado con éxito.', 'success')
    except Exception:
        flash('Error al editar el producto.', 'danger')

    return redirect(url_for('admin_panel'))

@app.route('/admin/producto/estado/<producto_id>')
@admin_required
def cambiar_estado_producto(producto_id):
    try:
        p = db.productos.find_one({"_id": ObjectId(producto_id)})
        if p:
            nuevo_estado = 0 if p.get("activo", 1) == 1 else 1
            db.productos.update_one({"_id": ObjectId(producto_id)}, {"$set": {"activo": nuevo_estado}})
            flash('Estado del producto actualizado.', 'info')
    except Exception:
        pass
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