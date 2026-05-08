# Demo: RunProof en 60 segundos

Esta carpeta muestra el potencial de RunProof con una historia mínima y reproducible:

1. Un agente dice: **"listo, los tests pasan"**.
2. El código todavía está roto.
3. RunProof ejecuta el comando real y bloquea el avance.
4. Se aplica una corrección de una línea.
5. RunProof acepta la verificación solo después de capturar evidencia de ejecución exitosa.

## Qué hay en esta demo

```text
demo/
├── broken-app/
│   ├── app.js          # bug intencional: suma usando resta
│   ├── package.json    # sin dependencias externas
│   └── test.js         # una aserción que debe fallar al inicio
└── scripts/
    ├── run-demo.sh     # demo automatizada para macOS/Linux
    └── run-demo.ps1    # demo automatizada para Windows PowerShell
```

El bug intencional está en `broken-app/app.js`:

```js
function sum(a, b) {
  return a - b;
}
```

## Ejecutar la demo completa

Desde la raíz del repo:

```bash
./demo/scripts/run-demo.sh
```

En Windows PowerShell:

```powershell
.\demo\scripts\run-demo.ps1
```

Los scripts crean `demo/.demo-workdir/` y corren el flujo normal de usuario: `runproof init`, `runproof run`, edición de artefactos, `runproof ready`, `runproof transition`, verificación fallida, fix de una línea y verificación exitosa. La carpeta temporal está ignorada por git.

## Recorrido manual

### 1. Demuestra que el código está roto

```bash
npm test --prefix demo/broken-app
```

Salida esperada: Node lanza un `AssertionError` porque `sum(2, 2)` devuelve `0` en vez de `4`.

### 2. Lee la promesa falsa del agente

> "Listo, los tests pasan."

RunProof no acepta esa frase como evidencia. Necesita ejecutar el comando.

### 3. Observa cómo RunProof bloquea el cierre falso

El script automatizado sigue primero los pasos normales del workflow:

```bash
python -m runproof init --no-prompt --root demo/.demo-workdir
python -m runproof run demo-sum-bug --profile quick --title "Fix broken sum demo" --root demo/.demo-workdir
# editar proposal.md
python -m runproof ready demo-sum-bug --root demo/.demo-workdir
python -m runproof transition demo-sum-bug task --root demo/.demo-workdir
# editar tasks.md
python -m runproof ready demo-sum-bug --root demo/.demo-workdir
```

Después ejecuta la verificación real dentro del workspace desechable:

```bash
python -m runproof verify demo-sum-bug --command "npm test --prefix broken-app" --root demo/.demo-workdir
```

Con el bug presente, RunProof devuelve un error similar a:

```text
✗ ERROR: .runproof/evidence/demo-sum-bug: verification command failed (exit 1): npm test --prefix broken-app
```

### 4. Aplica la corrección real

Cambia la implementación a:

```js
function sum(a, b) {
  return a + b;
}
```

### 5. Vuelve a verificar

Cuando el comando realmente pasa, RunProof registra la evidencia:

```text
✔ Verification recorded: demo-sum-bug
```

## Por qué esto muestra el potencial

RunProof convierte una afirmación informal —"ya está"— en una regla verificable del repositorio:

- si el comando no se ejecutó, no hay evidencia;
- si el comando falló, el cambio queda bloqueado;
- si el comando pasó, queda un registro con salida y checksum bajo `.runproof/evidence/`.

**Promesa corta:** RunProof evita cierres falsos de agentes y solo acepta progreso respaldado por ejecución real.
