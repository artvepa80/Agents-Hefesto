#!/bin/bash
# Script para configurar Stripe de forma segura

echo "🔐 Configuración Segura de Stripe API"
echo "======================================"
echo ""
echo "Por favor, ve a: https://dashboard.stripe.com/apikeys"
echo ""
echo "Copia tu Secret Key (sk_live_...) y ejecútalo así:"
echo ""
echo "  export STRIPE_SECRET_KEY='tu_key_aqui'"
echo ""
echo "O crea un archivo .env:"
echo "  echo 'STRIPE_SECRET_KEY=tu_key_aqui' > .env"
echo ""
echo "Luego ejecuta: source .env"
