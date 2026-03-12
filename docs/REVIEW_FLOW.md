# Revisión profesional inicial (flow multiusuario/multiaccount)

## Estado inicial validado en código

- Existe separación de roles `admin` y `user` con middleware por dependencia (`current_user`, `admin_user`).
- El super user puede activar/desactivar usuarios y permisos por plataforma.
- Hay modelo de grants por usuario/plataforma con límites de símbolos y movimientos.
- Cada conector soporta `market_type` (spot/futures/forex/cfd/signals).
- Hay webhook de TradingView con passphrase opcional y forwarding a conector destino.

## Hardening aplicado en esta iteración

1. **Corrección de defaults mutables en modelos de entrada** para evitar fuga de estado entre requests.
2. **Validación fuerte de parámetros de estrategia**:
   - `risk_per_trade` limitado a `(0, 0.1]`
   - `min_ml_probability` limitado a `[0, 1]`
3. **Cifrado robusto por defecto**:
   - Si `CREDENTIALS_KEY` no está configurada, se deriva una llave Fernet válida desde `SECRET_KEY`.
4. **Token cookie más seguro**:
   - Rechazo explícito de formato inválido.
   - Cookie con `httponly`, `samesite=lax`, `max_age` y `secure` automático en HTTPS.

## Preguntas clave para dejarla “a prueba de fallos”

1. ¿Quieres **aislamiento por tenant/empresa** real (multi-tenant) o solo super-admin global + usuarios?
2. ¿Deseas un **RBAC más fino** (ej: soporte, operador, analista) además de admin/user?
3. ¿Qué exchanges/brokers se consideran **prioridad de producción** (Binance spot/futures, Bybit, OKX, MT5)?
4. ¿Qué política de riesgo obligatoria quieres aplicar a nivel global?
   - pérdida máxima diaria por cuenta
   - máximo de operaciones por hora
   - stop de emergencia (kill switch)
5. ¿Los usuarios podrán usar **API keys de solo lectura + ejecución**, prohibiendo siempre withdrawals?
6. ¿Quieres **2FA obligatoria** para login de usuarios y especialmente super user?
7. ¿Qué auditoría necesitas por compliance?
   - bitácora inmutable de cambios de políticas y permisos
   - historial de activado/desactivado de usuarios/cuentas
8. ¿Cuál será la infraestructura objetivo inicial?
   - VPS único (rápido para iniciar)
   - Docker Compose
   - Kubernetes
9. ¿Cuál será el SLO esperado?
   - uptime objetivo (99.9/99.99)
   - RTO/RPO para recuperación ante fallos
10. ¿Deseas ejecución de estrategias en **jobs asíncronos** (Celery/RQ/Arq) con colas y reintentos?

## Próximo bloque recomendado

- Pruebas automatizadas de API (auth, admin grants, connector policies, webhooks).
- Idempotencia y locking por ejecución de estrategia.
- Circuit breakers / retry policies por exchange.
- Métricas y alertas (Prometheus + Grafana + logs estructurados).
- Plan de despliegue productivo con backup y rollback.

## Decisiones aplicadas en esta fase

- Super user por defecto: `davidksinc / M@davi19!` (configurable por entorno).
- Registro público deshabilitado: usuarios creados por super user.
- Usuarios finales: dashboard de solo lectura + actualización de credenciales de conectores + cambio de nombre.
- Centro de operaciones centralizado en panel Admin para control de usuarios, políticas y límites.
- Riesgo por monto configurable por conector usando `max_risk_amount` en `config`.
