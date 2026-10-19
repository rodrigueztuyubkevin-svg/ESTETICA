import sqlite3

DATABASE_NAME = "salon_estetica.db"

def obtener_conexion():
    """Establece y devuelve una conexión a la base de datos SQLite."""
    conexion = sqlite3.connect(DATABASE_NAME)
    # Permite acceder a las columnas por su nombre (ej. fila['nombre'])
    conexion.row_factory = sqlite3.Row
    return conexion

def inicializar_bd():
    """Crea la estructura de tablas si no existen."""
    conexion = obtener_conexion()
    cursor = conexion.cursor()

    # Habilitar el soporte de Claves Foráneas (Foreign Keys) en SQLite
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 1. Tabla de Usuarios
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        telefono TEXT,
        password_hash TEXT NOT NULL,
        rol TEXT CHECK(rol IN ('cliente', 'admin')) DEFAULT 'cliente',
        fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Tabla de Ficha de Salud (Relacionada 1 a 1 con Usuarios)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fichas_salud (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER UNIQUE NOT NULL,
        alergias TEXT,
        condiciones_piel TEXT,
        embarazo_lactancia INTEGER DEFAULT 0, -- 0 = No, 1 = Sí
        padecimientos_especiales TEXT,
        cita_silenciosa INTEGER DEFAULT 0,    -- 0 = No, 1 = Sí
        notas_adicionales TEXT,
        fecha_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
    );
    """)

    # 3. Tabla de Categorías de Servicios
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categorias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL UNIQUE,
        descripcion TEXT
    );
    """)

    # 4. Tabla de Servicios / Estilos / Productos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS servicios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        categoria_id INTEGER NOT NULL,
        nombre TEXT NOT NULL,
        descripcion TEXT,
        precio REAL NOT NULL,
        duracion_minutos INTEGER NOT NULL,
        imagen_url TEXT,
        es_producto INTEGER DEFAULT 0, -- 0 = Servicio/Estilo, 1 = Producto físico
        activo INTEGER DEFAULT 1,       -- 1 = Visible, 0 = Oculto
        FOREIGN KEY (categoria_id) REFERENCES categorias (id) ON DELETE RESTRICT
    );
    """)

    # 5. Tabla de Especialistas / Esteticistas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS especialistas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        especialidad TEXT,
        imagen_url TEXT,
        activo INTEGER DEFAULT 1
    );
    """)

    # 6. Tabla de Citas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS citas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        servicio_id INTEGER NOT NULL,
        especialista_id INTEGER,
        fecha_hora DATETIME NOT NULL,
        estado TEXT CHECK(estado IN ('pendiente', 'confirmada', 'completada', 'cancelada')) DEFAULT 'pendiente',
        notas_cliente TEXT,
        fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE,
        FOREIGN KEY (servicio_id) REFERENCES servicios (id) ON DELETE RESTRICT,
        FOREIGN KEY (especialista_id) REFERENCES especialistas (id) ON DELETE SET NULL
    );
    """)

    # Confirmar los cambios y cerrar
    conexion.commit()
    conexion.close()
    print("✨ Base de datos inicializada correctamente con todas sus tablas.")

if __name__ == "__main__":
    inicializar_bd()