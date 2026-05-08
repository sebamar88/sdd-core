# RunProof — Rebranding completo + Slash Commands Nativos + Fricción Mínima

**Fecha:** 2026-05-08  
**Estado:** Borrador — pendiente de aprobación  

---

## Contexto

La herramienta se llamaba SDD-Core, luego fue rebrandeada a ProofKit, pero ese nombre está tomado por otras empresas. El nombre definitivo es **RunProof**. Como la herramienta tiene 0 usuarios en producción y está 100% en fase de desarrollo, el rebranding es un refactor limpio sin consideraciones de backward compatibility.

Además del rebranding, se resuelven dos problemas de UX que impiden la adopción en herramientas AI.

---

## Problemas a resolver

1. **Rebranding incompleto**: el código aún usa `sdd` (legacy de SDD-Core), `proofkit` como nombre de CLI y paquete, y `.proofkit/` como directorio de estado.

2. **Visibilidad cero en Copilot**: `install-commands` escribe en `.github/copilot-prompts/sdd/` con archivos `.md` sin frontmatter. Copilot requiere `.github/prompts/*.prompt.md` con `mode: agent`.

3. **Fricción máxima para el agente**: los templates son listas de instrucciones, no agentes autónomos. El agente debe conocer el `change_id`, parsear salida coloreada, decidir el próximo comando y ejecutarlo — 3 a 4 pasos por fase.

---

## Objetivo

Refactor limpio a **RunProof** en todos los niveles, más un set de slash commands que permitan a cualquier agente AI avanzar un change completo con un solo comando, sin conocer el estado previo ni el `change_id`.

---

## Cambios de diseño

### 1. Rebranding completo: ProofKit → RunProof

#### Identidad

| Antes | Después |
|---|---|
| CLI: `proofkit` | CLI: `runproof` |
| PyPI: `proofkit-cli` | PyPI: `runproof-cli` |
| npm: `proofkit` | npm: `runproof` |
| Directorio: `.proofkit/` | Directorio: `.runproof/` |
| Constante: `SDD_DIR = ".proofkit"` | Constante: `SDD_DIR = ".runproof"` |
| Prefijo interno: `sdd` (schemas, templates, adapters) | Prefijo: `runproof` |

#### Archivos y directorios afectados

- `proofkit/` (paquete Python) → `runproof/`
- `proofkit/_types.py`: `SDD_DIR`, `REQUIRED_*`, `VERSION`, todas las strings con `sdd`/`proofkit`
- `proofkit/_wf_templates.py`: `_INTEGRATION_COMMAND_DIRS`, `_COMMAND_FILES`, schema keys
- `proofkit/templates/sdd/` → `runproof/templates/runproof/`
- `proofkit/templates/commands/sdd-*.md` → `runproof/templates/commands/runproof-*.md`
- `proofkit/templates/sdd/adapters/*.json`: campo `schema: "sdd.*"` → `schema: "runproof.*"`
- `bin/proofkit.js` → `bin/runproof.js`
- `pyproject.toml`: `name`, `scripts.proofkit` → `scripts.runproof`
- `package.json`: `name`, `bin.proofkit` → `bin.runproof`
- `CLAUDE.md`, `README.md`, docs internos

#### Schemas

Los schemas JSON (`adapter-capabilities.schema.json`, etc.) actualizan su campo `schema`:

```json
{ "schema": "runproof.adapter-capabilities.v1" }
```

---

### 2. `runproof next` — comando CLI de primera clase

Nuevo subcomando que encapsula toda la lógica de avance:

```bash
runproof next                         # detecta change activo, avanza todo lo posible
runproof next add-dark-mode           # change_id explícito opcional
runproof next --verify-with "pytest -x"
```

**Lógica interna:**
1. Detecta el change activo (ver sección 3)
2. Corre `runproof auto <id> --loop` para fases auto-ejecutables
3. Para fases que requieren artefacto humano: lee el skill de esa fase + escanea el repo → redacta el artefacto como borrador → lo escribe → llama `runproof ready <id>`
4. Reporta en una línea: qué avanzó + qué sigue

