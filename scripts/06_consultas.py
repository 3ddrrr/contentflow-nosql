import json
import time
from datetime import datetime
from pathlib import Path
from pprint import pprint
from db import conectar

EVID = Path(__file__).resolve().parent.parent / "evidencias"
MOSTRAR = 5  # filas que se imprimen por consulta
DIAS = {1: "Domingo", 2: "Lunes", 3: "Martes", 4: "Miércoles", 5: "Jueves", 6: "Viernes", 7: "Sábado"}

client, db = conectar()
CAMP = "campañas" if "campañas" in db.list_collection_names() else "campanas"
RESULTADOS = []


def ejecutar(num, titulo, requerimiento, fn):
    t0 = time.perf_counter()
    filas = fn()
    ms = (time.perf_counter() - t0) * 1000
    print(f"\n{'=' * 72}\nCONSULTA {num}: {titulo}\nRequerimiento: {requerimiento}")
    print(f"Registros devueltos: {len(filas)} | Tiempo: {ms:.0f} ms")
    for f in filas[:MOSTRAR]:
        pprint(f, sort_dicts=False, width=100)
    if len(filas) > MOSTRAR:
        print(f"... y {len(filas) - MOSTRAR} más")
    RESULTADOS.append({"consulta": num, "titulo": titulo, "registros": len(filas),
                       "ms": round(ms), "datos": filas})


# ---------- IE4: lectura con filtros, proyecciones y ordenamientos ----------

ejecutar(1, "Usuarios móviles de género femenino",
         "Segmentar la audiencia por dispositivo y género",
         lambda: list(db.usuarios.find(
             {"dispositivo": "Móvil", "genero": "Femenino"},
             {"nombre": 1, "pais": 1, "fecha_registro": 1, "_id": 0}
         ).sort("fecha_registro", -1).limit(10)))

ejecutar(2, "Últimas publicaciones de Tecnología",
         "Revisar el contenido reciente de una categoría",
         lambda: list(db.publicaciones.find(
             {"categoria": "Tecnología"},
             {"contenido": 0}
         ).sort("fecha_publicacion", -1).limit(10)))

ejecutar(3, "Comentarios más valorados",
         "Identificar los comentarios con más de 90 likes",
         lambda: list(db.comentarios.find(
             {"likes": {"$gt": 90}},
             {"comentario": 1, "likes": 1, "usuario_id": 1, "_id": 0}
         ).sort("likes", -1)))

ejecutar(4, "Videos con #cultura desde marzo de 2025",
         "Búsqueda compuesta: hashtag, tipo de publicación y rango de fechas",
         lambda: list(db.publicaciones.find(
             {"hashtags": "#cultura", "tipo": "Video",
              "fecha_publicacion": {"$gte": datetime(2025, 3, 1)}},
             {"categoria": 1, "hashtags": 1, "fecha_publicacion": 1}
         ).sort("fecha_publicacion", -1)))

# ---------- IE5: operadores y agregaciones de negocio ----------

ejecutar(5, "Top 10 usuarios más activos",
         "Usuarios con más publicaciones, comentarios y reacciones",
         lambda: list(db.usuarios.aggregate([
             {"$lookup": {"from": "publicaciones", "localField": "_id", "foreignField": "usuario_id", "as": "pubs"}},
             {"$lookup": {"from": "comentarios", "localField": "_id", "foreignField": "usuario_id", "as": "coms"}},
             {"$lookup": {"from": "reacciones", "localField": "_id", "foreignField": "usuario_id", "as": "reacs"}},
             {"$project": {"nombre": 1, "pais": 1,
                           "publicaciones": {"$size": "$pubs"},
                           "comentarios": {"$size": "$coms"},
                           "reacciones": {"$size": "$reacs"}}},
             {"$addFields": {"total": {"$add": ["$publicaciones", "$comentarios", "$reacciones"]}}},
             {"$sort": {"total": -1, "_id": 1}},
             {"$limit": 10},
         ])))

