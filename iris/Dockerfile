# Dockerfile para el Agente Iris
# Utiliza un build multi-etapa para optimizar el tamaño y la seguridad.

# --- Etapa 1: Builder ---
# Esta etapa instala las dependencias en un entorno virtual.
FROM python:3.10-slim as builder

WORKDIR /opt/builder

# Instala dependencias del sistema por si alguna librería lo necesita
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Crea un entorno virtual
RUN python -m venv /opt/venv

# Activa el entorno virtual
ENV PATH="/opt/venv/bin:$PATH"

# Copia el fichero de requerimientos e instala las dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# --- Etapa 2: Runtime ---
# Esta es la imagen final que se ejecutará en producción.
FROM python:3.10-slim

WORKDIR /app

# Copia el entorno virtual con las dependencias desde la etapa de build
COPY --from=builder /opt/venv /opt/venv

# Crea un usuario no-root para ejecutar la aplicación
RUN useradd --create-home --shell /bin/bash iris_user
USER iris_user

# Copia el código de la aplicación
COPY --chown=iris_user:iris_user ./core/ /app/core/
COPY --chown=iris_user:iris_user ./config/ /app/config/

# Activa el entorno virtual para el usuario final
ENV PATH="/opt/venv/bin:$PATH"

# Define las variables de entorno por defecto (pueden ser sobreescritas en ejecución)
ENV GCP_PROJECT_ID="your-gcp-project-id"
ENV IRIS_CONFIG_PATH="/app/config/rules.yaml"
ENV DRY_RUN="false"

# Punto de entrada para ejecutar el agente
ENTRYPOINT ["python", "-m", "core.iris_alert_manager"]
