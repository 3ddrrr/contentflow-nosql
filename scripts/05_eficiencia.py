import json
import re
import statistics
import sys
import time
from pathlib import Path
from db import conectar

EVID = Path(__file__).resolve().parent.parent / "evidencias"
REPETICIONES = 5

# (nombre, colección, filtro, orden)
FIND = [
    ("Publicaciones por categoría, orden por fecha", "publicaciones",
     {"categoria": "Tecnología"}, {"fecha_publicacion": -1}),
    ("Publicaciones de un usuario", "publicaciones", {"usuario_id": "user_359"}, None),
    ("Reacciones de una publicación", "reacciones", {"publicacion_id": "pub_201"}, None),
    ("Comentarios de un usuario", "comentarios", {"usuario_id": "user_329"}, None),
    ("Usuario por correo", "usuarios", {"correo": "jdouglas@gmail.com"}, None),
]


def pipelines(camp):
    top_usuarios = [
        {"$lookup": {"from": "publicaciones", "localField": "_id", "foreignField": "usuario_id", "as": "pubs"}},
        {"$lookup": {"from": "comentarios", "localField": "_id", "foreignField": "usuario_id", "as": "coms"}},
        {"$lookup": {"from": "reacciones", "localField": "_id", "foreignField": "usuario_id", "as": "reacs"}},
        {"$project": {"nombre": 1, "total": {"$add": [{"$size": "$pubs"}, {"$size": "$coms"}, {"$size": "$reacs"}]}}},
        {"$sort": {"total": -1}},
        {"$limit": 10},
    ]
    impacto_campanas = [
        {"$lookup": {"from": "reacciones", "localField": "publicaciones_asociadas", "foreignField": "publicacion_id", "as": "reacs"}},
        {"$project": {"nombre": 1, "reacciones": {"$size": "$reacs"}}},
        {"$sort": {"reacciones": -1}},
        {"$limit": 10},
    ]
    return [
        ("Agregación: top 10 usuarios más activos", "usuarios", top_usuarios),
        ("Agregación: impacto de campañas", camp, impacto_campanas),
    ]


def mediana_ms(fn):
    tiempos = []
    for _ in range(REPETICIONES):
        t0 = time.perf_counter()
        fn()
        tiempos.append((time.perf_counter() - t0) * 1000)
    return round(statistics.median(tiempos), 1)


def medir(db):
    camp = "campañas" if "campañas" in db.list_collection_names() else "campanas"
    resultados = []

    for nombre, col, filtro, orden in FIND:
        cmd = {"find": col, "filter": filtro}
        if orden:
            cmd["sort"] = orden
        ex = db.command("explain", cmd, verbosity="executionStats")
        plan = json.dumps(ex["queryPlanner"]["winningPlan"])
        etapa = "IXSCAN" if "IXSCAN" in plan else "COLLSCAN"
        m = re.search(r'"indexName": "([^"]+)"', plan)
        stats = ex["executionStats"]

        def ejecutar(col=col, filtro=filtro, orden=orden):
            c = db[col].find(filtro)
            if orden:
                c = c.sort(list(orden.items()))
            return list(c)

        resultados.append({
            "consulta": nombre, "etapa": etapa, "indice": m.group(1) if m else "-",
            "docs_examinados": stats["totalDocsExamined"],
            "docs_devueltos": stats["nReturned"],
            "ms_servidor": stats["executionTimeMillis"],
            "ms_cliente": mediana_ms(ejecutar),
        })

    for nombre, col, pipe in pipelines(camp):
        resultados.append({
            "consulta": nombre, "etapa": "-", "indice": "-",
            "docs_examinados": None,
            "docs_devueltos": len(list(db[col].aggregate(pipe))),
            "ms_servidor": None,
            "ms_cliente": mediana_ms(lambda col=col, pipe=pipe: list(db[col].aggregate(pipe))),
        })
    return resultados


def mostrar(titulo, res):
    print(f"\n=== {titulo} ===")
    print(f"{'Consulta':46} {'Etapa':8} {'Examin.':>8} {'Devuel.':>8} {'ms srv':>7} {'ms cli':>8}")
    for r in res:
        print(f"{r['consulta']:46} {r['etapa']:8} {str(r['docs_examinados']):>8} "
              f"{r['docs_devueltos']:>8} {str(r['ms_servidor']):>7} {r['ms_cliente']:>8}")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    if modo in ("antes", "despues"):
        client, db = conectar()
        res = medir(db)
        EVID.mkdir(exist_ok=True)
        (EVID / f"eficiencia_{modo}.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
        mostrar(f"MEDICIÓN {modo.upper()} DE ÍNDICES", res)
        print(f"\nGuardado en evidencias/eficiencia_{modo}.json")
    elif modo == "comparar":
        a = json.loads((EVID / "eficiencia_antes.json").read_text(encoding="utf-8"))
        d = json.loads((EVID / "eficiencia_despues.json").read_text(encoding="utf-8"))
        print(f"\n{'Consulta':46} {'ANTES (etapa/exam/ms srv/ms cli)':36} {'DESPUÉS':36}")
        for x, y in zip(a, d):
            ta = f"{x['etapa']}/{x['docs_examinados']}/{x['ms_servidor']}/{x['ms_cliente']}"
            td = f"{y['etapa']}/{y['docs_examinados']}/{y['ms_servidor']}/{y['ms_cliente']}"
            print(f"{x['consulta']:46} {ta:36} {td:36}")
    else:
        print("Uso: python scripts\\05_eficiencia.py [antes | despues | comparar]")