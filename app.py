import sqlite3
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, g
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'aura_estetica_secret_key_super_segura'
DATABASE = 'database.db'

# ------------------------------------------------------------------
# CONFIGURACIÓN Y MANEJO DE LA BASE DE DATOS
# ------------------------------------------------------------------

def get_db():
    """Conexión a la base de datos SQLite por petición."""
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    """Cierra la conexión al finalizar la petición."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Inicializa la estructura de las tablas en SQLite y datos por defecto."""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()

        # Tabla Usuarios
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                telefono TEXT,
                password TEXT NOT NULL,
                rol TEXT DEFAULT 'cliente'
            )
        ''')

        # Tabla Categorías
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL
            )
        ''')

        # Tabla Servicios / Productos (Catálogo)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS servicios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                categoria_id INTEGER,
                nombre TEXT NOT NULL,
                descripcion TEXT,
                precio REAL NOT NULL,
                duracion_min INTEGER,
                tipo TEXT DEFAULT 'servicio',
                activo INTEGER DEFAULT 1,
                FOREIGN KEY (categoria_id) REFERENCES categorias(id)
            )
        ''')

        # Tabla Especialistas / Esteticistas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS especialistas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                especialidad TEXT
            )
        ''')

        # Tabla Ficha de Salud
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fichas_salud (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER UNIQUE NOT NULL,
                alergias TEXT,
                condiciones_piel TEXT,
                padecimientos_especiales TEXT,
                embarazo_lactancia INTEGER DEFAULT 0,
                cita_silenciosa INTEGER DEFAULT 0,
                notas_adicionales TEXT,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            )
        ''')

        # Tabla Citas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS citas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                servicio_id INTEGER NOT NULL,
                especialista_id INTEGER,
                fecha_hora TEXT NOT NULL,
                estado TEXT DEFAULT 'pendiente',
                notas_cliente TEXT,
                creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
                FOREIGN KEY (servicio_id) REFERENCES servicios(id),
                FOREIGN KEY (especialista_id) REFERENCES especialistas(id)
            )
        ''')

        db.commit()

        # Insertar servicios iniciales si la tabla está vacía
        cursor.execute('SELECT COUNT(*) FROM servicios')
        if cursor.fetchone()[0] == 0:
            servicios_iniciales = [
                ('Limpieza Facial Profunda', 'Tratamiento purificante con exfoliación, extracción e hidratación intensiva para renovar tu piel.', 650.00, 60, 'servicio', 1),
                ('Masaje Relajante Corporal', 'Terapia corporal con aceites esenciales diseñada para liberar tensión muscular y reducir el estrés.', 800.00, 50, 'servicio', 1),
                ('Manicura & Pedicura Spa', 'Cuidado completo de uñas con exfoliación orgánica, tratamiento de cutículas y esmaltado duradero.', 550.00, 75, 'servicio', 1),
                ('Lifting y Tinte de Pestañas', 'Realce natural de tus pestañas desde la raíz con nutrición de queratina para una mirada definida.', 450.00, 45, 'servicio', 1)
            ]
            cursor.executemany('''
                INSERT INTO servicios (nombre, descripcion, precio, duracion_min, tipo, activo)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', servicios_iniciales)
            db.commit()

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
    """Página de inicio con servicios destacados."""
    db = get_db()
    servicios = db.execute('SELECT * FROM servicios WHERE activo = 1 AND tipo = "servicio" LIMIT 6').fetchall()
    return render_template('index.html', servicios=servicios)

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form['nombre']
        email = request.form['email']
        telefono = request.form['telefono']
        password = generate_password_hash(request.form['password'])

        db = get_db()
        try:
            cursor = db.cursor()
            cursor.execute(
                'INSERT INTO usuarios (nombre, email, telefono, password) VALUES (?, ?, ?, ?)',
                (nombre, email, telefono, password)
            )
            db.commit()
           
            nuevo_usuario_id = cursor.lastrowid
            session['usuario_id'] = nuevo_usuario_id
            session['nombre'] = nombre
            session['rol'] = 'cliente'

            flash(f'¡Bienvenido/a, {nombre}! Tu cuenta se ha creado con éxito.', 'success')
            return redirect(url_for('index'))
           
        except sqlite3.IntegrityError:
            flash('El correo electrónico ya está registrado.', 'danger')

    return render_template('registro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        db = get_db()
        usuario = db.execute('SELECT * FROM usuarios WHERE email = ?', (email,)).fetchone()

        if usuario and check_password_hash(usuario['password'], password):
            session['usuario_id'] = usuario['id']
            session['nombre'] = usuario['nombre']
            session['rol'] = usuario['rol']
            flash(f'¡Bienvenido de nuevo, {usuario["nombre"]}!', 'success')
           
            if usuario['rol'] == 'admin':
                return redirect(url_for('admin_panel'))
            return redirect(url_for('perfil'))
        else:
            flash('Credenciales incorrectas. Intenta de nuevo.', 'danger')

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
    db = get_db()
    usuario_id = session['usuario_id']

    # Procesar guardado/actualización de la Ficha de Salud
    if request.method == 'POST':
        alergias = request.form.get('alergias', '')
        condiciones_piel = request.form.get('condiciones_piel', '')
        padecimientos = request.form.get('padecimientos_especiales', '')
        embarazo = 1 if request.form.get('embarazo_lactancia') else 0
        silenciosa = 1 if request.form.get('cita_silenciosa') else 0
        notas = request.form.get('notas_adicionales', '')

        db.execute('''
            INSERT INTO fichas_salud
                (usuario_id, alergias, condiciones_piel, padecimientos_especiales, embarazo_lactancia, cita_silenciosa, notas_adicionales)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(usuario_id) DO UPDATE SET
                alergias = excluded.alergias,
                condiciones_piel = excluded.condiciones_piel,
                padecimientos_especiales = excluded.padecimientos_especiales,
                embarazo_lactancia = excluded.embarazo_lactancia,
                cita_silenciosa = excluded.cita_silenciosa,
                notas_adicionales = excluded.notas_adicionales
        ''', (usuario_id, alergias, condiciones_piel, padecimientos, embarazo, silenciosa, notas))
       
        db.commit()
        flash('Tu ficha de salud se ha actualizado correctamente.', 'success')
        return redirect(url_for('perfil'))

    # Obtener Ficha de Salud actual (Manejo robusto para índices o diccionarios)
    ficha = db.execute('SELECT * FROM fichas_salud WHERE usuario_id = ?', (usuario_id,)).fetchone()

    # Obtener Citas Agendadas del usuario
    citas = db.execute('''
        SELECT c.*, s.nombre AS servicio_nombre, e.nombre AS especialista_nombre
        FROM citas c
        JOIN servicios s ON c.servicio_id = s.id
        LEFT JOIN especialistas e ON c.especialista_id = e.id
        WHERE c.usuario_id = ?
        ORDER BY c.fecha_hora DESC
    ''', (usuario_id,)).fetchall()

    # Obtener datos de usuario
    usuario_info = db.execute('SELECT nombre, email, telefono FROM usuarios WHERE id = ?', (usuario_id,)).fetchone()

    return render_template('perfil.html', usuario=usuario_info, ficha_medica=ficha, citas=citas)


@app.route('/agendar', methods=['GET', 'POST'])
@login_required
def agendar():
    db = get_db()
    
    servicios = db.execute('SELECT * FROM servicios WHERE activo = 1 AND tipo = "servicio"').fetchall()
    especialistas = db.execute('SELECT * FROM especialistas').fetchall()

    if request.method == 'POST':
        paso = request.form.get('paso', '1')
        
        # PASO 1: Selección de Servicio -> Avanza a Paso 2
        if paso == '1':
            servicio_id = request.form.get('servicio_id')
            if not servicio_id:
                flash('Por favor selecciona un servicio para continuar.', 'warning')
                return redirect(url_for('agendar'))
            return render_template('agendar.html', paso=2, servicio_id=servicio_id, servicios=servicios, especialistas=especialistas)
        
        # PASO 2: Selección de Especialista -> Avanza a Paso 3
        elif paso == '2':
            servicio_id = request.form.get('servicio_id')
            especialista_id = request.form.get('especialista_id', '0')
            from datetime import date
            hoy = date.today().strftime('%Y-%m-%d')
            return render_template('agendar.html', paso=3, servicio_id=servicio_id, especialista_id=especialista_id, hoy=hoy, servicios=servicios, especialistas=especialistas)
        
        # PASO 3: Selección de Fecha y Hora -> Avanza a Paso 4 (Resumen)
        elif paso == '3':
            servicio_id = request.form.get('servicio_id')
            especialista_id = request.form.get('especialista_id')
            fecha = request.form.get('fecha')
            hora = request.form.get('hora')
            
            if not fecha or not hora:
                flash('Por favor selecciona una fecha y hora válidas.', 'warning')
                return render_template('agendar.html', paso=3, servicio_id=servicio_id, especialista_id=especialista_id, servicios=servicios, especialistas=especialistas)
            
            srv = db.execute('SELECT * FROM servicios WHERE id = ?', (servicio_id,)).fetchone()
            
            return render_template('agendar.html', paso=4, servicio_id=servicio_id, especialista_id=especialista_id, fecha=fecha, hora=hora, servicio_info=srv, servicios=servicios, especialistas=especialistas)

        # PASO 4: Confirmación Final y Guardado en Base de Datos
        elif paso == '4':
            servicio_id = request.form.get('servicio_id')
            especialista_id = request.form.get('especialista_id')
            fecha = request.form.get('fecha')
            hora = request.form.get('hora')
            notas = request.form.get('notas', '')

            fecha_hora = f"{fecha} {hora}"
            especialista_val = int(especialista_id) if especialista_id and especialista_id != '0' else None

            db.execute('''
                INSERT INTO citas (usuario_id, servicio_id, especialista_id, fecha_hora, notas_cliente, estado)
                VALUES (?, ?, ?, ?, ?, 'confirmada')
            ''', (session['usuario_id'], servicio_id, especialista_val, fecha_hora, notas))
            
            db.commit()
            flash('¡Tu cita ha sido reservada con éxito!', 'success')
            return redirect(url_for('perfil'))

    return render_template('agendar.html', servicios=servicios, especialistas=especialistas, paso=1)

# ------------------------------------------------------------------
# RUTAS DE ADMINISTRACIÓN
# ------------------------------------------------------------------

@app.route('/admin')
@admin_required
def admin_panel():
    db = get_db()

    citas_query = '''
        SELECT
            c.id, c.fecha_hora, c.estado, c.notas_cliente,
            u.nombre AS cliente_nombre, u.telefono,
            s.nombre AS servicio_nombre,
            CASE WHEN f.id IS NOT NULL AND (
                (f.alergias IS NOT NULL AND f.alergias != '') OR
                (f.condiciones_piel IS NOT NULL AND f.condiciones_piel != '') OR
                f.embarazo_lactancia = 1
            ) THEN 1 ELSE 0 END AS tiene_ficha
        FROM citas c
        JOIN usuarios u ON c.usuario_id = u.id
        JOIN servicios s ON c.servicio_id = s.id
        LEFT JOIN fichas_salud f ON u.id = f.usuario_id
        ORDER BY c.fecha_hora ASC
    '''
    citas = db.execute(citas_query).fetchall()
    catalogo = db.execute('SELECT * FROM servicios ORDER BY tipo, nombre').fetchall()

    return render_template('admin.html', citas=citas, catalogo=catalogo)


@app.route('/admin/cita/<int:cita_id>/<estado>')
@admin_required
def cambiar_estado_cita(cita_id, estado):
    if estado in ['confirmada', 'cancelada', 'completada']:
        db = get_db()
        db.execute('UPDATE citas SET estado = ? WHERE id = ?', (estado, cita_id))
        db.commit()
        flash(f'La cita #{cita_id} ha sido marcada como {estado}.', 'info')
    return redirect(url_for('admin_panel'))

# ------------------------------------------------------------------
# INICIALIZACIÓN
# ------------------------------------------------------------------

if __name__ == '__main__':
    init_db()
    app.run(debug=True)