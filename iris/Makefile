# Makefile para el Agente Iris
# Automatiza el ciclo de vida de build, deploy y ejecución.

# --- Configuración de Variables ---
# Sobrescribir estas variables desde la línea de comandos si es necesario.
# Ejemplo: make build GCR_PROJECT_ID=mi-otro-proyecto

# Google Cloud
ifeq ($(GCP_PROJECT_ID),)
  GCP_PROJECT_ID := $(shell gcloud config get-value project)
endif
ifeq ($(GCP_REGION),)
  GCP_REGION := us-central1
endif

# Imagen de Contenedor
IMAGE_NAME := hefesto-iris-agent
IMAGE_TAG ?= latest
IMAGE_URL := gcr.io/$(GCP_PROJECT_ID)/$(IMAGE_NAME):$(IMAGE_TAG)

# Cloud Run Job
JOB_NAME := iris-alert-manager-job
SERVICE_ACCOUNT := iris-agent-sa@$(GCP_PROJECT_ID).iam.gserviceaccount.com

# Cloud Scheduler
SCHEDULER_JOB_NAME := iris-monitoring-schedule
SCHEDULE ?= "*/15 * * * *" # Cada 15 minutos

# --- Targets del Makefile ---

.PHONY: all build push deploy execute cron run-local clean

all: build

# Construye la imagen de Docker del agente Iris
build:
	@echo "🏗️  Construyendo imagen Docker: $(IMAGE_URL)..."
	docker build -t $(IMAGE_URL) -f Dockerfile .
	@echo "✅ Imagen construida exitosamente."

# Publica la imagen de Docker en Google Container Registry (GCR)
push:
	@echo "🚀 Publicando imagen en GCR: $(IMAGE_URL)..."
	docker push $(IMAGE_URL)
	@echo "✅ Imagen publicada exitosamente."

# Despliega el agente como un Cloud Run Job
# Nota: El job se crea pero no se ejecuta.
deploy:
	@echo "☁️  Desplegando Cloud Run Job: $(JOB_NAME)..."
	gcloud run jobs create $(JOB_NAME) \
		--image $(IMAGE_URL) \
		--region $(GCP_REGION) \
		--service-account $(SERVICE_ACCOUNT) \
		--set-env-vars="GCP_PROJECT_ID=$(GCP_PROJECT_ID)" \
		--set-env-vars="DRY_RUN=false" \
		--cpu=1 \
		--memory=512Mi \
		--max-retries=3 \
		--task-timeout=600 # 10 minutos
	@echo "✅ Job desplegado/actualizado exitosamente."

# Ejecuta el Cloud Run Job manualmente una vez
execute:
	@echo "▶️  Ejecutando el job $(JOB_NAME) manualmente..."
	gcloud run jobs execute $(JOB_NAME) --region $(GCP_REGION) --wait
	@echo "✅ Ejecución completada."

# Crea/Actualiza un Cloud Scheduler para ejecutar el job periódicamente
cron:
	@echo "⏰ Configurando Cloud Scheduler: $(SCHEDULER_JOB_NAME)..."
	gcloud scheduler jobs create http $(SCHEDULER_JOB_NAME) \
		--schedule="$(SCHEDULE)" \
		--http-method=POST \
		--uri="https://$(GCP_REGION)-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$(GCP_PROJECT_ID)/jobs/$(JOB_NAME):run" \
		--oauth-service-account-email=$(SERVICE_ACCOUNT) \
		--location=$(GCP_REGION) \
		--description="Ejecuta el agente Iris para monitorear alertas de OMEGA."
	@echo "✅ Scheduler configurado para ejecutar el job cada 15 minutos."

# Ejecuta el agente localmente para desarrollo y pruebas
run-local:
	@echo "💻 Ejecutando el agente localmente (Dry Run)..."
	docker run --rm -it \
		-e GCP_PROJECT_ID=$(GCP_PROJECT_ID) \
		-e DRY_RUN=true \
		-v $(shell pwd)/config:/app/config \
		$(IMAGE_URL)

# Limpia la imagen de Docker local
clean:
	@echo "🧹 Limpiando imagen Docker local..."
	docker rmi $(IMAGE_URL)
	@echo "✅ Imagen eliminada."

# --- Ayuda ---

help:
	@echo "Uso: make [target]"
	@echo ""
	@echo "Targets disponibles:"
	@echo "  build          Construye la imagen Docker del agente."
	@echo "  push           Publica la imagen en Google Container Registry."
	@echo "  deploy         Despliega/Actualiza el Cloud Run Job."
	@echo "  execute        Ejecuta el job manualmente una vez."
	@echo "  cron           Crea/Actualiza el Cloud Scheduler para ejecuciones periódicas."
	@echo "  run-local      Ejecuta el agente en un contenedor local para pruebas."
	@echo "  clean          Elimina la imagen Docker del sistema local."
	@echo "  help           Muestra esta ayuda."
