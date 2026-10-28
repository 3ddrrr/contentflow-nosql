import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from pprint import pprint
from pymongo.errors import DuplicateKeyError
from db import conectar

LOG = Path(__file__).resolve().parent.parent / "logs" / "crud.log"
LOG.parent.mkdir(exist_ok=True)

client, db = conectar()
CAMP = "campañas" if "campañas" in db.list_collection_names() else "campanas"
COLECCIONES = ["usuarios", "publicaciones", "reacciones", "comentarios", CAMP]
VERIFICACIONES = []


def ahora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def log(msg):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{ahora():%Y-%m-%d %H:%M:%S} | {msg}\n")


def titulo(msg):
    print(f"\n{'=' * 72}\n{msg}\n{'=' * 72}")
    log(msg)


def paso(msg):
    print(f"\n-- {msg}")
    log(msg)


def check(descripcion, condicion):
    VERIFICACIONES.append(bool(condicion))
    estado = "OK" if condicion else "FALLO"
    print(f"   [{estado}] {descripcion}")
    log(f"{estado} | {descripcion}")


def limpiar_demo():
    """Borra cualquier documento de demostración (_id que empieza con demo_)."""
    total = 0
    for col in COLECCIONES:
        total += db[col].delete_many({"_id": {"$regex": "^demo_"}}).deleted_count
    return total


# ---------------------------------------------------------------- preparación
log("===== INICIO 07_crud_negocio.py =====")
residuo = limpiar_demo()
print(f"Limpieza previa de datos de demostración: {residuo} documentos")
BASE = {c: db[c].count_documents({}) for c in COLECCIONES}
print("Conteo inicial:", BASE)
db.usuarios.create_index([("correo", 1)], unique=True, name="idx_correo_unico")

# =========================================================== ESCENARIO 1
titulo("ESCENARIO 1: GESTIÓN DE USUARIOS")
usuario = {"_id": "demo_user_1", "nombre": "Usuario Demo", "correo": "demo.usuario@contentflow.test",
           "pais": "Chile", "genero": "Otro", "fecha_registro": ahora(), "dispositivo": "Móvil"}

paso("CREATE: registrar un usuario nuevo (insert_one)")
r = db.usuarios.insert_one(usuario)
check("insert_one devolvió el _id esperado", r.inserted_id == "demo_user_1")
check("el total de usuarios subió en 1", db.usuarios.count_documents({}) == BASE["usuarios"] + 1)

paso("VALIDACIÓN: el índice único impide registrar un correo repetido")
try:
    db.usuarios.insert_one({**usuario, "_id": "demo_user_dup"})
    check("el correo duplicado fue rechazado", False)
except DuplicateKeyError:
    check("el correo duplicado fue rechazado (DuplicateKeyError)", True)

paso("READ: buscar al usuario por correo con proyección (find_one)")
u = db.usuarios.find_one({"correo": usuario["correo"]}, {"nombre": 1, "pais": 1, "dispositivo": 1})
pprint(u)
check("el usuario se encontró", u is not None and u["_id"] == "demo_user_1")

paso("UPDATE: cambiar dispositivo y país ($set, update_one)")
r = db.usuarios.update_one({"_id": "demo_user_1"}, {"$set": {"dispositivo": "Tablet", "pais": "Argentina"}})
check("matched_count = 1 y modified_count = 1", (r.matched_count, r.modified_count) == (1, 1))
check("el cambio quedó guardado", db.usuarios.find_one({"_id": "demo_user_1"})["dispositivo"] == "Tablet")
r = db.usuarios.update_one({"_id": "demo_user_1"}, {"$set": {"dispositivo": "Tablet"}})
check("repetir el mismo cambio no modifica nada (modified_count = 0)", r.modified_count == 0)
r = db.usuarios.update_one({"_id": "demo_user_inexistente"}, {"$set": {"pais": "Chile"}})
check("actualizar un ID inexistente da matched_count = 0", r.matched_count == 0)

paso("DELETE: eliminar al usuario (delete_one)")
r = db.usuarios.delete_one({"_id": "demo_user_1"})
check("deleted_count = 1", r.deleted_count == 1)
check("el usuario ya no existe", db.usuarios.find_one({"_id": "demo_user_1"}) is None)
r = db.usuarios.delete_one({"_id": "demo_user_1"})
check("borrar de nuevo da deleted_count = 0", r.deleted_count == 0)

# =========================================================== ESCENARIO 2
titulo("ESCENARIO 2: CICLO DE VIDA DE UNA PUBLICACIÓN")
PUB = "demo_pub_1"
LECTORES = ["user_2", "user_3", "user_4", "user_5", "user_6"]

