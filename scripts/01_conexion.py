import os
import sys
import time
import certifi

import dns.resolver
dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ["8.8.8.8", "1.1.1.1"]

from dotenv import load_dotenv
from pymongo import MongoClient, WriteConcern
from pymongo.errors import ConnectionFailure, ConfigurationError, OperationFailure

load_dotenv()
URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")


def conectar():
    """Devuelve (client, db) o termina el programa con un mensaje claro."""
    if not URI or not DB_NAME:
        sys.exit("ERROR: faltan MONGO_URI o DB_NAME en el archivo .env")
    try:
        client = MongoClient(
            URI,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=5000,
        )
        t0 = time.perf_counter()
        client.admin.command("ping")
        ms = (time.perf_counter() - t0) * 1000
        print(f"[OK] Ping exitoso en {ms:.0f} ms")
        return client, client[DB_NAME]
    except OperationFailure as e:
        sys.exit(f"ERROR de autenticación/permisos: {e.details.get('errmsg', e)}")
    except ConfigurationError as e:
        sys.exit(f"ERROR en la URI (¿caracteres especiales en la clave?): {e}")
    except ConnectionFailure as e:
        sys.exit(f"ERROR de conexión (¿IP no permitida en Network Access?): {e}")


if __name__ == "__main__":
    client, db = conectar()

    info = client.server_info()
    print(f"Versión de MongoDB : {info['version']}")
    print(f"Base de datos      : {db.name}")

    hello = client.admin.command("hello")
    print(f"Replica set        : {hello.get('setName')}")
    print(f"Nodo primario      : {hello.get('primary')}")
    print(f"Miembros           : {hello.get('hosts')}")

    print("\nColecciones existentes:")
    for nombre in db.list_collection_names():
        print(f"  - {nombre}: {db[nombre].count_documents({})} docs")

    col = db.get_collection("usuarios", write_concern=WriteConcern(w="majority"))
    print(f"\nWrite concern configurado: {col.write_concern.document}")
    print(f"Read preference          : {db.read_preference.name}")