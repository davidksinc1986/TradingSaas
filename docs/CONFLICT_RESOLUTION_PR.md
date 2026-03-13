# Resolución de conflictos del PR

Si GitHub muestra **"This branch has conflicts that must be resolved"**, ejecuta:

```bash
scripts/resolve_conflicts_local.sh main
```

Si te sigue saliendo el mismo mensaje en GitHub, normalmente significa una de estas dos cosas:

1. No hiciste `git push --force-with-lease` después del rebase/resolución.
2. Tu rama `main` remota avanzó de nuevo y debes repetir el proceso.

Este flujo intenta resolver automáticamente los conflictos más frecuentes en:

- `app/routers/api.py`
- `app/static/admin.js`
- `app/static/styles.css`
- `app/templates/base.html`
- `app/templates/index.html`
- `app/templates/login.html`

Luego revisa los cambios y publica:

```bash
git push --force-with-lease
```

> Nota: si quedan archivos en conflicto, el script te los listará para resolverlos manualmente.
