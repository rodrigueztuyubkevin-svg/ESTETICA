# KAD Estética & Spa

## Integrantes
- (nombre completo 1)
- (nombre completo 2)

## Problema que resuelve
Sistema de gestión para un spa: catálogo de servicios, tienda de productos, agendamiento de citas con especialistas y reserva temporal de horarios para evitar doble reserva.

## Elemento reservado
Horarios de cita (fecha + hora + especialista). Duración de la reserva: **5 minutos**.

## Función del QR
Cada cita confirmada genera un QR que abre una ficha pública (`/ficha/cita/<id>`) con folio, servicio, especialista, fecha, hora y estado actualizado.

## Cómo ejecutar
```bash
pip install -r requirements.txt
export MONGO_URI="mongodb+srv://..."
export APP_BASE_URL="https://tu-app.onrender.com"
python app.py