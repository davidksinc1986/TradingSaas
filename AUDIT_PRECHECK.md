# Revisión inicial y requisitos para auditoría completa

## Estado actual del repositorio

Se realizó una inspección inicial del repositorio y no se encontró código fuente de la aplicación ni estructura de proyecto (backend/frontend/tests/infra). Solo existe metadata de Git.

## Qué necesito para revisar la app “a prueba de fallos”

Para poder hacer una auditoría profesional completa (arquitectura, seguridad, multiusuario, trading, operación online y dashboards), necesito:

1. Código fuente completo (backend, frontend, workers, bots, integraciones de exchange).
2. Variables de entorno de ejemplo (`.env.example`) y documentación de despliegue.
3. Esquema de base de datos y migraciones.
4. Flujo de autenticación/autorización (roles: super user, user).
5. Módulos de habilitación por:
   - Usuario on/off
   - Cuenta on/off
   - Exchange/producto (spot/futures) on/off
   - Símbolos permitidos por usuario
6. Motor de estrategias y scheduler (frecuencia: 1h, etc.).
7. Manejo de API keys/secrets (cifrado, rotación, masking, auditoría).
8. Logs, métricas, trazas y alertas.
9. Pruebas existentes (unitarias, integración, e2e, carga, resiliencia).
10. Stack de infraestructura actual (Docker/K8s/VM, DB, colas, cache, CI/CD).

## Preguntas clave para dejarla “impecable”

1. ¿Qué exchanges exactos soportan hoy (Binance, Bybit, etc.) y qué APIs (spot/futures)?
2. ¿Dónde se guardan actualmente API keys y cómo se cifran?
3. ¿Existe control de riesgo por usuario/cuenta? (max drawdown, max daily loss, stop global)
4. ¿Hay kill-switch global del super user para pausar todas las operaciones?
5. ¿Cómo se evita doble ejecución de órdenes en jobs concurrentes o reintentos?
6. ¿Hay idempotencia de órdenes y reconciliación periódica con el exchange?
7. ¿Se usa RBAC formal para separar dashboard super user y dashboard usuario?
8. ¿Qué SLAs/objetivos de disponibilidad quieren para producción?
9. ¿Qué región/proveedor cloud usarán para despliegue?
10. ¿Necesitan cumplimiento específico (auditoría, retención de logs, privacidad)?

## Entregable propuesto al recibir código

1. Diagnóstico técnico completo por módulos.
2. Lista priorizada de fallos/riesgos (P0/P1/P2).
3. Plan de hardening (seguridad, resiliencia, observabilidad, rendimiento).
4. Refactor y fixes con pruebas automatizadas.
5. Blueprint de despliegue en servidor + runbooks operativos.
6. Checklist de “go-live” para producción.
