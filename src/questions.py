"""Intérprete determinista de un catálogo cerrado; nunca evalúa código del usuario."""
import re
import unicodedata
from dataclasses import dataclass
import pandas as pd
from .analytics import summary, ranking, monthly, discounts, findings

EXAMPLES = ['Resumen del negocio', 'Top 10 productos por margen', 'Ventas por canal',
            'Margen por categoría', 'Venta mensual', 'Margen mensual',
            'Clientes para contactar', 'Clientes para reactivar',
            'Clientes para seguimiento', 'Descuentos y margen', 'Resultados de campañas',
            'Alertas del negocio']


@dataclass
class Answer:
    title: str
    table: pd.DataFrame
    note: str
    line_metric: str | None = None


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',text.lower()) if not unicodedata.combining(c))


def answer(question, sales, actions):
    q = normalize(question.strip())
    empty = pd.DataFrame()
    if re.search(r'\b20\d{2}\b|\b(ayer|hoy|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b',q):
        return Answer('Configura el periodo',empty,'Selecciona fechas en la barra lateral y reformula sin fechas. No interpreto fechas escritas.')
    if any(w in q for w in ['predec','pronostic','caus','por que','enviar','correo','trm','dolar']):
        return Answer('Pregunta fuera del catálogo',empty,'No genero pronósticos, explicaciones causales ni envío comunicaciones. Usa uno de los ejemplos.')
    if sales.empty:
        return Answer('Sin datos',empty,'No hay ventas dentro de los filtros.')
    if any(w in q for w in ['contact','reactiv','seguimiento']):
        a = actions.copy()
        if not a.empty:
            if 'reactiv' in q: a = a.loc[a.Accion.str.contains('Reactivar')]
            elif 'seguimiento' in q: a = a.loc[a.Accion.eq('Dar seguimiento')]
            else: a = a.loc[a.Prioridad.le(4)]
        return Answer('Acciones por cliente',a,'Historia completa hasta la fecha final seleccionada; no depende de los filtros de categoría o canal.')
    if 'campan' in q:
        return Answer('Contexto de campañas',summary(sales,['Contexto_Campania']), 'Coincidencia de fecha y canal; no mide impacto.')
    if 'descuento' in q:
        return Answer('Descuento y rentabilidad',discounts(sales),'Asociación descriptiva; el mix de productos puede explicar diferencias.')
    if any(w in q for w in ['alerta','riesgo','hallazgo']):
        return Answer('Prioridades del negocio',findings(sales),'Reglas descriptivas sobre el periodo filtrado.')
    metric = 'Margen' if 'margen' in q or 'rentab' in q else 'Venta_Neta'
    if 'mensual' in q or 'tendencia' in q:
        return Answer('Evolución mensual',monthly(sales),'Evolución mensual',metric)
    dims = [('producto','Producto_ID'),('canal','Canal'),('categoria','Categoria'),
            ('cliente','Cliente_ID'),('tienda','PDV'),('marca','Marca'),('zona','Zona')]
    for word, dim in dims:
        if word in q:
            match = re.search(r'\btop\s+(\d+)\b',q)
            n = min(max(int(match.group(1)),1),100) if match else 10
            return Answer(f'Top {n} por {dim}',ranking(sales,dim,metric,n),f'Orden descendente por {metric}; filtros de la barra lateral.')
    if 'resumen' in q or 'kpi' in q:
        return Answer('Resumen del negocio',summary(sales),'Margen porcentual ponderado y valor por transacción.')
    return Answer('Pregunta no reconocida',empty,'Usa un ejemplo del catálogo. No se inventará una respuesta.')
