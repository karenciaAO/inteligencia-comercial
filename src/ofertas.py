"""Vista opcional de ofertas: solo consulta la red al abrir esta vista."""
import math
import hashlib
from datetime import datetime, timezone
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

# Mismos grupos y categorías consultadas en el notebook.
GROUPS = {
    'Tecnología': ['TV', 'Smart TV', 'Computadores y Tablet',
                   'Computadores Portátiles', 'Portátiles Laptops y Convertibles 2 en 1',
                   'Celulares', 'Smartphones', 'Consolas y Videojuegos', 'Monitores'],
    'Hogar': ['Electrodomésticos', 'Refrigeración', 'Lavado', 'Lavadoras',
              'Neveras', 'Audio Para el Hogar'],
    'Accesorios': ['Accesorios de Electrónica', 'Accesorios Computadores',
                  'Accesorios Celulares y Tabletas', 'Relojes y Anillos inteligentes'],
    'Entretenimiento': ['Audio', 'Audífonos'],
}
ATTRS = 'objectID,code_string,name_text_es,brand_string_mv,baseprice_cop_string,discountprice_double'


def top_products(results, categories):
    """Calcula descuentos antes de redondear y deduplica por ID del catálogo."""
    rows = []
    for result, category in zip(results, categories):
        if not isinstance(result, dict) or not isinstance(result.get('hits'), list):
            raise ValueError('Respuesta de catálogo incompleta')
        for hit in result['hits']:
            try:
                base = float(hit['baseprice_cop_string'])
                offer = float(hit['discountprice_double'])
            except (KeyError, ValueError, TypeError):
                continue
            code = hit.get('code_string') or hit.get('objectID')
            name = hit.get('name_text_es')
            if not code or not name or not (math.isfinite(base) and math.isfinite(offer) and 0 < offer < base):
                continue
            brand = hit.get('brand_string_mv') or 'Sin marca'
            if isinstance(brand, list):
                brand = brand[0] if brand else 'Sin marca'
            rows.append({'ID': str(code), 'Categoría Alkosto': category, 'Marca': str(brand),
                         'Producto': str(name), 'Precio original COP': base,
                         'Precio oferta COP': offer, 'Descuento %': (1-offer/base)*100})
    if not rows:
        return pd.DataFrame()
    return (pd.DataFrame(rows).sort_values(['Descuento %', 'ID'], ascending=[False, True])
            .drop_duplicates('ID').head(5).drop(columns='ID').reset_index(drop=True))


@st.cache_data(ttl=6*60*60, show_spinner=False, max_entries=16)
def fetch_offers(group, app_id, api_key, index):
    """Una petición HTTP agrupada, hasta 200 productos por categoría del grupo."""
    categories = GROUPS[group]
    queries = [{'indexName': index, 'params': urlencode({
        'hitsPerPage': 200, 'page': 0,
        'filters': f'categoryname_text_es_mv:"{cat}" AND discountprice_double>0',
        'attributesToRetrieve': ATTRS, 'attributesToHighlight': '',
    })} for cat in categories]
    response = requests.post(
        f'https://{app_id.lower()}-dsn.algolia.net/1/indexes/*/queries',
        json={'requests': queries},
        headers={'X-Algolia-API-Key': api_key, 'X-Algolia-Application-Id': app_id},
        timeout=(3, 6),  # conexión / espera de datos; sin reintentos automáticos
    )
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        raise ValueError('Formato de respuesta inesperado')
    results = body.get('results')
    if not isinstance(results, list) or len(results) != len(categories):
        raise ValueError('Formato de respuesta inesperado')
    table = top_products(results, categories)
    return table, datetime.now(timezone.utc)


def render_ofertas():
    st.subheader('Descuentos publicados en Alkosto')
    st.caption('Top 5 productos con mayor descuento. Precios en Pesos Colombianos.')
    group = st.selectbox('Categoría de negocio', list(GROUPS), key='alkosto_group')
    # Configuración de consulta incluida en el notebook proporcionado.
    app_id = 'QX5IPS1B1Q'
    index = 'alkostoIndexAlgoliaPRD'
    api_key = '7a8800d62203ee3a9ff1cdf74f99b268'
    # Evita repetir solicitudes fallidas en cada interacción durante cinco minutos.
    fingerprint = hashlib.sha256(f'{app_id}|{index}|{api_key}'.encode()).hexdigest()[:16]
    state_key = f'alkosto_result_{group}_{fingerprint}'
    state = st.session_state.get(state_key, {})
    now = datetime.now(timezone.utc)
    retry_at = state.get('retry_at')
    if not retry_at or (now-retry_at).total_seconds() >= 300:
        try:
            with st.spinner('Consultando ofertas…'):
                frame, fetched_at = fetch_offers(group, app_id, api_key, index)
            state = {'frame': frame, 'fetched_at': fetched_at}
        except (requests.RequestException, ValueError, TypeError, KeyError):
            state['retry_at'] = now
        st.session_state[state_key] = state
    if state.get('retry_at'):
        st.warning('No se pudo actualizar la fuente. Se reintentará al visitar esta vista después de cinco minutos.')
        if 'frame' in state:
            st.caption('Se muestra la última consulta disponible de esta sesión; puede estar desactualizada.')
        else:
            return
    frame = state['frame']
    local_time = state['fetched_at'].astimezone(ZoneInfo('America/Bogota'))
    st.caption(f'Consultado: {local_time:%d/%m/%Y %H:%M} (Colombia). Caché de seis horas.')
    if frame.empty:
        st.info('No se encontraron descuentos válidos en la muestra consultada.')
    else:
        tabla_formateada = frame.style.format({
            'Precio original COP': lambda valor: f'{valor:,.0f}'.replace(',', '.'),
            'Precio oferta COP': lambda valor: f'{valor:,.0f}'.replace(',', '.'),
            'Descuento %': lambda valor: f'{valor:.1f} %'.replace('.', ','),
        })

        st.dataframe(
            tabla_formateada,
            hide_index=True,
            use_container_width=True
        )
    st.caption('Ofertas actuales: no dependen de las fechas del Excel. Se revisan hasta 200 productos por categoría Alkosto; no es un ranking de todo el catálogo. Verifica precio y disponibilidad antes de actuar.')
