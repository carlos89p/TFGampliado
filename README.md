# Generador inteligente de rutinas de entrenamiento

Aplicación desarrollada en Python para generar rutinas de gimnasio personalizadas a partir del perfil del usuario. El sistema combina reglas deterministas para construir la rutina con una capa de inteligencia artificial local, ejecutada mediante Ollama, que revisa el resultado y puede corregir ejercicios problemáticos.

## Funcionamiento

1. Recoge o reutiliza los datos del usuario: edad, sexo, composición corporal, objetivo, experiencia, días disponibles y posibles molestias.
2. Normaliza el perfil y selecciona una distribución semanal adecuada.
3. Determina el volumen, los grupos musculares y los ejercicios de cada sesión.
4. Filtra y puntúa los ejercicios del catálogo según el nivel y las restricciones detectadas.
5. Adapta la rutina cuando existen molestias lumbares o lesiones indicadas en las observaciones.
6. Valida la rutina con un modelo local de Ollama y, cuando es necesario, elige sustitutos únicamente entre ejercicios reales del catálogo.
7. Guarda por separado la rutina generada por reglas y la versión final validada.

## Requisitos

- Python 3.12 recomendado.
- [Ollama](https://ollama.com/) instalado y en ejecución.
- Modelo `qwen2.5:7b` descargado, o cualquier otro modelo compatible configurado por el usuario.
- Biblioteca Python `pandas`.

## Instalación

Desde la carpeta del proyecto:

```bash
python -m venv venv
```

En Windows:

```powershell
.\venv\Scripts\activate
```

En Linux o macOS:

```bash
source venv/bin/activate
```

Instala la dependencia necesaria:

```bash
pip install pandas
```

Descarga el modelo predeterminado de Ollama:

```bash
ollama pull qwen2.5:7b
```

## Ejecución

```bash
python main.py
```

Al iniciar, el programa permite reutilizar `manual_input_ai_ready.json` o completar un nuevo cuestionario por consola.

Los resultados se guardan en:

- `generated_routines/rutina_generada.json`: rutina creada únicamente mediante reglas.
- `generated_routines/rutina_generada_validada.json`: rutina revisada y, si procede, corregida mediante IA.

El catálogo ya está preprocesado. Para volver a generarlo desde el CSV original:

```bash
python preprocess_catalog.py
```

## Pruebas

Prueba básica con perfiles predefinidos:

```bash
python test_routines.py
```

Comparación entre varios modelos de Ollama:

```bash
python test_routines_multi_model.py
```

También es posible indicar modelos concretos:

```bash
python test_routines_multi_model.py --models qwen2.5:7b llama3.1:8b mistral:7b
```

Para comprobar únicamente la generación basada en reglas:

```bash
python test_routines_multi_model.py --disable-ai
```

## Estructura principal

```text
TFGampliado/
├── main.py                       # Punto de entrada del programa
├── procesamiento_manual.py       # Cuestionario y creación del perfil
├── preprocess_catalog.py         # Preprocesamiento del dataset
├── ai/                           # Cliente de Ollama, validación y corrección
├── rules/                        # Reglas de generación y selección
├── context/                      # Dataset original
├── processed_context/            # Catálogo normalizado
├── generated_routines/           # Rutinas generadas
├── test_routines.py              # Pruebas básicas
├── test_routines_multi_model.py  # Pruebas con varios modelos
└── test_outputs/                 # Resultados de las pruebas
```

## Catálogo de ejercicios

El proyecto utiliza el dataset [Gym Exercise Data](https://www.kaggle.com/datasets/niharika41298/gym-exercise-data). El preprocesamiento elimina duplicados y normaliza el nivel, el equipamiento, el grupo muscular y el tipo de ejercicio. El catálogo incluido contiene 2.909 ejercicios únicos.

## Aviso

Las rutinas generadas son orientativas y no sustituyen la valoración de un entrenador, médico o fisioterapeuta, especialmente cuando existen lesiones, dolor intenso o síntomas neurológicos.