**Implementación:** nuevo subcomando en `cli.py` / `_workflow.py`, lógica de drafting en `_wf_changeops.py`.

---

### 3. Auto-detección de `change_id`

Todos los comandos que requieren `<change_id>` explícito deben inferirlo:

- Un solo change activo → usarlo silenciosamente
- Cero changes → error: `"No active changes. Create one with 'runproof new'"`
- Más de uno → listar y pedir selección interactiva

**Afecta:** `runproof auto`, `runproof verify`, `runproof transition`, `runproof log`, `runproof evidence`, `runproof pr-check`, `runproof next`.

---

### 4. `runproof status --json`

Salida machine-readable para que los slash commands tomen decisiones sin parsear texto coloreado:

```bash
runproof status --json
```

```json
{
  "change_id": "add-dark-mode",
  "phase": "specify",
  "profile": "standard",
  "next_action": "Complete specify.md and mark ready",
  "missing_artifacts": ["specify.md"],
  "can_auto_advance": false
}
```

**`can_auto_advance`:** `true` si `runproof next` puede avanzar sin intervención humana.  
**Implementación:** nueva rama en `print_status` / `_render.py`.

---

### 5. `constitution` como clave de memory

Agregar `"constitution"` a `MEMORY_KEYS` en `_types.py`. Vive en `.runproof/memory/constitution.md`.

**Template base** (`templates/runproof/memory/constitution.md`):

```markdown
# RunProof Constitution

## Tech Stack
<!-- Languages, frameworks, runtimes, and key libraries. -->

## Testing Standards
<!-- Required coverage, test runner, naming conventions, TDD policy. -->

## Code Quality
<!-- Linting rules, formatting, forbidden patterns, review requirements. -->

## AI Agent Guidelines
<!-- What agents may and may not do autonomously in this repo. -->
```

`runproof memory show --key constitution` funciona igual que con `project` y `decisions`.

---

### 6. Templates nativos por integración

Reemplazar `sdd-*.md` por templates que actúan como agentes autónomos en el formato nativo de cada herramienta.

#### Set de comandos

| Slash command | Qué hace |
|---|---|
| `/runproof-next` | Auto-avanza todo lo posible; redacta artefactos pendientes como borrador |
| `/runproof-new` | Crea un nuevo change con proposal redactado desde contexto del repo |
| `/runproof-status` | Una línea: fase actual + próxima acción |
| `/runproof-verify` | Corre tests + captura evidencia criptográfica |
| `/runproof-constitution` | Crea/actualiza `.runproof/memory/constitution.md` |

#### Renombrado

| Antes | Después |
|---|---|
| `sdd-status.md` | `runproof-status.md` |
| `sdd-verify.md` | `runproof-verify.md` |
| `sdd-propose.md` | absorbido por `runproof-next.md` |
| `sdd-specify.md` | absorbido por `runproof-next.md` |
| `sdd-design.md` | absorbido por `runproof-next.md` |
| `sdd-tasks.md` | absorbido por `runproof-next.md` |
| *(nuevo)* | `runproof-next.md` |
| *(nuevo)* | `runproof-new.md` |
| *(nuevo)* | `runproof-constitution.md` |

#### Paths corregidos por integración

| Integración | Path actual (roto) | Path correcto |
|---|---|---|
| `copilot` | `.github/copilot-prompts/sdd/` | `.github/prompts/` |
| `claude-code` | `.claude/commands/` | `.claude/commands/` ✅ |
| `cursor` | `.cursor/rules/sdd/` | `.cursor/rules/` |
| `gemini-cli` | `.gemini/commands/sdd/` | `.gemini/commands/` |
| `codex` | `.codex/commands/sdd/` | `.codex/commands/` |
| `opencode` | `.opencode/commands/sdd/` | `.opencode/commands/` |