paso("VALIDACIÓN previa: los usuarios referenciados existen")
check("autor y lectores existen en usuarios",
      db.usuarios.count_documents({"_id": {"$in": ["user_1"] + LECTORES}}) == 6)

paso("CREATE: publicar contenido (insert_one)")
db.publicaciones.insert_one({
    "_id": PUB, "usuario_id": "user_1", "contenido": "Lanzamiento de ContentFlow",
    "fecha_publicacion": ahora(), "categoria": "Tecnología", "hashtags": ["#innovacion"], "tipo": "Video"})
check("la publicación existe", db.publicaciones.count_documents({"_id": PUB}) == 1)

paso("CREATE: agregar reacciones y comentarios (insert_many)")
reacciones = [{"_id": f"demo_react_{i}", "usuario_id": u, "publicacion_id": PUB,
               "tipo_reaccion": t, "fecha": ahora()}
              for i, (u, t) in enumerate([("user_2", "Me gusta"), ("user_3", "Me encanta"),
                                          ("user_4", "Me gusta")], 1)]
comentarios = [{"_id": f"demo_comm_{i}", "usuario_id": u, "publicacion_id": PUB,
                "comentario": txt, "fecha": ahora(), "likes": likes}
               for i, (u, txt, likes) in enumerate([("user_5", "Muy buen contenido", 10),
                                                     ("user_6", "Gracias por compartir", 3)], 1)]
check("se insertaron 3 reacciones", len(db.reacciones.insert_many(reacciones).inserted_ids) == 3)
check("se insertaron 2 comentarios", len(db.comentarios.insert_many(comentarios).inserted_ids) == 2)

paso("UPDATE: editar el contenido y agregar un hashtag ($set + $push)")
r = db.publicaciones.update_one({"_id": PUB}, {
    "$set": {"contenido": "Lanzamiento oficial de ContentFlow"},
    "$push": {"hashtags": "#aprendizaje"}})
check("matched_count = 1 y modified_count = 1", (r.matched_count, r.modified_count) == (1, 1))

paso("UPDATE: $addToSet no repite un hashtag que ya existe")
r = db.publicaciones.update_one({"_id": PUB}, {"$addToSet": {"hashtags": "#aprendizaje"}})
check("hashtag repetido: modified_count = 0", r.modified_count == 0)
r = db.publicaciones.update_one({"_id": PUB}, {"$addToSet": {"hashtags": "#futbol"}})
check("hashtag nuevo: modified_count = 1", r.modified_count == 1)
check("la publicación quedó con 3 hashtags",
      len(db.publicaciones.find_one({"_id": PUB})["hashtags"]) == 3)

paso("UPDATE masivo: sumar 5 likes a los comentarios ($inc, update_many)")
r = db.comentarios.update_many({"publicacion_id": PUB}, {"$inc": {"likes": 5}})
check("matched_count = 2 y modified_count = 2", (r.matched_count, r.modified_count) == (2, 2))

paso("READ: resumen de la publicación (aggregate con $lookup)")
resumen = list(db.publicaciones.aggregate([
    {"$match": {"_id": PUB}},
    {"$lookup": {"from": "reacciones", "localField": "_id", "foreignField": "publicacion_id", "as": "r"}},
    {"$lookup": {"from": "comentarios", "localField": "_id", "foreignField": "publicacion_id", "as": "c"}},
    {"$project": {"categoria": 1, "hashtags": 1, "reacciones": {"$size": "$r"},
                  "comentarios": {"$size": "$c"}, "likes_comentarios": {"$sum": "$c.likes"}}},
]))
pprint(resumen, sort_dicts=False)
check("resumen: 3 reacciones, 2 comentarios y 23 likes en comentarios",
      resumen and (resumen[0]["reacciones"], resumen[0]["comentarios"], resumen[0]["likes_comentarios"]) == (3, 2, 23))

paso("DELETE en cascada: borrar la publicación y todo lo que depende de ella")
rr = db.reacciones.delete_many({"publicacion_id": PUB})
rc = db.comentarios.delete_many({"publicacion_id": PUB})
rp = db.publicaciones.delete_one({"_id": PUB})
check("deleted_count: reacciones = 3, comentarios = 2, publicación = 1",
      (rr.deleted_count, rc.deleted_count, rp.deleted_count) == (3, 2, 1))
huerfanos = (db.reacciones.count_documents({"publicacion_id": PUB})
             + db.comentarios.count_documents({"publicacion_id": PUB}))
check("no quedaron registros huérfanos", huerfanos == 0)

