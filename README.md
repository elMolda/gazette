# Gazette

Herramienta de automatización y CLI en Python para consultar feeds RSS y URLs directas, generar un EPUB optimizado y enviarlo automáticamente a Kindle por correo.

Permite generar dos tipos de publicaciones:
- **Periódico diario (`--periodico` / `-t periodico`):** Actualidad y noticias del día (1 a 12 min de lectura, 5 artículos por defecto).
- **Revista de ensayos (`--revista` / `-t revista`):** Ensayos largos, análisis y lecturas de fondo (4 a 25 min de lectura, 3 artículos por defecto).

---

## Requisitos

- Python >= 3.12
- [Poetry](https://python-poetry.org/)

## Instalación

```bash
poetry install
```

Copia `.env.example` a `.env` y configura tus credenciales SMTP y tu correo de Kindle:

```bash
cp .env.example .env
```

---

## Uso

### 1. Periódico diario (noticias de actualidad)

Consulta fuentes de actualidad (BBC Mundo, DW, NASA, Lobsters, ElDiario.es, etc.):

```bash
# Periódico en español (5 artículos breves)
poetry run python generar_edicion.py --periodico

# Periódico en inglés con las noticias más recientes
poetry run python generar_edicion.py en --periodico --orden reciente

# Filtrar por tema específico (internacional, tecnologia, ciencia, politica_economia)
poetry run python generar_edicion.py --periodico --tema internacional -n 4
```

### 2. Revista (ensayos y lecturas de fondo)

Comportamiento por defecto. Consulta fuentes de ensayo (Jot Down, Gatopardo, Aeon, Razón Pública, Ethic, etc.):

```bash
# Revista dominical en español (3 artículos)
poetry run python generar_edicion.py --revista
# o simplemente:
poetry run python generar_edicion.py

# Filtrar por fuente específica
poetry run python generar_edicion.py -f "Jot Down" -n 2

# Filtrar por tema dentro de la revista
poetry run python generar_edicion.py --revista --tema ciencia
```

### 3. Desde un archivo de URLs

Genera la edición a partir de enlaces directos guardados en un archivo de texto (uno por línea), omitiendo restricciones de tiempo de lectura:

```bash
poetry run python generar_edicion.py -u articulos.txt
```

### 4. Envío automático a Kindle

Agrega `--send` a cualquier comando para despachar el archivo generado vía SMTP a tu dirección Kindle:

```bash
poetry run python generar_edicion.py --periodico --send
poetry run python generar_edicion.py -u articulos.txt --send
```

Reenviar un archivo existente sin regenerar:

```bash
poetry run python generar_edicion.py --send-only output/periodico_es_2026-11-25.epub
```
