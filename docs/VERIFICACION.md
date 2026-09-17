# Verificación del MVP

## Conciliación con el notebook original

Se ejecutaron las celdas de preparación del notebook adjunto en un entorno de prueba, sustituyendo únicamente la lectura de Google Drive por la copia local. La aplicación no ejecuta ni incluye ese notebook.

| Control | Notebook | Aplicación |
|---|---:|---:|
| Filas analíticas | 59.994 | 59.994 |
| Venta neta | 263.631.918.896,28418 | 263.631.918.896,28418 |
| Costo | 216.309.733.179 | 216.309.733.179 |
| Margen | 47.322.185.717,284164 | 47.322.185.717,284164 |

Se comprobó además igualdad del conjunto de Transaccion_ID. Las cantidades de arriba son controles de prueba sobre la base adjunta, no cifras fijas usadas por el dashboard.

Conciliación de filas: 60.005 originales − 5 duplicados exactos − 3 clientes sin correspondencia − 3 inconsistencias financieras = 59.994 filas. Periodo: 1 de enero de 2024 a 31 de diciembre de 2025.

## Cobertura automatizada

Resultado de la ejecución final: **19 pruebas aprobadas**, sin fallos.

Las pruebas cubren población final, conciliación de importes y filas, margen ponderado, consolidación mensual, grupos excluyentes de campañas, archivos inválidos, hojas/columnas faltantes, claves conflictivas, conversiones erróneas, fechas vacías, rangos de campañas inválidos, idempotencia, ausencia de datos futuros en RFM, límite de 90 días, seguimiento de intención, catálogo de preguntas y protección de CSV. También prueban cambio de resultados con una nueva transacción y respuestas vacías.

La navegación de Streamlit se comprueba con AppTest: arranque sin datos, carga de la base de ejemplo, cinco vistas y filtro de canal. El servicio HTTP local respondió `200 ok` en su control de salud. La interacción del selector de archivos nativo del navegador no se automatiza con AppTest; la misma función de carga se prueba directamente con bytes del Excel.

Entorno probado: Python 3.12.14, Streamlit 1.49.1, pandas 2.2.3, NumPy 2.3.5, openpyxl 3.1.5 y Plotly 6.3.0.

Para repetir: `python -m pytest -q`. La copia de Excel en `data/` es necesaria para estas pruebas de integración. No se han realizado pruebas de concurrencia empresarial, accesibilidad en navegador ni instalaciones en todos los sistemas operativos.
