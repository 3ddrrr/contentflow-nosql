import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from pymongo.errors import DuplicateKeyError
from db import conectar

RAIZ = Path(__file__).resolve().parent.parent
EVID = RAIZ / "evidencias"
LOG = RAIZ / "logs" / "validaciones.log"
LOG.parent.mkdir(exist_ok=True)
EVID.mkdir(exist_ok=True)

client, db = conectar()
CAMP = "campañas" if "campañas" in db.list_collection_names() else "campanas"
MODO = sys.argv[1] if len(sys.argv) > 1 else "diagnostico"

CAMPOS = {
    "usuarios": ["nombre", "correo", "pais", "genero", "fecha_registro", "dispositivo"],
    "publicaciones": ["usuario_id", "contenido", "fecha_publicacion", "categoria", "tipo"],
    "reacciones": ["usuario_id", "publicacion_id", "tipo_reaccion", "fecha"],
    "comentarios": ["usuario_id", "publicacion_id", "comentario", "fecha", "likes"],
    CAMP: ["nombre", "fecha_inicio", "fecha_fin", "objetivo", "metricas_objetivo"],
}
FECHAS = {"usuarios": ["fecha_registro"], "publicaciones": ["fecha_publicacion"],
          "reacciones": ["fecha"], "comentarios": ["fecha"], CAMP: ["fecha_inicio", "fecha_fin"]}
VERIFICACIONES = []


def ahora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def log(msg):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{ahora():%Y-%m-%d %H:%M:%S} | {msg}\n")


def titulo(msg):
    print(f"\n{'=' * 72}\n{msg}\n{'=' * 72}")
    log(msg)


def check(descripcion, condicion):
    VERIFICACIONES.append(bool(condicion))
    estado = "OK" if condicion else "FALLO"
    print(f"   [{estado}] {descripcion}")
    log(f"{estado} | {descripcion}")


def grupos_reacciones_repetidas():
    return list(db.reacciones.aggregate([
        {"$group": {"_id": {"usuario": "$usuario_id", "publicacion": "$publicacion_id"},
                    "n": {"$sum": 1}}},
        {"$match": {"n": {"$gt": 1}}},
    ]))


