from fastapi import FastAPI, HTTPException, status, Depends
from pymongo.errors import DuplicateKeyError
#from api.database import get_db
from scripts.db import conectar
from api.models import UsuarioCreate, UsuarioUpdate
import logging
from fastapi import FastAPI, HTTPException, status
from pymongo.errors import DuplicateKeyError
from scripts.db import conectar
from api.models import UsuarioCreate, UsuarioUpdate
import logging
from datetime import datetime

app = FastAPI()
#db = get_db()
_, db = conectar()

# Configuración de Logging (IE11)
logging.basicConfig(filename='logs/app.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# --- Endpoints de Usuarios ---

@app.post("/usuarios", status_code=status.HTTP_201_CREATED)
def crear_usuario(usuario: UsuarioCreate):
    try:
        user_dict = usuario.model_dump()
        # Generar un ID simple para el ejemplo
        user_dict["_id"] = f"user_{db.usuarios.count_documents({})+1}" 
        user_dict["fecha_registro"] = datetime.now()
        
        resultado = db.usuarios.insert_one(user_dict)
        logging.info(f"Usuario creado con éxito: {user_dict['_id']}")
        return {"mensaje": "Usuario creado", "id": resultado.inserted_id}
    
    except DuplicateKeyError:
        logging.error(f"Intento de crear usuario con correo duplicado: {usuario.correo}")
        raise HTTPException(status_code=409, detail="El correo ya está registrado.")
    except Exception as e:
        logging.error(f"Error al crear usuario: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor.")

@app.get("/usuarios/{usuario_id}")
def obtener_usuario(usuario_id: str):
    usuario = db.usuarios.find_one({"_id": usuario_id})
    if not usuario:
        logging.warning(f"Intento de consultar usuario inexistente: {usuario_id}")
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return usuario

@app.put("/usuarios/{usuario_id}")
def actualizar_usuario(usuario_id: str, usuario: UsuarioUpdate):
    update_data = {k: v for k, v in usuario.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No se proporcionaron datos para actualizar.")
        
    resultado = db.usuarios.update_one({"_id": usuario_id}, {"$set": update_data})
    if resultado.matched_count == 0:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    
    logging.info(f"Usuario actualizado: {usuario_id}")
    return {"mensaje": "Usuario actualizado con éxito."}

@app.delete("/usuarios/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_usuario(usuario_id: str):
    resultado = db.usuarios.delete_one({"_id": usuario_id})
    if resultado.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    logging.info(f"Usuario eliminado: {usuario_id}")
    return {"mensaje": "Usuario eliminado."}

@app.get("/metricas/publicaciones/{pub_id}")
def metricas_publicacion(pub_id: str):
    # Basado en la agregación de tu archivo 07_crud_negocio.py
    resumen = list(db.publicaciones.aggregate([
        {"$match": {"_id": pub_id}},
        {"$lookup": {"from": "reacciones", "localField": "_id", "foreignField": "publicacion_id", "as": "r"}},
        {"$lookup": {"from": "comentarios", "localField": "_id", "foreignField": "publicacion_id", "as": "c"}},
        {"$project": {"categoria": 1, "hashtags": 1, "reacciones": {"$size": "$r"}, "comentarios": {"$size": "$c"}}}
    ]))
    if not resumen:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    return resumen[0]

@app.get("/segmentacion/usuarios")
def segmentacion_usuarios(pais: str):
    usuarios = list(db.usuarios.find({"pais": pais}, {"nombre": 1, "correo": 1, "dispositivo": 1}))
    return {"total_encontrados": len(usuarios), "usuarios": usuarios}