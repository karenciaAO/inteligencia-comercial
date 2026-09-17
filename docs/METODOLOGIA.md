### Qué responde esta solución

Identifica dónde se concentra la venta, qué operaciones erosionan el margen y qué clientes ameritan una revisión comercial. Los hallazgos se recalculan con el Excel y los filtros; no son frases fijas ni predicciones.

### Base y alcance (resumen)

Se conserva la lógica del notebook original: normalizar texto e IDs, convertir tipos sin ocultar errores, eliminar duplicados exactos, validar claves y unir muchos-a-uno. Se excluyen clientes no registrados e inconsistencias financieras. No se corrigen importes por intuición.

Fórmulas validadas: venta neta = unidades × precio unitario × (1 − descuento), costo = unidades × costo base, margen = venta neta − costo, margen % = margen / venta neta. Tolerancia 0,01 para importes y 0,0001 para proporciones. Unidades negativas consistentes pueden representar devoluciones; no se eliminan por su signo.

### Diccionario de indicadores clave

| Indicador | Cálculo e interpretación |
|---|---|
| Venta neta | Suma del importe validado, incluyendo devoluciones consistentes |
| Margen | Suma de venta neta menos costo; no es utilidad neta, no incluye gastos operativos |
| Margen porcentual | Suma de margen / suma de venta neta; nunca promedio de porcentajes |
| Valor por transacción | Venta neta / Transacciones |

### Reglas de segmentación de clientes (RFM + intención)

- **Inactividad**: días sin compra (default 90) → acción *Reactiva*.
- **Intención**: interacciones de carrito/cotización/consulta sin conversión en ventana (default 30 días) → acción *Seguimiento* o *Contactar* según valor.
- **Valor**: percentil 75 del valor monetario histórico → clientes *Valiosos*.
- **Categoría preferida**: mayor venta neta histórica por cliente; desempate alfabético.

### Auditoría y exclusiones

El archivo `audit` en el objeto `Dataset` registra filas por etapa (original, duplicados, clientes sin correspondencia, inconsistencias financieras). El total de filas finales coincide con la suma de exclusiones. El detalle técnico no se muestra en el dashboard ejecutivo; está disponible vía CLI para auditoría.