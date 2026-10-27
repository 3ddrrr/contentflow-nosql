import json
from datetime import datetime
from pathlib import Path
from pymongo import ReplaceOne
from db import conectar

DATA = Path(__file__).resolve().parent.parent / "data"

client, db = conectar()
existentes = db.list_collection_names()
CAMP = "campañas" if "campañas" in existentes else "campanas"

# (archivo, colección destino, campos de fecha a convertir)
CARGAS = [
    ("usuarios.json", "usuarios", ["fecha_registro"]),
    ("publicaciones.json", "publicaciones", ["fecha_publicacion"]),
    ("reacciones.json", "reacciones", ["fecha"]),
    ("comentarios.json", "comentarios", ["fecha"]),
    ("campanas.json", CAMP, ["fecha_inicio", "fecha_fin"]),
]

print(f"{'colección':15} {'leídos':>7} {'nuevos':>7} {'reemplazados':>13} {'ya iguales':>11}")
for archivo, coleccion, campos in CARGAS:
    docs = json.loads((DATA / archivo).read_text(encoding="utf-8"))
    for d in docs:
        for c in campos:
            d[c] = datetime.fromisoformat(d[c])

    ops = [ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in docs]
    r = db[coleccion].bulk_write(ops, ordered=False)
    iguales = r.matched_count - r.modified_count
    print(f"{coleccion:15} {len(docs):>7} {r.upserted_count:>7} {r.modified_count:>13} {iguales:>11}")

print("\nVerificación de tipos y conteos:")
for archivo, coleccion, campos in CARGAS:
    ejemplo = db[coleccion].find_one({}, {c: 1 for c in campos})
    tipos = {c: type(ejemplo[c]).__name__ for c in campos}
    print(f"{coleccion:15} {db[coleccion].count_documents({}):>4} docs  {tipos}")