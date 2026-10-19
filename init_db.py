import sqlite3

def inicializar_servicios():
    conexion = sqlite3.connect('database.db') # Cambia por el nombre de tu archivo .db
    cursor = conexion.cursor()

    # Creación de tabla si no existe
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS servicios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            duracion_min INTEGER NOT NULL,
            precio REAL NOT NULL
        )
    ''')

    # Datos de ejemplo
    servicios = [
        ('Limpieza Facial Profunda', 'Tratamiento purificante con exfoliación, extracción e hidratación intensiva.', 60, 650.00),
        ('Masaje Relajante Corporal', 'Terapia corporal con aceites esenciales para liberar tensión muscular.', 50, 800.00),
        ('Manicura & Pedicura Spa', 'Cuidado completo de uñas con exfoliación orgánica y esmaltado duradero.', 75, 550.00),
        ('Lifting y Tinte de Pestañas', 'Realce natural de pestañas con nutrición de queratina.', 45, 450.00)
    ]

    # Insertar si la tabla está vacía
    cursor.execute('SELECT COUNT(*) FROM servicios')
    if cursor.fetchone()[0] == 0:
        cursor.executemany('''
            INSERT INTO servicios (nombre, descripcion, duracion_min, precio)
            VALUES (?, ?, ?, ?)
        ''', servicios)
        conexion.commit()

    conexion.close()

if __name__ == '__main__':
    inicializar_servicios()
    print("Servicios insertados correctamente en la base de datos.")