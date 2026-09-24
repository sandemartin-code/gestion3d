from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db():
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL no configurada.")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

# Ruta raíz de la API para probar que responde
@app.get("/api")
@app.get("/api/")
def root():
    return {"status": "ok", "message": "API de Gestión 3D en Vercel"}

# Rutas de Pedidos
@app.get("/api/pedidos")
def listar_pedidos():
    conn = get_db()
    cursor = conn.cursor()
    try:
        query = """
            SELECT p.id_pedido, p.fecha, COALESCE(c.nombre || ' ' || COALESCE(c.apellido, ''), 'Cliente General') as cliente,
                   COALESCE(c.telefono, '') as telefono, p.estado, p.total_presupuesto, p.anticipo,
                   (p.total_presupuesto - p.anticipo) as saldo_pendiente
            FROM pedidos p
            LEFT JOIN clientes c ON p.id_cliente = c.id_cliente
            ORDER BY p.fecha DESC
        """
        cursor.execute(query)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()