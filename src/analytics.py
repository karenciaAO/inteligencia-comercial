"""Métricas únicas, reutilizadas por todas las vistas y por el consultor."""
import numpy as np
import pandas as pd


def summary(t: pd.DataFrame, groups: list[str] | None = None) -> pd.DataFrame:
    if t.empty:
        return pd.DataFrame()
    d = t.assign(Total='Total') if not groups else t
    groups = groups or ['Total']
    r = d.groupby(groups, dropna=False, observed=True).agg(
        Venta_Neta=('Venta_Neta','sum'), Costo=('Costo','sum'), Margen=('Margen','sum'),
        Transacciones=('Transaccion_ID','nunique'), Clientes=('Cliente_ID','nunique'),
        Productos=('Producto_ID','nunique'), Puntos_de_Venta=('PDV_ID','nunique'),
        Descuento_Max=('Descuento','max'), Unidades_Netas=('Unidades','sum')).reset_index()
    r['Margen_Pct'] = r.Margen / r.Venta_Neta.replace(0,np.nan)
    r['Valor_por_transaccion'] = r.Venta_Neta / r.Transacciones.replace(0,np.nan)
    return r


def ranking(t, dimension, metric='Venta_Neta', n=10, ascending=False):
    r = summary(t, [dimension])
    result = r.sort_values([metric, dimension], ascending=[ascending, True]).head(n) if not r.empty else r
    # If ranking by Producto_ID, include Categoria for context
    if dimension == 'Producto_ID' and not result.empty and 'Categoria' in t.columns:
        cat_map = t.drop_duplicates('Producto_ID').set_index('Producto_ID')['Categoria']
        result = result.copy()
        result['Categoria'] = result['Producto_ID'].map(cat_map)
        cols = ['Producto_ID', 'Categoria'] + [c for c in result.columns if c not in ['Producto_ID', 'Categoria']]
        result = result[cols]
    return result


def monthly(t):
    return summary(t,['Año','Mes'])


def discounts(t):
    d = t.copy()
    d['Tramo_Descuento'] = pd.cut(d.Descuento, [-0.001,0,0.1,0.2,0.3,1],
                                 labels=['Sin descuento','Hasta 10%','10–20%','20–30%','Más de 30%'])
    return summary(d,['Tramo_Descuento'])


def findings(t):
    """Observaciones reproducibles; no inferencia causal ni impacto inventado."""
    rows = []
    if t.empty:
        return pd.DataFrame()
    r = ranking(t,'Canal', n=100)
    top = r.iloc[0]
    total = t.Venta_Neta.sum()
    share = top.Venta_Neta/total if total > 0 else np.nan
    rows.append({'Prioridad':2,'Hallazgo':'Concentración por canal',
                 'Evidencia':f'{top.Canal}: {share:.1%} de la venta neta seleccionada' if np.isfinite(share) else 'Participación no evaluable con venta total ≤ 0',
                 'Decisión':'Revisar dependencia y rentabilidad antes de redistribuir inversión.'})
    
    # Análisis de margen negativo por categoría
    cat = summary(t,['Categoria'])
    loss = cat.loc[cat.Margen.lt(0)]
    if not loss.empty:
        cat_list = ', '.join(loss.Categoria.astype(str))
        rows.append({'Prioridad':1,'Hallazgo':'Categorías con margen negativo',
                     'Evidencia':f'{cat_list} (margen total: {loss.Margen.sum():,.0f})',
                     'Decisión':'Revisar precio, costo y descuentos por referencia.'})
    
    # Análisis detallado de operaciones con margen negativo
    neg = t.loc[t.Margen.lt(0)]
    if not neg.empty:
        # Top productos con margen negativo
        neg_prod = neg.groupby('Producto_ID').agg(
            Margen=('Margen','sum'),
            Venta_Neta=('Venta_Neta','sum'),
            Transacciones=('Transaccion_ID','nunique'),
            Descuento_Pct=('Descuento','mean')
        ).sort_values('Margen').head(5)
        if 'Categoria' in neg.columns:
            cat_map = neg.drop_duplicates('Producto_ID').set_index('Producto_ID')['Categoria']
            neg_prod = neg_prod.copy()
            neg_prod['Categoria'] = neg_prod.index.map(cat_map)
        
        prod_detail = '; '.join([f"{idx} ({row.get('Categoria','N/A')}): margen {row['Margen']:,.0f}, desc. {row['Descuento_Pct']:.1%}" 
                                  for idx, row in neg_prod.iterrows()])
        
        rows.append({'Prioridad':1,'Hallazgo':'Operaciones con margen negativo',
                     'Evidencia':f'{len(neg):,} operaciones; margen agregado {neg.Margen.sum():,.0f}. Top productos: {prod_detail}',
                     'Decisión':'Auditar descuentos y costos en productos listados; no confundir este margen con utilidad neta.'})
    else:
        rows.append({'Prioridad':1,'Hallazgo':'Operaciones con margen negativo',
                     'Evidencia':'No se detectaron operaciones con margen negativo en el periodo filtrado.',
                     'Decisión':'Monitorear periódicamente.'})
    
    overlap = t.Numero_Campanias.gt(1)
    rows.append({'Prioridad':3,'Hallazgo':'Atribución de campañas',
                 'Evidencia':f'{overlap.sum():,} operaciones coinciden con varias campañas',
                 'Decisión':'No sumar ventas por campaña solapada ni presentar causalidad.'})
    
    # Categoría que más vende y la que más margina
    cat_sales = cat.sort_values('Venta_Neta', ascending=False)
    cat_margin = cat.sort_values('Margen', ascending=False)
    if not cat_sales.empty and not cat_margin.empty:
        top_sell = cat_sales.iloc[0]
        top_margin = cat_margin.iloc[0]
        rows.append({'Prioridad':2,'Hallazgo':'Categoría líder en venta y margen',
                     'Evidencia':f'Más vende: {top_sell.Categoria} ({top_sell.Venta_Neta:,.0f}); Más margina: {top_margin.Categoria} ({top_margin.Margen:,.0f}, {top_margin.Margen_Pct:.1%})',
                     'Decisión':'Validar si la categoría que más margina tiene descuentos competitivos en Alkosto (ver notebook scraping).'})
    
    return pd.DataFrame(rows).sort_values('Prioridad')
