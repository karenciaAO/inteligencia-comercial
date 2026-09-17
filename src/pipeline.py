"""Porta las celdas 4–23 del notebook a funciones comprobables, sin Colab."""
from dataclasses import dataclass
from io import BytesIO
from zipfile import ZipFile
import numpy as np
import pandas as pd


class DataError(ValueError):
    """Error de origen que puede corregir quien entrega el Excel."""


IDS = {'Transacciones': ['Transaccion_ID', 'Cliente_ID', 'Producto_ID', 'PDV_ID'],
       'Clientes': ['Cliente_ID'], 'Productos': ['Producto_ID'], 'Tiendas': ['PDV_ID'],
       'Campanias': ['Campania_ID'], 'Interacciones': ['Interaccion_ID', 'Cliente_ID']}
DATES = {'Transacciones': ['Fecha'], 'Clientes': ['Fecha_Alta'],
         'Campanias': ['Fecha_Inicio', 'Fecha_Fin'], 'Interacciones': ['Fecha']}
NUMBERS = {'Transacciones': ['Unidades', 'Descuento', 'Precio_Lista', 'Costo_Base',
                            'Precio_Unitario', 'Venta_Neta', 'Costo', 'Margen', 'Margen_%'],
           'Clientes': ['Edad'], 'Productos': ['Precio_Lista', 'Costo_Base'],
           'Campanias': ['Descuento_Objetivo'], 'Interacciones': ['Duracion_Min']}
ATTRS = {'Transacciones': ['Canal', 'Categoria', 'Subcategoria', 'Marca', 'Zona', 'Ciudad'],
         'Clientes': ['Tipo_Cliente_Actual'], 'Productos': ['Rotacion'],
         'Tiendas': ['PDV', 'Formato'], 'Campanias': ['Canal', 'Tipo_Campania'],
         'Interacciones': ['Canal', 'Tipo', 'Resultado']}


@dataclass
class Dataset:
    sales: pd.DataFrame
    interactions: pd.DataFrame
    campaigns: pd.DataFrame
    audit: pd.DataFrame
    rejected: pd.DataFrame


def read_excel(payload: bytes) -> dict[str, pd.DataFrame]:
    """Solo xlsx, límites de tamaño y encabezados verificados antes de pandas."""
    if len(payload) > 50 * 1024**2:
        raise DataError('El archivo supera 50 MB.')
    try:
        with ZipFile(BytesIO(payload)) as z:
            if sum(i.file_size for i in z.infolist()) > 300 * 1024**2:
                raise DataError('El contenido descomprimido supera 300 MB.')
        book = pd.ExcelFile(BytesIO(payload), engine='openpyxl')
        missing = set(IDS) - set(book.sheet_names)
        if missing:
            raise DataError(f'Faltan hojas: {sorted(missing)}')
        tables = {}
        for name in IDS:
            header = book.parse(name, header=None, nrows=1).iloc[0]
            if header.duplicated().any() or header.isna().any():
                raise DataError(f'{name}: encabezados repetidos o vacíos.')
            tables[name] = book.parse(name)
        return tables
    except DataError:
        raise
    except Exception as exc:
        raise DataError('No se pudo leer el Excel. Usa un .xlsx válido, sin contraseña.') from exc