def diagnosticar():
    """Solo lectura. Devuelve {descripción: cantidad de problemas}."""
    usuarios = db.usuarios.distinct("_id")
    pubs = db.publicaciones.distinct("_id")
    r = {}
    r["Correos duplicados"] = len(list(db.usuarios.aggregate([
        {"$group": {"_id": "$correo", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}])))
    r["Reacciones repetidas (mismo usuario y publicación)"] = len(grupos_reacciones_repetidas())
    for col, campos in CAMPOS.items():
        r[f"{col}: documentos con campos obligatorios vacíos"] = db[col].count_documents(
            {"$or": [{c: {"$in": [None, ""]}} for c in campos]})
    r["Fechas guardadas como texto"] = sum(
        db[col].count_documents({c: {"$type": "string"}}) for col, cs in FECHAS.items() for c in cs)
    r["Publicaciones con usuario inexistente"] = db.publicaciones.count_documents({"usuario_id": {"$nin": usuarios}})
    r["Reacciones con usuario inexistente"] = db.reacciones.count_documents({"usuario_id": {"$nin": usuarios}})
    r["Reacciones con publicación inexistente"] = db.reacciones.count_documents({"publicacion_id": {"$nin": pubs}})
    r["Comentarios con usuario inexistente"] = db.comentarios.count_documents({"usuario_id": {"$nin": usuarios}})
    r["Comentarios con publicación inexistente"] = db.comentarios.count_documents({"publicacion_id": {"$nin": pubs}})
    r["Campañas con publicaciones inexistentes"] = db[CAMP].count_documents(
        {"publicaciones_asociadas": {"$elemMatch": {"$nin": pubs}}})
    r["Campañas con fecha_fin anterior a fecha_inicio"] = db[CAMP].count_documents(
        {"$expr": {"$lt": ["$fecha_fin", "$fecha_inicio"]}})
    r["Campañas con publicaciones repetidas en su lista"] = db[CAMP].count_documents(
        {"$expr": {"$ne": [{"$size": "$publicaciones_asociadas"},
                           {"$size": {"$setUnion": ["$publicaciones_asociadas", []]}}]}})
    r["Comentarios con likes negativos"] = db.comentarios.count_documents({"likes": {"$lt": 0}})
    return r


def mostrar(titulo_tabla, res):
    print(f"\n{titulo_tabla}")
    for k, v in res.items():
        print(f"   [{'OK' if v == 0 else 'PROBLEMA'}] {k}: {v}")
    print(f"   Total de problemas: {sum(res.values())}")


log(f"===== INICIO 08_validaciones.py (modo {MODO}) =====")
titulo("1. DIAGNÓSTICO DE CALIDAD (solo lectura)")
antes = diagnosticar()
mostrar("Resultado antes de cualquier corrección:", antes)
conteo_antes = db.reacciones.count_documents({})

grupos = grupos_reacciones_repetidas()
for g in grupos:
    docs = list(db.reacciones.find({"usuario_id": g["_id"]["usuario"],
                                    "publicacion_id": g["_id"]["publicacion"]}).sort([("fecha", 1), ("_id", 1)]))
    print(f"\n   Reacción repetida: {g['_id']['usuario']} sobre {g['_id']['publicacion']} ({g['n']} registros)")
    for d in docs:
        print(f"      {d['_id']} | {d['tipo_reaccion']} | {d['fecha']}")

if MODO != "corregir":
    (EVID / "diagnostico_calidad.json").write_text(
        json.dumps(antes, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nModo diagnóstico: no se modificó nada.")
    print("Para corregir:  python scripts\\08_validaciones.py corregir")
    print("Resultado guardado en evidencias/diagnostico_calidad.json")
    sys.exit(0)

# ------------------------------------------------------------ corrección
titulo("2. CORRECCIÓN DE REACCIONES REPETIDAS")
a_borrar = []
for g in grupos:
    docs = list(db.reacciones.find({"usuario_id": g["_id"]["usuario"],
                                    "publicacion_id": g["_id"]["publicacion"]}).sort([("fecha", 1), ("_id", 1)]))
    a_borrar.extend(docs[1:])  # se conserva la primera reacción (la original)

if a_borrar:
    print(f"Se conservará la reacción más antigua de cada par y se eliminarán {len(a_borrar)} registro(s):")
    for d in a_borrar:
        print(f"   - {d['_id']} ({d['usuario_id']} -> {d['publicacion_id']}, {d['fecha']})")
    if input("\nLa base es compartida. Escribe SI para continuar: ").strip().upper() != "SI":
        print("Cancelado. No se modificó nada.")
        sys.exit(0)
    respaldo = EVID / "reacciones_eliminadas.json"
    respaldo.write_text(json.dumps(a_borrar, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"Respaldo guardado en {respaldo.name}")
    r = db.reacciones.delete_many({"_id": {"$in": [d["_id"] for d in a_borrar]}})
    check(f"deleted_count = {len(a_borrar)}", r.deleted_count == len(a_borrar))
else:
    print("No hay reacciones repetidas que corregir.")

titulo("3. PREVENCIÓN: ÍNDICE ÚNICO (usuario_id + publicacion_id)")
nombre = db.reacciones.create_index([("usuario_id", 1), ("publicacion_id", 1)],
                                    unique=True, name="idx_reaccion_unica")
check("índice idx_reaccion_unica creado", nombre in db.reacciones.index_information())

ej = db.reacciones.find_one({"_id": {"$not": {"$regex": "^demo_"}}})
intento = {"_id": "demo_react_dup", "usuario_id": ej["usuario_id"], "publicacion_id": ej["publicacion_id"],
           "tipo_reaccion": "Me gusta", "fecha": ahora()}
try:
    db.reacciones.insert_one(intento)
    check("la reacción repetida fue rechazada", False)
except DuplicateKeyError:
    check("insertar una reacción repetida ahora falla (DuplicateKeyError)", True)
finally:
    db.reacciones.delete_one({"_id": "demo_react_dup"})
check("no quedó ningún registro de prueba", db.reacciones.count_documents({"_id": "demo_react_dup"}) == 0)

titulo("4. VERIFICACIÓN POSTERIOR")
despues = diagnosticar()
mostrar("Resultado después de la corrección:", despues)
check("reacciones repetidas = 0", despues["Reacciones repetidas (mismo usuario y publicación)"] == 0)
check(f"reacciones: {db.reacciones.count_documents({})} (antes {conteo_antes}, eliminadas {len(a_borrar)})",
      db.reacciones.count_documents({}) == conteo_antes - len(a_borrar))
check("integridad referencial intacta (huérfanos = 0)",
      all(despues[k] == 0 for k in despues if "inexistente" in k))

(EVID / "validaciones_resultado.json").write_text(json.dumps(
    {"antes": antes, "despues": despues, "reacciones_eliminadas": [d["_id"] for d in a_borrar]},
    indent=2, ensure_ascii=False), encoding="utf-8")
ok, total = sum(VERIFICACIONES), len(VERIFICACIONES)
print(f"\nRESULTADO: {ok}/{total} verificaciones correctas")
log(f"===== FIN: {ok}/{total} verificaciones correctas =====")
sys.exit(0 if ok == total else 1)