ejecutar(6, "Publicaciones más populares",
         "Contenidos con más reacciones y a qué categoría y tipo pertenecen",
         lambda: list(db.reacciones.aggregate([
             {"$group": {"_id": "$publicacion_id", "reacciones": {"$sum": 1}}},
             {"$sort": {"reacciones": -1, "_id": 1}},
             {"$limit": 10},
             {"$lookup": {"from": "publicaciones", "localField": "_id", "foreignField": "_id", "as": "pub"}},
             {"$unwind": "$pub"},
             {"$project": {"_id": 0, "publicacion": "$_id", "categoria": "$pub.categoria",
                           "tipo": "$pub.tipo", "reacciones": 1}},
         ])))


def horarios():
    filas = list(db.reacciones.aggregate([
        {"$group": {"_id": {"dia": {"$dayOfWeek": "$fecha"}, "hora": {"$hour": "$fecha"}},
                    "interacciones": {"$sum": 1}}},
        {"$sort": {"interacciones": -1, "_id.dia": 1, "_id.hora": 1}},
        {"$limit": 10},
        {"$project": {"_id": 0, "dia": "$_id.dia", "hora": "$_id.hora", "interacciones": 1}},
    ]))
    for f in filas:
        f["dia"] = DIAS[f["dia"]]
    return filas


ejecutar(7, "Mejores horarios de interacción (hora UTC)",
         "Día y hora con más reacciones, para decidir cuándo publicar", horarios)

ejecutar(8, "Perfil de la audiencia",
         "Reacciones por género y dispositivo del usuario",
         lambda: list(db.reacciones.aggregate([
             {"$lookup": {"from": "usuarios", "localField": "usuario_id", "foreignField": "_id", "as": "u"}},
             {"$unwind": "$u"},
             {"$group": {"_id": {"genero": "$u.genero", "dispositivo": "$u.dispositivo"},
                         "reacciones": {"$sum": 1}}},
             {"$sort": {"reacciones": -1}},
             {"$project": {"_id": 0, "genero": "$_id.genero", "dispositivo": "$_id.dispositivo",
                           "reacciones": 1}},
         ])))

ejecutar(9, "Impacto de campañas frente a sus metas",
         "Reacciones y comentarios logrados por campaña vs. métricas objetivo",
         lambda: list(db[CAMP].aggregate([
             {"$lookup": {"from": "reacciones", "localField": "publicaciones_asociadas",
                          "foreignField": "publicacion_id", "as": "reacs"}},
             {"$lookup": {"from": "comentarios", "localField": "publicaciones_asociadas",
                          "foreignField": "publicacion_id", "as": "coms"}},
             {"$project": {"nombre": 1, "objetivo": 1,
                           "reacciones": {"$size": "$reacs"}, "comentarios": {"$size": "$coms"},
                           "meta_likes": "$metricas_objetivo.likes",
                           "meta_comentarios": "$metricas_objetivo.comentarios"}},
             {"$addFields": {
                 "cumplimiento_likes_pct": {"$round": [{"$multiply": [
                     {"$divide": ["$reacciones", {"$max": ["$meta_likes", 1]}]}, 100]}, 1]},
                 "cumplimiento_comentarios_pct": {"$round": [{"$multiply": [
                     {"$divide": ["$comentarios", {"$max": ["$meta_comentarios", 1]}]}, 100]}, 1]}}},
             {"$sort": {"reacciones": -1, "_id": 1}},
             {"$limit": 10},
         ])))

ejecutar(10, "Categorías con mayor engagement",
         "Interacciones totales y promedio por publicación en cada categoría",
         lambda: list(db.publicaciones.aggregate([
             {"$lookup": {"from": "reacciones", "localField": "_id", "foreignField": "publicacion_id", "as": "r"}},
             {"$lookup": {"from": "comentarios", "localField": "_id", "foreignField": "publicacion_id", "as": "c"}},
             {"$group": {"_id": "$categoria", "publicaciones": {"$sum": 1},
                         "reacciones": {"$sum": {"$size": "$r"}},
                         "comentarios": {"$sum": {"$size": "$c"}}}},
             {"$addFields": {"interacciones": {"$add": ["$reacciones", "$comentarios"]}}},
             {"$addFields": {"promedio_por_publicacion": {"$round": [
                 {"$divide": ["$interacciones", "$publicaciones"]}, 2]}}},
             {"$sort": {"interacciones": -1}},
         ])))

EVID.mkdir(exist_ok=True)
(EVID / "resultados_consultas.json").write_text(
    json.dumps(RESULTADOS, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
print("\nResultados completos guardados en evidencias/resultados_consultas.json")