def prepare(tables: dict[str, pd.DataFrame]) -> Dataset:
    """Una sola preparación para dashboard, preguntas y pruebas."""
    clean = {}
    for name in IDS:
        if name not in tables:
            raise DataError(f'Falta la hoja {name}.')
        d = tables[name].copy(deep=True)
        required = set(IDS[name] + DATES.get(name, []) + NUMBERS.get(name, []) + ATTRS[name])
        if d.columns.duplicated().any() or required - set(d.columns):
            raise DataError(f'{name}: revisa encabezados. Faltan: {sorted(required - set(d.columns))}')
        for c in d.select_dtypes(include=['object', 'string']).columns:
            d[c] = d[c].map(lambda v: ' '.join(v.split()) if isinstance(v, str) else v).replace('', pd.NA)
        for c in IDS[name]:
            d[c] = d[c].astype('string').str.strip().str.upper()
        for columns, convert in [(DATES.get(name, []), pd.to_datetime),
                                 (NUMBERS.get(name, []), pd.to_numeric)]:
            for c in columns:
                before = d[c]
                d[c] = convert(before, errors='coerce')
                bad = before.notna() & d[c].isna()
                if bad.any():
                    raise DataError(f'{name}.{c}: {bad.sum()} valores no convertibles. Corrige el origen.')
        clean[name] = d
    for name, key in [('Clientes','Cliente_ID'), ('Productos','Producto_ID'),
                      ('Tiendas','PDV_ID'), ('Campanias','Campania_ID')]:
        if clean[name][key].isna().any() or clean[name][key].duplicated().any():
            raise DataError(f'{name}: claves nulas o repetidas en {key}; unión bloqueada.')
    t = clean['Transacciones']
    t = t.dropna(subset=['Canal']).copy()
    stages = []
    def log(label, rows):
        stages.append({'Etapa': label, 'Filas': len(rows), 'Venta_Neta': rows.Venta_Neta.sum()})
    log('Origen', t)
    duplicated = t.loc[t.duplicated()].copy().assign(Motivo='Duplicado exacto')
    log('Duplicados excluidos', duplicated)
    t = t.drop_duplicates().copy()
    # Un ID repetido con diferente contenido requiere confirmar el grano.
    if t.Transaccion_ID.isna().any() or t.Transaccion_ID.duplicated().any():
        raise DataError('Transaccion_ID nulo o repetido con contenido distinto. Confirma el grano del archivo.')
    if t.Fecha.isna().any():
        raise DataError('Transacciones.Fecha contiene fechas vacías.')
    unknown = t.loc[~t.Cliente_ID.isin(clean['Clientes'].Cliente_ID)].copy().assign(Motivo='Cliente no registrado')
    log('Clientes no registrados excluidos', unknown)
    t = t.loc[t.Cliente_ID.isin(clean['Clientes'].Cliente_ID)].copy()
    expected = {'Venta_Neta': t.Unidades*t.Precio_Unitario*(1-t.Descuento),
                'Costo': t.Unidades*t.Costo_Base, 'Margen': t.Venta_Neta-t.Costo,
                'Margen_%': t.Margen/t.Venta_Neta.replace(0,np.nan)}
    checks = pd.DataFrame({c: np.isfinite(t[c]) & np.isfinite(v) &
                           np.isclose(t[c], v, atol=0.0001 if c=='Margen_%' else 0.01, rtol=0)
                           for c,v in expected.items()}, index=t.index)
    # Añade guardas explícitas para futuros archivos; no corrige cifras por intuición.
    checks['Descuento_en_0_1'] = t.Descuento.between(0,1)
    bad = t.loc[~checks.all(axis=1)].copy()
    bad['Motivo'] = checks.loc[bad.index].apply(lambda r: ', '.join(r.index[~r]), axis=1)
    log('Inconsistencias financieras excluidas', bad)
    t = t.loc[checks.all(axis=1)].copy()
    for name,key,attrs in [('Clientes','Cliente_ID',['Edad','Tipo_Cliente_Actual']),
                           ('Productos','Producto_ID',['Rotacion']), ('Tiendas','PDV_ID',['PDV','Formato'])]:
        t = t.drop(columns=attrs, errors='ignore').merge(clean[name][[key]+attrs], on=key,
                                                       how='left', validate='many_to_one')
    t['Cliente_Registrado'] = True
    camp = clean['Campanias']
    start, end = camp.Fecha_Inicio.dt.normalize(), camp.Fecha_Fin.dt.normalize()
    if (start.isna() | end.isna() | start.gt(end) | camp.Canal.isna()).any():
        raise DataError('Campanias: fecha/canal vacío o inicio posterior al fin.')
    t['Campanias'] = ''
    t['Tipo_Campania'] = ''
    t['Numero_Campanias'] = 0
    for _, c in camp.iterrows():
        hit = (t.Fecha.dt.normalize().between(c.Fecha_Inicio.normalize(), c.Fecha_Fin.normalize()) &
               t.Canal.astype('string').str.casefold().eq(str(c.Canal).casefold())).fillna(False)
        t.loc[hit,'Campanias'] += str(c.Campania_ID)+', '
        t.loc[hit, 'Tipo_Campania'] += (
            str(c.Tipo_Campania) if pd.notna(c.Tipo_Campania)
            else 'Sin tipo'
        ) + ', '
        t.loc[hit,'Numero_Campanias'] += 1
    t['Campanias'] = t.Campanias.str.rstrip(', ').replace('', 'SIN CAMPAÑA')
    t['Tipo_Campania'] = (
        t['Tipo_Campania']
        .str.rstrip(', ')
        .replace('', 'SIN CAMPAÑA')
    )
    t['Contexto_Campania'] = np.select([t.Canal.isna(), t.Numero_Campanias.gt(1), t.Numero_Campanias.eq(1)],
                                      ['No evaluable','Campañas solapadas','Una campaña'], default='Sin campaña')
    for c in ['Canal','Categoria','Subcategoria','Marca','Zona','Ciudad','PDV','Formato','Rotacion','Tipo_Cliente_Actual']:
        t[c] = t[c].fillna('Sin información')
    t['Año'], t['Mes'] = t.Fecha.dt.year, t.Fecha.dt.month
    log('Base analítica', t)
    i = clean['Interacciones'].drop_duplicates().copy()
    if i.Interaccion_ID.isna().any() or i.Interaccion_ID.duplicated().any() or i.Fecha.isna().any():
        raise DataError('Interacciones: IDs nulos/conflictivos o fechas vacías.')
    i = i.loc[i.Cliente_ID.isin(clean['Clientes'].Cliente_ID)].copy()
    return Dataset(t.reset_index(drop=True), i, camp, pd.DataFrame(stages),
                   pd.concat([duplicated,unknown,bad], ignore_index=True))


def load(payload: bytes) -> Dataset:
    return prepare(read_excel(payload))
