from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from src.pipeline import read_excel, prepare, load, DataError
from src.analytics import summary, monthly
from src.rules import customer_actions, Rules
from src.questions import answer, EXAMPLES
from src.presentation import safe_csv

BASE = Path(__file__).resolve().parents[1]/'data'/'Base_Datos.xlsx'


@pytest.fixture(scope='module')
def tables():
    return read_excel(BASE.read_bytes())


@pytest.fixture(scope='module')
def data(tables):
    return prepare(tables)


def test_notebook_population(data):
    assert len(data.sales)==59994
    assert data.sales.Transaccion_ID.is_unique
    assert data.sales.Cliente_Registrado.all()


def test_reconciliation(data):
    a = data.audit.set_index('Etapa')
    assert a.Filas.iloc[0] == a.Filas.iloc[1:].sum()
    assert np.isclose(a.Venta_Neta.iloc[0],a.Venta_Neta.iloc[1:].sum(),atol=.01)


def test_summary(data):
    s = data.sales
    k = summary(s).iloc[0]
    assert np.isclose(k.Margen_Pct,s.Margen.sum()/s.Venta_Neta.sum())
    assert np.isclose(k.Valor_por_transaccion,s.Venta_Neta.sum()/s.Transaccion_ID.nunique())
    assert np.isclose(monthly(s).Venta_Neta.sum(),k.Venta_Neta)
    assert np.isclose(summary(s,['Contexto_Campania']).Venta_Neta.sum(),k.Venta_Neta)


@pytest.mark.parametrize('fault',['missing_sheet','duplicate_key','bad_number','bad_date','bad_campaign','conflicting_id','missing_column'])
def test_invalid_inputs(tables,fault):
    t = {k:v.copy(deep=True) for k,v in tables.items()}
    if fault=='missing_sheet': del t['Productos']
    elif fault=='duplicate_key': t['Clientes'].loc[1,'Cliente_ID']=t['Clientes'].loc[0,'Cliente_ID']
    elif fault=='bad_number':
        t['Transacciones']['Venta_Neta']=t['Transacciones'].Venta_Neta.astype(object)
        t['Transacciones'].loc[0,'Venta_Neta']='no-numero'
    elif fault=='bad_date': t['Transacciones'].loc[0,'Fecha']=pd.NaT
    elif fault=='bad_campaign': t['Campanias'].loc[0,'Fecha_Fin']=pd.Timestamp('2000-01-01')
    elif fault=='conflicting_id': t['Transacciones'].loc[1,'Transaccion_ID']=t['Transacciones'].loc[0,'Transaccion_ID']
    elif fault=='missing_column': t['Transacciones']=t['Transacciones'].drop(columns=['Unidades'])
    with pytest.raises(DataError): prepare(t)


def test_bad_xlsx():
    with pytest.raises(DataError): load(b'not an Excel file')


def test_idempotent(tables):
    a, b = prepare(tables), prepare(tables)
    pd.testing.assert_frame_equal(a.sales,b.sales)
    assert len(tables['Transacciones'])==60005


def test_no_future_leakage(data):
    cut = pd.Timestamp('2024-12-31')
    a = customer_actions(data.sales,data.interactions,cut)
    assert a.Ultima_Compra.max()<=cut
    assert a.Ultima_Intencion.dropna().max()<=cut
    b = customer_actions(data.sales.loc[data.sales.Fecha.le(cut)],data.interactions.loc[data.interactions.Fecha.le(cut)],cut)
    pd.testing.assert_frame_equal(a,b)


def test_recency_boundary_and_followup():
    s = pd.DataFrame({'Cliente_ID':['C1','C2'], 'Fecha':pd.to_datetime(['2025-01-01','2025-03-01']),
                      'Unidades':[1,1],'Venta_Neta':[100,50],'Transaccion_ID':['T1','T2'],
                      'Margen':[10,5],'Categoria':['A','B']})
    i = pd.DataFrame({'Cliente_ID':['C2','C1'],'Fecha':pd.to_datetime(['2025-03-30','2026-01-01']),
                      'Tipo':['Carrito','Carrito'],'Resultado':['Seguimiento','Seguimiento'],
                      'Canal':['Web','Web'],'Interaccion_ID':['I1','I2']})
    a = customer_actions(s,i,'2025-03-31',Rules(inactive_days=90)).set_index('Cliente_ID')
    assert a.loc['C1','Recencia']==90
    assert a.loc['C1','Accion']=='Reactivar cliente valioso'
    assert a.loc['C2','Accion']=='Dar seguimiento'


def test_questions(data):
    a = customer_actions(data.sales,data.interactions,'2025-12-31')
    for q in EXAMPLES:
        assert answer(q,data.sales,a).title not in ['Pregunta no reconocida','Pregunta fuera del catálogo']
    assert answer('pronostica las ventas',data.sales,a).table.empty
    assert answer('ventas enero 2025',data.sales,a).table.empty
    assert answer('xyz',data.sales,a).table.empty
    top = answer('Top 5 productos por margen',data.sales,a).table
    assert len(top)==5 and top.Margen.is_monotonic_decreasing


def test_csv_formula_guard():
    text = safe_csv(pd.DataFrame({'x':['=1+1','@SUM(A1)','normal']})).decode('utf-8-sig')
    assert "'=1+1" in text and "'@SUM" in text


def test_changed_source_recalculates(tables,data):
    t = {k:v.copy(deep=True) for k,v in tables.items()}
    row = t['Transacciones'].iloc[0].copy()
    row['Transaccion_ID']='T_NEW_1'
    t['Transacciones']=pd.concat([t['Transacciones'],row.to_frame().T],ignore_index=True)
    updated = prepare(t)
    assert len(updated.sales)==len(data.sales)+1
    assert np.isclose(updated.sales.Venta_Neta.sum()-data.sales.Venta_Neta.sum(),row.Venta_Neta,atol=.01)


def test_empty_results(data):
    empty = data.sales.iloc[:0]
    assert summary(empty).empty
    assert customer_actions(empty,data.interactions,'2023-01-01').empty
    assert answer('resumen',empty,pd.DataFrame()).table.empty
