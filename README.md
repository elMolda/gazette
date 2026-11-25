# Gazette

Herramienta de automatización y CLI en Python para consultar feeds RSS y URLs de ensayos o artículos largos, generar un EPUB optimizado y enviarlo automáticamente a Kindle por correo.

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

## Uso

### 1. Desde feeds RSS

```bash
# Edición en español (por defecto)
poetry run python generar_edicion.py

# Filtrar por fuente (coincidencia parcial o exacta)
poetry run python generar_edicion.py -f "Razón Pública" -n 2

# Orden cronológico más reciente en lugar de aleatorio
poetry run python generar_edicion.py -f aeon --orden reciente

# Seleccionar idioma ('es', 'en' o 'mix')
poetry run python generar_edicion.py mix -n 3
```

### 2. Desde un archivo de URLs

Permite generar el EPUB directamente a partir de URLs listadas en un archivo de texto (una por línea), omitiendo restricciones de tiempo de lectura:

```bash
poetry run python generar_edicion.py -u articulos.txt
```

### 3. Envío a Kindle

Agrega `--send` a cualquier comando para despachar el archivo generado vía SMTP a tu dirección Kindle:

```bash
poetry run python generar_edicion.py -u articulos.txt --send
```

También puedes reenviar un archivo existente sin volver a consultar la web:

```bash
poetry run python generar_edicion.py --send-only output/edicion_es_2026-11-25.epub
```
