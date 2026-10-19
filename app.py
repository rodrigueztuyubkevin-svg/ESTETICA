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
    """Asegura que los servicios iniciales existan en MongoDB si la colección está vacía."""
    if db.servicios.count_documents({}) == 0:
        servicios_iniciales = [
            {
                'nombre': 'Limpieza Facial Profunda',
                'descripcion': 'Tratamiento purificante con exfoliación, extracción e hidratación intensiva para renovar tu piel.',
                'precio': 650.00,
                'duracion_min': 60,
                'tipo': 'servicio',
                'activo': 1
            },
            {
                'nombre': 'Masaje Relajante Corporal',
                'descripcion': 'Terapia corporal con aceites esenciales diseñada para liberar tensión muscular y reducir el estrés.',
                'precio': 800.00,
                'duracion_min': 50,
                'tipo': 'servicio',
                'activo': 1
            },
            {
                'nombre': 'Manicura & Pedicura Spa',
                'descripcion': 'Cuidado completo de uñas con exfoliación orgánica, tratamiento de cutículas y esmaltado duradero.',
                'precio': 550.00,
                'duracion_min': 75,
                'tipo': 'servicio',
                'activo': 1
            },
            {
                'nombre': 'Lifting y Tinte de Pestañas',
                'descripcion': 'Realce natural de tus pestañas desde la raíz con nutrición de queratina para una mirada definida.',
                'precio': 450.00,
                'duracion_min': 45,
                'tipo': 'servicio',
                'activo': 1
            }
        ]
        db.servicios.insert_many(servicios_iniciales)

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
# RUTAS DE CLIENTE: PERFIL, FICHA DE SALUD Y AGENDAMIENTO
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
        srv = db.servicios.find_one({"_id": c.get("servicio_id")})
        esp = db.especialistas.find_one({"_id": c.get("especialista_id")}) if c.get("especialista_id") else None
        
        c['servicio_nombre'] = srv['nombre'] if srv else 'Tratamiento Estético'
        c['especialista_nombre'] = esp['nombre'] if esp else 'Asignado según disponibilidad'
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
# RUTAS DE ADMINISTRACIÓN
# ------------------------------------------------------------------

@app.route('/admin')
@admin_required
def admin_panel():
    citas_raw = list(db.citas.find({}).sort("fecha_hora", 1))
    citas = []
    for c in citas_raw:
        u_id = c["usuario_id"]
        try:
            u_obj = ObjectId(u_id)
        except Exception:
            u_obj = u_id

        u = db.usuarios.find_one({"$or": [{"_id": u_obj}, {"_id": u_id}]})
        s = db.servicios.find_one({"_id": c["servicio_id"]})
        f = db.fichas_salud.find_one({"usuario_id": str(u_id)})
        
        tiene_ficha = 1 if f and (f.get("alergias") or f.get("condiciones_piel") or f.get("embarazo_lactancia") == 1) else 0

        citas.append({
            "id": str(c["_id"]),
            "fecha_hora": c["fecha_hora"],
            "estado": c.get("estado", "pendiente"),
            "notas_cliente": c.get("notas_cliente", ""),
            "cliente_nombre": u["nombre"] if u else "Desconocido",
            "telefono": u.get("telefono", "") if u else "",
            "servicio_nombre": s["nombre"] if s else "Servicio",
            "tiene_ficha": tiene_ficha
        })

    catalogo_raw = list(db.servicios.find({}).sort([("tipo", 1), ("nombre", 1)]))
    catalogo = []
    for cat in catalogo_raw:
        cat['id'] = str(cat['_id'])
        catalogo.append(cat)

    return render_template('admin.html', citas=citas, catalogo=catalogo)

@app.route('/admin/cita/<cita_id>/<estado>')
@admin_required
def cambiar_estado_cita(cita_id, estado):
    if estado in ['confirmada', 'cancelada', 'completada']:
        db.citas.update_one({"_id": ObjectId(cita_id)}, {"$set": {"estado": estado}})
        flash(f'La cita ha sido marcada como {estado}.', 'info')
    return redirect(url_for('admin_panel'))

@app.route('/admin/servicio/nuevo', methods=['POST'])
@admin_required
def agregar_servicio():
    nombre = request.form.get('nombre', '').strip()
    descripcion = request.form.get('descripcion', '').strip()
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
            "activo": 1
        }
        db.servicios.insert_one(nuevo_servicio)
        flash('Servicio agregado al catálogo correctamente.', 'success')
    else:
        flash('El nombre del servicio es obligatorio.', 'danger')
        
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

if __name__ == '__main__':
    app.run(debug=True)