# =========================================================== ESCENARIO 3
titulo("ESCENARIO 3: GESTIÓN DE UNA CAMPAÑA")
CID = "demo_camp_1"


def validar_campana(c):
    errores = []
    if c["fecha_fin"] < c["fecha_inicio"]:
        errores.append("fecha_fin anterior a fecha_inicio")
    pubs = list(set(c["publicaciones_asociadas"]))
    if db.publicaciones.count_documents({"_id": {"$in": pubs}}) != len(pubs):
        errores.append("hay publicaciones asociadas que no existen")
    return errores


inicio = ahora()
camp = {"_id": CID, "nombre": "Campaña Demo", "fecha_inicio": inicio, "fecha_fin": inicio + timedelta(days=30),
        "objetivo": "Aumentar engagement", "publicaciones_asociadas": [],
        "metricas_objetivo": {"likes": 100, "comentarios": 50, "compartidos": 20}}

paso("VALIDACIÓN: una campaña con fechas invertidas se rechaza antes de insertar")
errores = validar_campana({**camp, "fecha_fin": inicio - timedelta(days=1)})
check("rechazada: " + "; ".join(errores), len(errores) > 0)

paso("CREATE: crear la campaña (insert_one)")
db[CAMP].insert_one(camp)
check("la campaña existe", db[CAMP].count_documents({"_id": CID}) == 1)

paso("VALIDACIÓN: asociar una publicación inexistente se rechaza")
errores = validar_campana({**camp, "publicaciones_asociadas": ["pub_999999"]})
check("rechazada: " + "; ".join(errores), len(errores) > 0)

paso("UPDATE: asociar publicaciones reales ($addToSet con $each)")
nuevas = ["pub_1", "pub_2", "pub_3"]
check("las 3 publicaciones existen", not validar_campana({**camp, "publicaciones_asociadas": nuevas}))
r = db[CAMP].update_one({"_id": CID}, {"$addToSet": {"publicaciones_asociadas": {"$each": nuevas}}})
check("matched_count = 1 y modified_count = 1", (r.matched_count, r.modified_count) == (1, 1))

paso("UPDATE: ajustar las métricas objetivo ($inc y $set en un campo anidado)")
r = db[CAMP].update_one({"_id": CID}, {"$inc": {"metricas_objetivo.likes": 50},
                                       "$set": {"metricas_objetivo.comentarios": 80}})
m = db[CAMP].find_one({"_id": CID})["metricas_objetivo"]
check("métricas: likes = 150 y comentarios = 80", (m["likes"], m["comentarios"]) == (150, 80))

paso("READ: avance de la campaña (aggregate con $lookup sobre un arreglo)")
avance = list(db[CAMP].aggregate([
    {"$match": {"_id": CID}},
    {"$lookup": {"from": "reacciones", "localField": "publicaciones_asociadas",
                 "foreignField": "publicacion_id", "as": "r"}},
    {"$lookup": {"from": "comentarios", "localField": "publicaciones_asociadas",
                 "foreignField": "publicacion_id", "as": "c"}},
    {"$project": {"nombre": 1, "reacciones": {"$size": "$r"}, "comentarios": {"$size": "$c"},
                  "meta_likes": "$metricas_objetivo.likes"}},
]))
pprint(avance, sort_dicts=False)
check("la consulta de avance devolvió la campaña", len(avance) == 1)

paso("UPDATE: cerrar la campaña ($set de fecha_fin y estado)")
r = db[CAMP].update_one({"_id": CID}, {"$set": {"fecha_fin": ahora(), "estado": "cerrada"}})
check("matched_count = 1 y modified_count = 1", (r.matched_count, r.modified_count) == (1, 1))
check("la campaña quedó cerrada", db[CAMP].find_one({"_id": CID}).get("estado") == "cerrada")

paso("DELETE: eliminar la campaña de demostración (delete_one)")
r = db[CAMP].delete_one({"_id": CID})
check("deleted_count = 1", r.deleted_count == 1)

# ============================================================== CIERRE
titulo("VERIFICACIÓN FINAL")
residuo = limpiar_demo()
check(f"no quedaron datos de demostración (residuo: {residuo})", residuo == 0)
for col in COLECCIONES:
    actual = db[col].count_documents({})
    check(f"{col}: {actual} documentos, igual que al inicio ({BASE[col]})", actual == BASE[col])

ok = sum(VERIFICACIONES)
total = len(VERIFICACIONES)
print(f"\nRESULTADO: {ok}/{total} verificaciones correctas")
log(f"===== FIN: {ok}/{total} verificaciones correctas =====")
print("Registro guardado en logs/crud.log")
sys.exit(0 if ok == total else 1)
