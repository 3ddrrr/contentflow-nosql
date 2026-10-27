import os
import sys
import certifi
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ConfigurationError, OperationFailure

load_dotenv()


def conectar():
    """Devuelve (client, db) o termina con un mensaje claro."""
    uri = os.getenv("MONGO_URI")
    nombre = os.getenv("DB_NAME")
    if not uri or not nombre:
        sys.exit("ERROR: faltan MONGO_URI o DB_NAME en el archivo .env")
    try:
        client = MongoClient(uri, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=30000)
        client.admin.command("ping")
        return client, client[nombre]
    except OperationFailure as e:
        sys.exit(f"ERROR de autenticación o permisos: {e.details.get('errmsg', e)}")
    except ConfigurationError as e:
        sys.exit(f"ERROR de URI o DNS (prueba otra red): {e}")
    except ConnectionFailure as e:
        sys.exit(f"ERROR de conexión (revisa Network Access): {e}")