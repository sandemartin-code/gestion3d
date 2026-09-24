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

class ItemPresupuesto(BaseModel):
    id_material: Optional[str] = None
    id_producto: Optional[str] = None
    descripcion_producto: str
    cantidad: int = 1
    precio_producto: float = 0.0
    peso_gramos: float = 0.0
    horas_impresion: float = 0.0
    costo_hora_maquina: float = 0.0
    extras: float = 0.0
    margen_porcentaje: float = 100.0

class PedidoCreate(BaseModel):
    id_pedido: str
    id_cliente: Optional[str] = "CLI-TEMP"
    estado: str = "Ingresado"
    anticipo: float = 0.0
    items: List[ItemPresupuesto]

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

@app.post("/api/pedidos")
def crear_pedido(pedido: PedidoCreate):
    conn = get_db()
    cursor = conn.cursor()
    try:
        total_pedido = 0.0
        detalles_calculados = []
        
        for item in pedido.items:
            if item.id_producto and item.precio_producto > 0:
                precio_pieza = item.cantidad * item.precio_producto
            else:
                costo_gramo = 0.0
                if item.id_material:
                    cursor.execute(
                        "SELECT (costo_bobina / NULLIF(peso_bobina_gramos, 0)) as cpg FROM materiales WHERE id_material = %s",
                        (item.id_material,)
                    )
                    mat = cursor.fetchone()
                    if mat and mat["cpg"]:
                        costo_gramo = float(mat["cpg"])
                
                costo_base = (item.peso_gramos * costo_gramo) + (item.horas_impresion * item.costo_hora_maquina) + item.extras
                precio_pieza = costo_base * (1 + (item.margen_porcentaje / 100.0)) * item.cantidad
            
            total_pedido += precio_pieza
            detalles_calculados.append((item, precio_pieza))
        
        cursor.execute(
            "INSERT INTO pedidos (id_pedido, id_cliente, estado, total_presupuesto, anticipo) VALUES (%s, %s, %s, %s, %s)",
            (pedido.id_pedido, pedido.id_cliente, pedido.estado, total_pedido, pedido.anticipo)
        )
        
        for item, precio_pieza in detalles_calculados:
            cursor.execute(
                """INSERT INTO presupuesto_detalle 
                   (id_pedido, id_material, id_producto, descripcion_producto, cantidad, precio_producto, peso_gramos, horas_impresion, costo_hora_maquina, extras_arandelas_tornillos, margen_ganancia_porcentaje, precio_pieza)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (pedido.id_pedido, item.id_material, item.id_producto, item.descripcion_producto, item.cantidad, item.precio_producto, item.peso_gramos, item.horas_impresion, item.costo_hora_maquina, item.extras, item.margen_porcentaje, precio_pieza)
            )
        
        conn.commit()
        return {"status": "ok", "id_pedido": pedido.id_pedido, "total": total_pedido}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()