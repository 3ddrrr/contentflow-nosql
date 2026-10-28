
# ContentFlow - API REST con NoSQL

ContentFlow es una plataforma de gestión de contenidos y análisis de interacciones respaldada por una base de datos NoSQL (MongoDB) y desarrollada con Python y FastAPI. Este proyecto demuestra la implementación de un ciclo CRUD completo, validación de datos estricta, y consultas de agregación para análisis de negocio.

## 🚀 Requisitos Previos

Antes de comenzar, asegúrate de tener instalado:
* **Python 3.11** o superior.
* **Git** para clonar el repositorio.
* Una cuenta en **MongoDB Atlas** (o una instancia local de MongoDB).

## 🛠️ Instalación y Configuración Paso a Paso

Sigue estos pasos para levantar el entorno de desarrollo local.

### 1. Clonar el repositorio
Abre tu terminal y clona este proyecto:
```bash
git clone https://github.com/3ddrrr/contentflow-nosql.git
cd contentflow-nosql
```


### 2. Crear y activar el entorno virtual
Es una buena práctica aislar las dependencias del proyecto.
* **En Windows:**
  ```bash
  python -m venv venv
  .\venv\Scripts\activate
  ```
* **En macOS/Linux:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### 3. Instalar dependencias
Con el entorno activado, instala las librerías necesarias. Ejecuta estos comandos para asegurar las validaciones correctas (especialmente para los correos electrónicos):

```bash
pip install fastapi uvicorn pymongo python-dotenv
pip install "pydantic[email]"
pip install email-validator
```
*(Si tienes un archivo `requirements.txt` actualizado, puedes usar simplemente `pip install -r requirements.txt`).*

### 4. Configurar Variables de Entorno (.env)
Para conectar la API con la base de datos de manera segura, necesitas crear un archivo `.env` en la raíz del proyecto. **Nunca subas este archivo a GitHub.**

1. Crea un archivo nuevo llamado exactamente `.env`.
2. Añade las siguientes variables con tus credenciales de MongoDB:

```env
# URL de conexión a tu clúster de MongoDB Atlas (reemplaza <user> y <password>)
#esto va# MONGO_URI="mongodb+srv://<usuario>:<password>@cluster0.ejemplo.mongodb.net/?retryWrites=true&w=majority"
La URL de conexión en drivers, dandole a connect en cluster, luego opcion de drivers and clients libraries, seleccionando python
Esta URL: mongodb+srv://<db_username>:<db_password>@cluster0.ugzhooy.mongodb.net/
# Nombre de la base de datos
#esto va# DB_NAME="contentflow"
```

## 💻 Ejecución del Servidor

Una vez configurado todo, puedes levantar la API con Uvicorn. Desde la raíz del proyecto, ejecuta:

```bash - powershell
uvicorn api.main:app --reload
```

El servidor estará corriendo en: `http://127.0.0.1:8000`

Puedes acceder a la **documentación interactiva automática (Swagger UI)** navegando a:
👉 `http://127.0.0.1:8000/docs`

## 🧪 Pruebas con Postman

Para interactuar con la API en Postman, asegúrate de configurar los siguientes **Headers** globales en tus peticiones:
* `Content-Type`: `application/json`
* `api-key`: `mi_clave_secreta_123` *(Cabecera simulada para la evaluación)*

### Endpoints Principales:
* **POST** `/usuarios` - Crea un nuevo usuario (valida formato de correo y duplicidad).
* **GET** `/usuarios/{user_id}` - Obtiene los datos de un usuario específico.
* **PUT** `/usuarios/{user_id}` - Actualiza el dispositivo o país del usuario.
* **DELETE** `/usuarios/{user_id}` - Elimina un usuario del sistema.
* **GET** `/segmentacion/usuarios?pais=Chile` - Consulta de negocio: lista usuarios por país.
* **GET** `/metricas/publicaciones/{pub_id}` - Consulta analítica: total de reacciones y comentarios usando `$lookup`.

1. CREATE: Registro Exitoso
Método: POST
URL: http://127.0.0.1:8000/usuarios
Body (JSON):
{
    "nombre": "Juan Pérez",
    "correo": "juan.demo@ejemplo.com",
    "pais": "Chile",
    "genero": "Masculino",
    "dispositivo": "Móvil"
}

Respuesta Esperada: 201 Created y el ID del nuevo usuario (cópialo para usarlo después).


2. CONTROL DE ERRORES: Duplicados y Formatos Inválidos
Prueba de Duplicado (409): Envía la misma petición POST del paso 1 de nuevo. El sistema debe responder 409 Conflict.
Prueba de Validación (422): Cambia el correo a "juan.demo-sin-arroba" y envía el POST. El sistema debe responder 422 Unprocessable Entity.


3. READ: Consulta Analítica de Segmentación
Método: GET
URL: http://127.0.0.1:8000/segmentacion/usuarios?pais=Chile
Respuesta Esperada: 200 OK, listando los usuarios de Chile y el total encontrados.

4. UPDATE: Actualización de Datos
Método: PUT
URL: http://127.0.0.1:8000/usuarios/AQUI_TU_ID_GENERADO_EN_EL_PASO_1
Body (JSON):
{
    "dispositivo": "Tablet",
    "pais": "Argentina"
}
Respuesta Esperada: 200 OK ("Usuario actualizado con éxito").

5. READ: Consulta de Métricas de Agregación
Método: GET
URL: http://127.0.0.1:8000/metricas/publicaciones/demo_pub_1
Respuesta Esperada: 200 OK, devolviendo el resumen de reacciones y comentarios cruzados desde MongoDB usando $lookup.

6. DELETE: Eliminación de Registro
Método: DELETE
URL: http://127.0.0.1:8000/usuarios/AQUI_TU_ID_GENERADO_EN_EL_PASO_1
Respuesta Esperada: 204 No Content (cuerpo de respuesta vacío).

7. VERIFICACIÓN: Recurso no encontrado (404)
Método: GET
URL: http://127.0.0.1:8000/usuarios/AQUI_TU_ID_GENERADO_EN_EL_PASO_1
Respuesta Esperada: 404 Not Found (confirmando que el usuario ya no existe).






## 📁 Estructura del Proyecto

```text
contentflow-nosql/
│
├── api/
│   ├── main.py         # Endpoints de la API FastAPI
│   ├── models.py       # Modelos Pydantic para validación
│   └── database.py     # Configuración de base de datos
│
├── scripts/
│   ├── 01_conexion.py  # Pruebas de conexión
│   ├── db.py           # Conector reutilizable
│   └── ...             # Scripts de carga y agregación
│
├── .env                # Variables de entorno (¡NO SUBIR!)
├── .gitignore          # Archivos excluidos de Git
└── README.md           # Este archivo
```
