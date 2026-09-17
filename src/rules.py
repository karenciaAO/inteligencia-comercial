"""Reglas duras configurables. Ningún modelo se entrena ni envía mensajes."""
from dataclasses import dataclass
import pandas as pd


@dataclass(frozen=True)
class Rules:
    inactive_days: int = 90
    intent_days: int = 30
    valuable_percentile: float = 0.75


def customer_actions(sales, interactions, cutoff, rules=Rules()):
    """Historia hasta el corte. No usa interacciones ni compras futuras."""
    cutoff = pd.Timestamp(cutoff).normalize()
    reference = cutoff + pd.Timedelta(days=1)
    s = sales.loc[sales.Fecha.lt(reference)].copy()
    buy = s.loc[s.Unidades.gt(0) & s.Venta_Neta.gt(0)]
    if buy.empty:
        return pd.DataFrame()
    r = buy.groupby('Cliente_ID').agg(Ultima_Compra=('Fecha','max'),
            Frecuencia=('Transaccion_ID','nunique'), Valor_Monetario=('Venta_Neta','sum'))
    r['Recencia'] = (reference-r.Ultima_Compra.dt.normalize()).dt.days
    r['Margen_Historico'] = s.groupby('Cliente_ID').Margen.sum().reindex(r.index)
    # Categoría preferida: mayor venta positiva histórica, desempate alfabético.
    pref = buy.groupby(['Cliente_ID','Categoria']).Venta_Neta.sum().reset_index()
    pref = pref.sort_values(['Cliente_ID','Venta_Neta','Categoria'], ascending=[True,False,True]).drop_duplicates('Cliente_ID')
    r['Categoria_Preferida'] = pref.set_index('Cliente_ID').Categoria
    inter = interactions.loc[interactions.Fecha.lt(reference)].copy()
    intents = inter.loc[inter.Tipo.isin(['Carrito','Cotizacion','Consulta']) &
                        inter.Resultado.isin(['Sin_Conversion','Seguimiento']) &
                        inter.Fecha.ge(reference-pd.Timedelta(days=rules.intent_days))]
    latest = intents.sort_values(['Fecha','Interaccion_ID']).drop_duplicates('Cliente_ID',keep='last').set_index('Cliente_ID')
    r['Ultima_Intencion'] = latest.Fecha.reindex(r.index)
    r['Canal_Contacto_Sugerido'] = latest.Canal.reindex(r.index).fillna('Validar canal autorizado')
    r['Tipo_Intencion'] = latest.Tipo.reindex(r.index)
    threshold = r.Valor_Monetario.quantile(rules.valuable_percentile)
    def decide(row):
        if row.Margen_Historico < 0:
            return 1,'Revisar rentabilidad','Margen histórico negativo','Revisar precio y costos; no ofrecer descuento automático.'
        if pd.notna(row.Ultima_Intencion) and row.Ultima_Intencion > row.Ultima_Compra:
            return 2,'Dar seguimiento',f'{row.Tipo_Intencion} reciente sin compra posterior registrada','Confirmar interés y disponibilidad; validar si requiere soporte.'
        if row.Recencia >= rules.inactive_days and row.Valor_Monetario >= threshold:
            return 3,'Reactivar cliente valioso',f'Recencia ≥ {rules.inactive_days} días y valor ≥ percentil {rules.valuable_percentile:.0%}',f'Consultar interés en {row.Categoria_Preferida}; validar consentimiento.'
        if row.Recencia >= rules.inactive_days:
            return 4,'Reactivar',f'Recencia ≥ {rules.inactive_days} días','Consultar motivo de inactividad antes de ofrecer promoción.'
        return 5,'Mantener relación','Compra dentro del umbral de actividad','Seguimiento posventa sin presión comercial.'
    decisions = r.apply(lambda row: pd.Series(decide(row),index=['Prioridad','Accion','Motivo','Sugerencia']),axis=1)
    return r.join(decisions).reset_index().sort_values(['Prioridad','Valor_Monetario','Cliente_ID'],ascending=[True,False,True])