#### Formato Copilot (`.prompt.md` con frontmatter YAML)

Los archivos Copilot van en `templates/commands/copilot/` y se instalan en `.github/prompts/`:

```markdown
---
mode: agent
description: Advance the active RunProof change to the next phase
---

Run `runproof next --json` and act on the result...
```

#### Formato Claude Code (`.md` sin frontmatter)

```markdown
Run `runproof next` and report what changed in one line.
```

---

### 7. Comportamiento detallado de cada comando

#### `/runproof-next`

1. Corre `runproof status --json`
2. Si `can_auto_advance: true` → corre `runproof next` y reporta la fase alcanzada
3. Si `can_auto_advance: false` → lee `missing_artifacts`, escanea el repo para contexto relevante (stack, specs existentes, constitution si existe), redacta el artefacto, lo escribe en `.runproof/changes/<change_id>/`, corre `runproof ready <change_id>`
4. Reporta en una línea

#### `/runproof-new <intent>`

1. Slugifica el intent a kebab-case → `change_id`
2. Corre `runproof new <change_id>`
3. Lee contexto del repo + `constitution.md` si existe
4. Redacta `proposal.md`: intent, scope, success criteria — sin fluff
5. Corre `runproof ready <change_id>`
6. Reporta: `add-dark-mode | propose → specify`

#### `/runproof-status`

Corre `runproof status --json` y reporta en formato ultra-conciso:
```
add-dark-mode | specify | missing: specify.md | next: /runproof-next
```

#### `/runproof-verify`

1. Detecta change activo
2. Corre `runproof verify <id> --discover`
3. Si falla: muestra el error y sugiere el fix
4. Si pasa: una línea con la fase alcanzada + checksum de evidencia

#### `/runproof-constitution [args]`

- **Con texto inline**: redacta constitution basada en esas directivas
- **Con `@path/file`**: lee el archivo y lo usa como base
- **Sin argumentos**: escanea el repo (stack, CI, linters, test runner, commits, `CLAUDE.md`) y redacta constitution inferida
- **Si ya existe**: muestra diff y pide confirmación antes de sobreescribir
- Escribe en `.runproof/memory/constitution.md`

---

### 8. Rebranding en contenido de archivos generados/scaffoldeados

El rebranding no es solo renombrar archivos — el contenido generado por `runproof init` y sus helpers arrastra strings de `sdd` y `proofkit` que deben actualizarse:

| Módulo | String actual | String nueva |
|---|---|---|
| `_wf_infra.py` hooks git | `proofkit guard --root ...` | `runproof guard --root ...` |
| `_wf_infra.py` CI templates | `pip install proofkit-cli` | `pip install runproof-cli` |
| `_wf_infra.py` CI templates | `proofkit guard` | `runproof guard` |
| `templates/runproof/adapters/*.json` | `"schema": "sdd.adapter-capabilities.v1"` | `"schema": "runproof.adapter-capabilities.v1"` |
| `templates/runproof/adapters/github-copilot.json` | `"required_core_commands": ["ssd-core validate", ...]` | `["runproof validate", ...]` |
| `templates/runproof/agents/*.md` | referencias a `proofkit <cmd>` | `runproof <cmd>` |
| `templates/runproof/skills/*.md` | referencias a `proofkit <cmd>` | `runproof <cmd>` |
| `templates/runproof/memory/*.md` | instrucciones con `proofkit init` | `runproof init` |
| `templates/commands/runproof-*.md` | (nuevos — usar `runproof` desde el inicio) | ✅ |

**Regla:** cualquier string literal `"sdd"`, `"proofkit"`, o `"ssd-core"` dentro del contenido de un archivo generado o template debe reemplazarse por `"runproof"`. Incluye comentarios, mensajes de ayuda, y ejemplos de uso embebidos en los templates.

