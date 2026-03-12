# Guía simple de despliegue (opción fácil y casi gratis)

## Recomendación inicial
Para empezar rápido, usa **Oracle Cloud Free Tier** (VPS gratuita) + Docker Compose.

## 1) Crear servidor
1. Crea cuenta en Oracle Cloud.
2. Lanza una VM Ubuntu (Always Free).
3. Abre puertos 80 y 443 en el Security List.

## 2) Instalar Docker
```bash
sudo apt update && sudo apt -y upgrade
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
sudo apt -y install docker-compose-plugin
```

## 3) Subir proyecto
```bash
git clone <TU_REPO_GIT> TradingSaas
cd TradingSaas
cp .env.example .env
```

## 4) Configurar variables
Editar `.env` mínimo:
- `SECRET_KEY`
- `CREDENTIALS_KEY` (Fernet real)
- `ADMIN_EMAIL=davidksinc`
- `ADMIN_NAME=davidksinc`
- `ADMIN_PASSWORD=M@davi19!`
- `DATABASE_URL` (para producción ideal PostgreSQL)

## 5) Correr con Docker
```bash
docker compose up -d --build
```

## 6) HTTPS (recomendado)
- Opción fácil: Cloudflare Tunnel o Nginx Proxy Manager + Let's Encrypt.
- Apunta tu dominio al servidor.

## 7) Operación centralizada
- Entra como super user.
- Crea usuarios desde Admin.
- Crea conectores por usuario.
- Define límites (símbolos, movimientos, riesgo por monto `max_risk_amount`).

## 8) Backups
- Respaldar DB cada noche.
- Guardar `.env` en gestor seguro (nunca en repositorio público).

