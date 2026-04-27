# Procedimiento de Release

> Cómo versionar y publicar releases de Taskboard MCP.

---

## Versionado (SemVer)

Seguimos [Semantic Versioning](https://semver.org/lang/es/): `MAJOR.MINOR.PATCH`

| Tipo | Cuándo usar | Ejemplo |
|------|-------------|---------|
| **MAJOR** | Breaking changes (schema changes, API incompatible, removal de features) | `1.0.0` → `2.0.0` |
| **MINOR** | Nuevas features backwards-compatible | `1.0.0` → `1.1.0` |
| **PATCH** | Bug fixes, cambios menores | `1.0.0` → `1.0.1` |

### Reglas

- **MAJOR**: Solo si hay cambios en el schema de SQLite, removal de herramientas MCP, o cambios incompatibles en la REST API
- **MINOR**: Nuevas herramientas MCP, nuevas páginas en el dashboard, nuevas endpoints de API
- **PATCH**: Bug fixes en store, templates, rutas, sin cambios de funcionalidad
- **Pre-release**: `1.1.0-alpha.1`, `1.1.0-beta.1` para testing antes de release final

---

## Flujo de Release

### 1. Preparación

```bash
# Asegurar estar en main y al día
git checkout main
git pull origin main

# Verificar que todos los tests pasan
uv run pytest tests/ -v --cov=taskboard
```

### 2. Checklist antes de versionar

- [ ] Todos los tests pasan (`uv run pytest tests/ -v`)
- [ ] Coverage >= 90%
- [ ] No hay `print()` en producción (solo logging)
- [ ] No hay TODOs pendientes en código nuevo
- [ ] Changelog actualizado con cambios desde la última versión
- [ ] `.gitignore` no incluye archivos que deberían versionarse
- [ ] Docker build funciona (`docker compose build`)
- [ ] No hay secrets ni credenciales en el código

### 3. Crear el tag

```bash
# Actualizar versión en pyproject.toml
# version = "X.Y.Z"

# Commitear el cambio de versión
git add pyproject.toml
git commit -m "chore: bump version to X.Y.Z"

# Crear tag anotado
git tag -a v0.2.0 -m "v0.2.0: descripción de los cambios principales"

# Push tag
git push origin main --tags
```

### 4. Crear GitHub Release

```bash
gh release create v0.2.0 \
  --title "v0.2.0" \
  --notes "## Cambios

### Nuevas features
- Feature 1
- Feature 2

### Bug fixes
- Fix 1

### Breaking changes (si aplica)
- Cambio 1"
```

O manualmente desde https://github.com/aleka/taskboard-mcp/releases/new

---

## Formato del Tag Message

```
v0.2.0

Nuevas features:
- Added timeline view to dashboard
- CSV export with date range filters

Bug fixes:
- Fixed thread safety in concurrent writes
- Fixed HTMX partial refresh on status change
```

---

## Formato de GitHub Release Notes

```markdown
## v0.2.0

### Nuevas features
- Descripción de la feature

### Bug fixes
- Descripción del fix

### Cambios internos
- Refactors, mejoras de performance, etc.

### Breaking changes (si aplica)
- Qué cambió y cómo migrar
```

---

## Rollback

Si algo sale mal después de un release:

```bash
# Revertir al tag anterior
git checkout v0.1.0

# O crear un patch release
git checkout main
git tag -a v0.2.1 -m "v0.2.1: hotfix para ..."
git push origin main --tags
```

---

## Historial de Versiones

| Versión | Fecha | Descripción |
|---------|-------|-------------|
| `0.1.0` | 2026-04-26 | Versión inicial — MCP server + web dashboard + REST API |
| `0.2.0` | 2026-04-27 | Nuevas tools MCP (delete_task, delete_project, tags), task detail page, design system CSS, cache busting, HTMX compliance fixes, XSS sanitization |