**Implementación:** pasar todos los archivos en `templates/` por un grep exhaustivo de `sdd\|proofkit\|ssd-core` antes de cerrar el PR.

---

## Archivos a modificar / crear

### Renombrar/mover

| Antes | Después |
|---|---|
| `proofkit/` (dir) | `runproof/` |
| `proofkit/templates/sdd/` | `runproof/templates/runproof/` |
| `proofkit/templates/commands/sdd-*.md` | `runproof/templates/commands/runproof-*.md` |
| `bin/proofkit.js` | `bin/runproof.js` |

### Modificar

| Archivo | Cambio |
|---|---|
| `runproof/_types.py` | `SDD_DIR = ".runproof"`, `MEMORY_KEYS` + `"constitution"`, strings `sdd`→`runproof` |
| `runproof/_wf_templates.py` | `_INTEGRATION_COMMAND_DIRS` (paths corregidos), `_COMMAND_FILES` (renombrados), lógica de templates Copilot |
| `runproof/cli.py` | Agregar `next`, agregar `--json` a `status`, renombrar referencias `proofkit`→`runproof` |
| `runproof/_workflow.py` | `next_change()`, auto-detección de `change_id`, `constitution` en memory API |
| `runproof/_render.py` | `print_status_json()`, actualizar strings de output |
| `runproof/_wf_changeops.py` | Lógica de drafting de artefactos para `runproof next` |
| `pyproject.toml` | `name = "runproof-cli"`, `scripts.runproof` |
| `package.json` | `name = "runproof"`, `bin.runproof` |
| `CLAUDE.md`, `README.md` | Rebranding completo |
| `templates/runproof/adapters/*.json` | `schema: "runproof.*"` |
| `templates/runproof/memory/constitution.md` | Nuevo template base |

### Crear

| Archivo | Descripción |
|---|---|
| `runproof/templates/commands/runproof-next.md` | Template Claude Code |
| `runproof/templates/commands/runproof-new.md` | Template Claude Code |
| `runproof/templates/commands/runproof-status.md` | Template Claude Code |
| `runproof/templates/commands/runproof-verify.md` | Template Claude Code |
| `runproof/templates/commands/runproof-constitution.md` | Template Claude Code |
| `runproof/templates/commands/copilot/runproof-next.prompt.md` | Template Copilot |
| `runproof/templates/commands/copilot/runproof-new.prompt.md` | Template Copilot |
| `runproof/templates/commands/copilot/runproof-status.prompt.md` | Template Copilot |
| `runproof/templates/commands/copilot/runproof-verify.prompt.md` | Template Copilot |
| `runproof/templates/commands/copilot/runproof-constitution.prompt.md` | Template Copilot |
| `runproof/templates/runproof/memory/constitution.md` | Template base de constitution |

### Eliminar

Los templates `sdd-*.md` se eliminan (sin período de deprecación — 0 usuarios).

---

## Criterios de éxito

1. `runproof install-commands --integration copilot` → los comandos aparecen en Copilot Chat como `/runproof-*`
2. `runproof install-commands --integration claude-code` → los comandos aparecen en Claude Code como `/runproof-*`
3. `runproof status --json` devuelve JSON válido con `change_id`, `phase`, `next_action`, `can_auto_advance`, `missing_artifacts`
4. `runproof next` sin argumentos funciona cuando hay un único change activo
5. Un agente puede ir de `not-started` a `verify` con `/runproof-next` repetido sin escribir nada
6. `/runproof-constitution` sin argumentos genera un `constitution.md` válido escaneando el repo
7. `runproof memory show --key constitution` funciona
8. El directorio de estado es `.runproof/` en todos los paths internos
9. Tests existentes pasan con el nuevo nombre (actualizar `test_version.py` y todas las referencias a `proofkit`/`sdd` en tests)
10. `grep -r "sdd\|proofkit\|ssd-core" runproof/templates/` devuelve cero resultados — ningún archivo generado/scaffoldeado arrastra el nombre viejo
