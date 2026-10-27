from pprint import pprint
from db import conectar

client, db = conectar()
existentes = db.list_collection_names()
CAMP = "campañas" if "campañas" in existentes else "campanas"
COLECCIONES = ["usuarios", "publicaciones", "reacciones", "comentarios", CAMP]

print("=== 1. Conteo de documentos ===")
for n in COLECCIONES:
    print(f"{n:15} {db[n].count_documents({})}")

print("\n=== 2. Tipo de las fechas (datetime = correcto, str = hay que convertir) ===")
campos = {"usuarios": "fecha_registro", "publicaciones": "fecha_publicacion",
          "reacciones": "fecha", "comentarios": "fecha", CAMP: "fecha_inicio"}
for col, campo in campos.items():
    valor = db[col].find_one({}, {campo: 1})[campo]
    print(f"{col:15} {campo:18} -> {type(valor).__name__}")

print("\n=== 3. Un documento de ejemplo por colección ===")
for n in COLECCIONES:
    print(f"\n--- {n} ---")
    pprint(db[n].find_one())

print("\n=== 4. Integridad referencial (todo debe dar 0) ===")
usuarios = db.usuarios.distinct("_id")
pubs = db.publicaciones.distinct("_id")
print("publicaciones con usuario inexistente :", db.publicaciones.count_documents({"usuario_id": {"$nin": usuarios}}))
print("reacciones con usuario inexistente    :", db.reacciones.count_documents({"usuario_id": {"$nin": usuarios}}))
print("reacciones con publicación inexistente:", db.reacciones.count_documents({"publicacion_id": {"$nin": pubs}}))
print("comentarios con usuario inexistente   :", db.comentarios.count_documents({"usuario_id": {"$nin": usuarios}}))
print("comentarios con publicación inexistente:", db.comentarios.count_documents({"publicacion_id": {"$nin": pubs}}))
print("campañas con publicaciones inexistentes:", db[CAMP].count_documents({"publicaciones_asociadas": {"$elemMatch": {"$nin": pubs}}}))
print("campañas con fecha_fin < fecha_inicio :", db[CAMP].count_documents({"$expr": {"$lt": ["$fecha_fin", "$fecha_inicio"]}}))

print("\n=== 5. Duplicados ===")
dup_correos = list(db.usuarios.aggregate([
    {"$group": {"_id": "$correo", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}]))
dup_reac = list(db.reacciones.aggregate([
    {"$group": {"_id": {"usuario": "$usuario_id", "publicacion": "$publicacion_id"}, "n": {"$sum": 1}}},
    {"$match": {"n": {"$gt": 1}}}]))
print("correos duplicados             :", len(dup_correos))
print("reacciones repetidas (usuario+publicación):", len(dup_reac))
for d in dup_reac:
    print("   ", d)

print("\n=== 6. Índices actuales ===")
for n in COLECCIONES:
    print(f"{n:15} {list(db[n].index_information().keys())}")

print("\n=== 7. Colección metricas_de_rendimiento ===")
for d in db.metricas_de_rendimiento.find():
    pprint(d)