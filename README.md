# Cloud Function — se activa al subir un archivo al bucket

Este proyecto implementa una Cloud Function de **2ª generación**, escrita en Python 3.15 y diseñada para ejecutarse cuando se sube o reemplaza un archivo en un bucket de Cloud Storage.

La función recibe el evento `google.cloud.storage.object.v1.finalized`, extrae el nombre, el tamaño y el tipo de contenido del archivo, y registra el resultado en Cloud Logging con formato JSON. También registra advertencias y errores sin exponer el procesamiento a una excepción silenciosa.

## Arquitectura del proceso

El flujo es:

1. Un usuario o aplicación sube un archivo al bucket.
2. Cloud Storage genera un evento de objeto finalizado.
3. Eventarc entrega ese evento a la Cloud Function.
4. La función valida el payload y extrae los metadatos.
5. Cloud Logging conserva los resultados y los errores.

![Arquitectura: subida de archivo, Cloud Storage, Eventarc, Cloud Function y Cloud Logging](https://home.agenda-master.com.mx/storage/turing/dia.png)

## Archivos del proyecto

- `src/main.py`: contiene la función `on_file_upload` y las funciones de extracción y validación.
- `src/test_main.py`: pruebas unitarias de éxito, casos límite y errores.
- `src/requirements.txt`: dependencias de ejecución.
- `src/docs/img`: capturas de los pasos realizados en Google Cloud.

# Configuración paso a paso en Google Cloud

## 1. Acceder al proyecto y revisar los permisos

Abra Google Cloud, seleccione el proyecto y revise la sección **IAM y administración**. La captura muestra el proyecto utilizado y el menú donde se administran los recursos y las identidades.

![Acceso a Google Cloud y al proyecto](https://home.agenda-master.com.mx/storage/turing/step1.png)

Desde el menú lateral puede abrir **IAM y administración → IAM** para consultar los principales accesos asignados al proyecto.

![Menú de IAM y administración](https://home.agenda-master.com.mx/storage/turing/step2.png)

En **Permisos para el proyecto**, revise qué usuarios, cuentas de servicio y roles tienen acceso a los recursos. No conceda permisos que no sean necesarios para el ejercicio.

![Permisos actuales del proyecto](https://home.agenda-master.com.mx/storage/turing/step3.png)

Para agregar un colaborador, use **Otorgar acceso**, introduzca su correo electrónico y seleccione un rol mínimo. En el ejemplo se asignó el rol **Lector**, adecuado para consultar recursos sin modificar su configuración.

![Otorgar acceso con el rol Lector](https://home.agenda-master.com.mx/storage/turing/step4.png)

## 2. Entrar a Cloud Storage

Después de confirmar la identidad y los permisos, vuelva a la página principal y entre a **Cloud Storage** desde el menú de productos o el buscador.

![Página principal de bienvenida a Google Cloud](https://home.agenda-master.com.mx/storage/turing/step5.png)

La consola de Cloud Storage permite crear y administrar buckets. Esta sección se usará para guardar los archivos que dispararán la función.

![Consola de Cloud Storage](https://home.agenda-master.com.mx/storage/turing/step6.png)

Puede confirmar que la API de almacenamiento está disponible desde **APIs y servicios → Biblioteca**, buscando **Cloud Storage**.

![Detalles del servicio Cloud Storage](https://home.agenda-master.com.mx/storage/turing/info1.png)

## 3. Crear el bucket

Use **Crear bucket** y configure los parámetros básicos:

- Nombre: `eval_turing`.
- Ubicación: `northamerica-south1` (México).
- Clase de almacenamiento: `Standard`.
- Espacio de nombres: jerárquico deshabilitado.
- Acceso público: deshabilitado.
- Control de acceso uniforme.
- Región seleccionada según su disponibilidad y requisitos de latencia.

![Primeros pasos y ubicación del bucket](https://home.agenda-master.com.mx/storage/turing/step7.png)

Configure la clase de almacenamiento, el control de acceso y la prevención de acceso público.

![Protección de datos y clase de almacenamiento](https://home.agenda-master.com.mx/storage/turing/step7.png)

Configure la duración de eliminación de objetos o mantenga la política según las necesidades del proyecto. En el ejemplo se seleccionó una retención personalizada de 3 días.

![Opciones de ciclo de vida y retención](https://home.agenda-master.com.mx/storage/turing/step7.png)

La vista de creación también muestra el código REST equivalente para el bucket. Después de completar los pasos, seleccione **Crear**.

![Configuración final del bucket y código REST](https://home.agenda-master.com.mx/storage/turing/step7.png)

Cuando el bucket esté creado, verá sus detalles, objetos, configuración, permisos y operaciones.

![Detalles del bucket evalu_turing](https://home.agenda-master.com.mx/storage/turing/step8.png)

## 4. Configurar el ciclo de vida del bucket

Abra la pestaña **Ciclo de vida** del bucket. Allí puede agregar reglas que cambien o eliminen objetos automáticamente según su antigüedad.

![Configuración del ciclo de vida](https://home.agenda-master.com.mx/storage/turing/step8.png)

Como ejemplo, cree una regla que elimine los objetos después de 30 días. Puede combinarse con una condición por prefijo, como `.jpg`, para controlar solamente ciertos archivos.

![Regla de ciclo de vida](https://home.agenda-master.com.mx/storage/turing/step9.png)

Puede limitar la regla con una condición de nombre de objeto y una fecha o antigüedad mínima.

![Acción y condiciones de la regla](https://home.agenda-master.com.mx/storage/turing/step10.png)

Una regla adicional puede establecer la clase de almacenamiento en **Nearline** después de un mes y conservar ahí las copias menos utilizadas.

![Selección de la acción de ciclo de vida](https://home.agenda-master.com.mx/storage/turing/step10.png)

En **Permisos**, revise que se hayan creado las cuentas de servicio y los roles necesarios. El bucket debe permitir su administración y lectura sin habilitar el acceso público.

![Permisos asociados al bucket](https://home.agenda-master.com.mx/storage/turing/step 11.png)

## 5. Crear una regla personalizada

Para definir una condición fuera de las reglas básicas, use **Condiciones** y complete el título y la descripción.

En el ejemplo se creó una condición llamada `Días laborales`, basada en la condición de **Día de la semana** con el operador **Antes**, restringida a días posteriores a viernes y a la zona horaria estándar central.

![Creación de una condición personalizada](https://home.agenda-master.com.mx/storage/turing/step12.png)

Guarde la condición y revisela junto con las demás reglas del bucket.

## 6. Preparar las APIs necesarias

Abra **Cloud Run**, que es el servicio administrado usado por las Cloud Functions de 2ª generación.

![Consola de Cloud Run](https://home.agenda-master.com.mx/storage/turing/step13.png)

En **APIs y servicios → Biblioteca**, confirme que **Cloud Build** está disponible. Cloud Build compila la imagen a partir del código fuente.

![Detalles de Cloud Build API](https://home.agenda-master.com.mx/storage/turing/info1.2.png)

Compruebe también que estén visibles las APIs necesarias: Cloud Storage, Cloud Functions, Cloud Logging, Eventarc y Cloud Pub/Sub.

![Catálogo de APIs necesarias](https://home.agenda-master.com.mx/storage/turing/info1.3.png)

Desde el botón **Habilitar APIs y servicios**, habilite las APIs requeridas por la función y por el activador de eventos.

![Habilitación de Eventarc y Cloud Pub/Sub](https://home.agenda-master.com.mx/storage/turing/info 13.png)

Si Google Cloud solicita otorgar roles, revise cuidadosamente el alcance antes de continuar:

- Eventarc necesita el rol `roles/eventarc.eventReceiver` sobre la cuenta de servicio.
- El receptor de eventos de Cloud Storage necesita permisos para consumir las publicaciones.
- Cloud Pub/Sub necesita `roles/iam.serviceAccountTokenCreator` para generar tokens de identidad.

![Solicitud de rol para Eventarc](https://home.agenda-master.com.mx/storage/turing/info 13.1.png)

![Asignación del receptor de eventos](https://home.agenda-master.com.mx/storage/turing/info 13.2.png)

![Permisos requeridos por el servicio de Cloud Storage](https://home.agenda-master.com.mx/storage/turing/info 13.3.png)

![Permisos requeridos por Cloud Pub/Sub](https://home.agenda-master.com.mx/storage/turing/info 13.4.png)

Otorgue los roles solo a las cuentas de servicio que aparecerán en la configuración del activador.

# Instalar, probar y ejecutar localmente

Desde la raíz del proyecto, cree y active un entorno virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Instale las dependencias y ejecute las pruebas:

```bash
python3 -m pip install -r src/requirements.txt
python3 -m pip install pytest
python3 -m pytest src/test_main.py -v
```

Las pruebas verifican:

- Extracción correcta de metadatos.
- Conversión de tamaño a bytes y a kilobytes.
- Valor predeterminado de `application/octet-stream`.
- Tamaño inválido o ausente sin detener el flujo.
- Errores controlados cuando faltan `bucket` o `name`.
- Registro estructurado de errores.

# Desplegar la Cloud Function

Antes del despliegue debe habilitarse **Cloud Functions API**, **Cloud Storage API**, **Cloud Run API**, **Eventarc API**, **Cloud Build API**, **Cloud Pub/Sub API** y **Cloud Logging API**.

## Configuración de origen

En la configuración de compilación de Cloud Run o Cloud Functions:

- Rama: `main`.
- Tipo de compilación: fuente mediante paquetes de compilación.
- Directorio de contexto: `/src`.
- Punto de entrada: `on_file_upload`.
- Entorno: Python 3.15.

![Configuración de compilación con Python](https://home.agenda-master.com.mx/storage/turing/step17.png)

## Crear el activador

En **Eventarc → Activadores**, cree un activador llamado `exportador-metadatos`:

- Tipo de evento: `google.cloud.storage.object.v1.finalized`.
- Tipo de destino: Cloud Run.
- Bucket: `eval_turing`.
- Región: `northamerica-south1`.
- Cuenta de servicio predeterminada o una cuenta creada específicamente para el activador.
- Servicio Cloud Run: el nombre de la función desplegada.

![Configuración del activador en Eventarc](https://home.agenda-master.com.mx/storage/turing/step14.png)

Para el acceso al activador se recomienda **Requerir autenticación**. Cuando sea necesario, habilite también los permisos de servicio y puede marcar **Identity and access management (IAM)** o **Identity-aware Proxy** según las políticas de la organización.

![Opciones de autenticación del activador](https://home.agenda-master.com.mx/storage/turing/step15.png)

Después de guardar, seleccione el bucket desde el activador y revise el resumen antes de finalizar.

# Comportamiento de la función

Cuando llega un evento válido, la función registra un mensaje similar a:

```json
{
  "event": "file_metadata_extracted",
  "bucket": "eval_turing",
  "name": "factura-001.pdf",
  "size_bytes": 24576,
  "size_kb": 24.0,
  "content_type": "application/pdf"
}
```

Si falta `bucket` o `name`, registra un `validation_error` y propaga `ValueError`. Si ocurre otro problema inesperado, registra el tipo de error y el traceback y vuelve a propagar la excepción para permitir el reintento.

## Probar una subida

Suba un archivo al bucket desde la consola o con `gsutil`:

```bash
gsutil cp prueba.pdf gs://eval_turing/prueba.pdf
```

Luego abra **Logging → Explorador de registros** y filtre por el identificador del servicio o por `process-file-upload`.

La subida debe generar en la función los eventos `file_upload_received`, `file_metadata_extracted` y `file_upload_processed`. Los casos sin tamaño o sin tipo de contenido también pueden generar avisos, pero no interrumpen el procesamiento.
