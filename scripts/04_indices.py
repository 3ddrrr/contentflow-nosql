from db import conectar

client, db = conectar()
CAMP = "campañas" if "campañas" in db.list_collection_names() else "campanas"

INDICES = [
    ("usuarios", [("correo", 1)], {"unique": True, "name": "idx_correo_unico"}),
    ("publicaciones", [("usuario_id", 1)], {"name": "idx_usuario"}),
    ("publicaciones", [("categoria", 1), ("fecha_publicacion", -1)], {"name": "idx_categoria_fecha"}),
    ("reacciones", [("publicacion_id", 1)], {"name": "idx_publicacion"}),
    ("reacciones", [("usuario_id", 1)], {"name": "idx_usuario"}),
    ("comentarios", [("publicacion_id", 1)], {"name": "idx_publicacion"}),
    ("comentarios", [("usuario_id", 1)], {"name": "idx_usuario"}),
    (CAMP, [("publicaciones_asociadas", 1)], {"name": "idx_publicaciones_asociadas"}),
]

for col, campos, opciones in INDICES:
    nombre = db[col].create_index(campos, **opciones)
    print(f"[OK] {col:15} -> {nombre}")

print("\nÍndices por colección:")
for col in ["usuarios", "publicaciones", "reacciones", "comentarios", CAMP]:
    print(f"{col:15} {list(db[col].index_information().keys())}")