"""Ejecutar: python -m streamlit run app.py"""
from pathlib import Path
import logging
import pandas as pd
import streamlit as st
from src.pipeline import load, DataError
from src.analytics import summary, ranking, monthly, discounts, findings
from src.rules import customer_actions, Rules
from src.questions import answer, EXAMPLES
from src.presentation import line_chart, safe_csv
from src.ofertas import render_ofertas

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title='Inteligencia comercial', page_icon='📊', layout='wide')


@st.cache_data(show_spinner=False, max_entries=3)
def cached_load(payload):
    # Los bytes son parte de la clave: mismo nombre con contenido nuevo se recalcula.
    return load(payload)


def table(df, key):
    if df.empty:
        st.info('Sin resultados para esta selección.')
        return
    formats = {c: '{:,.0f}' for c in df.select_dtypes(include='number').columns}
    formats.update({c: '{:.1%}' for c in ['Margen_Pct','Descuento_Max'] if c in df})
    st.dataframe(df.style.format(formats,na_rep='No disponible'), hide_index=True,
                 use_container_width=True)
    st.download_button('Descargar tabla CSV',safe_csv(df),file_name=f'{key}.csv',mime='text/csv',key=key)


def main():
    st.title('Inteligencia comercial')
    st.caption('Ventas, rentabilidad y acciones sobre clientes')
    uploaded = st.sidebar.file_uploader('Cargar base Excel', type=['xlsx'])
    demo = ROOT/'data'/'Base_Datos.xlsx'
    use_demo = st.sidebar.checkbox('Usar base adjunta de ejemplo', value=False) if demo.exists() else False
    if uploaded is None and not use_demo:
        st.info('Carga el Excel original con Transacciones, Clientes, Productos, Tiendas, Campanias e Interacciones.')
        st.write('La aplicación recalcula todo al cambiar el archivo.')
        return
    try:
        with st.spinner('Calculando resultados del archivo…'):
            data = cached_load(uploaded.getvalue() if uploaded else demo.read_bytes())
    except DataError as exc:
        st.error(str(exc))
        st.info('Corrige el archivo y vuelve a cargarlo. No se muestran cifras de una carga anterior.')
        return
    except Exception:
        logging.exception('Error de procesamiento')
        st.error('Ocurrió un error inesperado. Revisa el registro en la terminal y el formato del archivo.')
        return
    if data.sales.empty:
        st.warning('No quedan transacciones válidas después de aplicar las reglas del notebook.')
        return
    s = data.sales
    lo, hi = s.Fecha.min().date(), s.Fecha.max().date()
    # Valores de filtros se reconstruyen al cambiar de archivo.
    dates = st.sidebar.date_input('Periodo de ventas', (lo,hi),min_value=lo,max_value=hi)
    if len(dates)!=2:
        st.info('Selecciona una fecha inicial y una final.'); return
    start, end = map(pd.Timestamp,dates)
    d = s.loc[s.Fecha.ge(start) & s.Fecha.lt(end+pd.Timedelta(days=1))].copy()
    for c in ['Canal','Categoria','Zona']:
        values = sorted(s[c].unique())
        chosen = st.sidebar.multiselect(c,values)
        if chosen:
            d = d.loc[d[c].isin(chosen)]
    st.sidebar.caption('Sin selección = todos. Los filtros aplican a ventas, rankings y tendencias.')
    st.sidebar.subheader('Reglas de clientes')
    inactive = st.sidebar.number_input('Días sin compra para reactivar',30,730,90,step=15)
    intent = st.sidebar.number_input('Ventana de intención (días)',7,180,30,step=1)
    actions = customer_actions(s,data.interactions,end,Rules(inactive_days=inactive,intent_days=intent))
    st.caption(f'Ventas: {start:%d/%m/%Y} — {end:%d/%m/%Y} · Importes en la unidad monetaria del archivo; moneda no documentada.')
    excluded = int(data.audit.loc[data.audit.Etapa.str.contains('excluid'), 'Filas'].sum())
    if excluded:
        st.caption(f'Alcance: clientes registrados y operaciones financieramente consistentes. {excluded:,} filas de origen excluidas; detalle técnico disponible fuera del dashboard.')
    page = st.radio(
        'Vista',
        [
            'Resumen ejecutivo',
            'Desempeño y campañas',
            'Clientes y acciones',
            'Preguntar',
            'Descuentos Alkosto',
            #'Metodología'
        ],
        horizontal=True
    )
    if page == 'Descuentos Alkosto':
        render_ofertas()
    elif page == 'Clientes y acciones':
        st.subheader('Clientes priorizados al corte')
        with st.expander('¿Cómo se asignan las acciones?'):
            st.write(
                'Las reglas se revisan en este orden. Cada cliente recibe '
                'la primera acción que cumple, usando su historial hasta '
                'la fecha final seleccionada.'
            )

            if not actions.empty:
                # Mismo cálculo utilizado por la regla de cliente valioso.
                umbral = actions['Valor_Monetario'].quantile(0.75)
                umbral_texto = f'{umbral:,.0f}'.replace(',', '.')

                st.markdown(f"""
| Prioridad | Acción | ¿Cuándo se asigna? |
|---|---|---|
| 1 | **Revisar rentabilidad** | Su margen histórico es negativo: el costo supera la venta neta acumulada. |
| 2 | **Dar seguimiento** | Tiene un carrito, cotización o consulta en los últimos **{intent} días**, con resultado Sin_Conversion o Seguimiento, posterior a su última compra. |
| 3 | **Reactivar cliente valioso** | Lleva **{inactive} días o más sin comprar** y ha comprado al menos **{umbral_texto}** en total, sin cumplir una regla anterior. |
| 4 | **Reactivar** | Lleva **{inactive} días o más sin comprar** y no cumple ninguna regla anterior. |
| 5 | **Mantener relación** | No cumple las condiciones anteriores. Se recomienda mantener la atención y el seguimiento posventa. |
""")

                st.markdown(
                    f'**¿Qué significa el percentil 75?** '
                    f'Con los datos hasta el corte, el límite calculado es '
                    f'**{umbral_texto}**, en la moneda del archivo. '
                    f'Quienes igualan o superan ese importe están aproximadamente '
                    f'entre el 25 % de clientes que más han comprado. '
                    f'Puede haber más clientes en ese grupo si existen empates. '
                    f'El límite se recalcula cuando cambian los datos o el corte.'
                )

            st.markdown(
                '**¿Se utiliza la frecuencia?** '
                'Se muestra cuántas transacciones de compra tiene cada cliente, '
                'pero ese número no determina su acción. Las reglas actuales '
                'utilizan margen, interacciones, días sin comprar y valor comprado.'
            )
        st.caption(f'Historia completa hasta {end:%d/%m/%Y}. Referencia RFM: día siguiente al corte. No aplica fecha inicial, canal, categoría ni zona.')
        # st.info('Propuestas para revisión humana. El archivo no contiene correo ni consentimiento; no se envían mensajes.')
        if not actions.empty:
            st.caption('**Categoría_Preferida**: categoría con mayor venta histórica neta del cliente. Útil para ofertas dirigidas.')
            
            # Resumen por acción y categoría preferida
            st.subheader('Resumen por acción y categoría preferida')
            action_cat = actions.groupby(['Accion','Categoria_Preferida']).agg(
                Clientes=('Cliente_ID','count'),
                Valor_Monetario_Medio=('Valor_Monetario','mean'),
                Margen_Historico_Medio=('Margen_Historico','mean')
            ).reset_index().sort_values(['Accion','Clientes'], ascending=[True,False])
            action_cat['Valor_Monetario_Medio'] = action_cat['Valor_Monetario_Medio'].round(0)
            action_cat['Margen_Historico_Medio'] = action_cat['Margen_Historico_Medio'].round(0)
            table(action_cat,'resumen_accion_categoria')
            
            choices = st.multiselect('Acciones',sorted(actions.Accion.unique()))
            selected = actions.loc[actions.Accion.isin(choices)] if choices else actions
            table(selected,'acciones_clientes')
        else: st.info('No hay compras positivas hasta el corte.')
    #elif page=='Metodología':
    #    st.markdown((ROOT/'docs'/'METODOLOGIA.md').read_text(encoding='utf-8'))
    elif page=='Preguntar':
        st.subheader('Consulta el negocio por escrito')
        st.caption('Consultor de reglas, no IA generativa. Fechas y filtros se seleccionan en la barra lateral. El resultado indica lo interpretado.')
        example = st.selectbox('Ejemplos soportados',EXAMPLES)
        question = st.text_input('Tu pregunta',value=example,key=f'question_{example}')
        if question.strip():
            result = answer(question,d,actions)
            st.write(result.title); st.caption(result.note)
            if not result.table.empty:
                table(result.table,'respuesta')
                if result.line_metric: st.plotly_chart(line_chart(result.table,result.line_metric),use_container_width=True)
            else: st.info('No hay resultados o la consulta no está soportada.')
    elif d.empty:
        st.info('No hay ventas para estos filtros. Amplía el periodo o la selección.')
    elif page=='Resumen ejecutivo':
        st.subheader('Indicadores del periodo')
        st.caption('Resumen general: venta neta, costo, margen, transacciones, clientes únicos, productos, PDVs, descuento promedio y unidades. Margen % = Margen / Venta neta (ponderado, no promedio).')
        table(summary(d),'indicadores')
        st.subheader('Ventas y margen por categoría y subcategoría')

        ordenar_por = st.selectbox(
            'Ordenar de mayor a menor por',
            ['Venta neta', 'Margen']
        )

        # Reutiliza la función existente y los filtros del dashboard.
        categorias = summary(d, ['Categoria', 'Subcategoria'])

        columna = 'Venta_Neta' if ordenar_por == 'Venta neta' else 'Margen'

        categorias = (
            categorias[
                ['Categoria', 'Subcategoria', 'Venta_Neta', 'Margen', 'Margen_Pct']
            ]
            .sort_values(columna, ascending=False)
            .reset_index(drop=True)
        )

        table(categorias, 'ventas_margen_categorias')
        metric = st.selectbox('Tendencia',['Venta_Neta','Margen'])
        m = monthly(d)
        st.plotly_chart(line_chart(m,metric),use_container_width=True)
        st.caption('Rojo: máximo y mínimo mensual observado por año. Meses sin registros no equivalen a ventas cero. No se garantiza cobertura completa de años o meses.')
        table(m,'mensual')
    else:
        st.subheader('Desempeño comercial')
        st.caption('Ranking agrupando por la dimensión seleccionada. Al ordenar por Producto_ID, se incluye la Categoría para contexto. Métricas: Venta neta (facturación), Margen (rentabilidad absoluta), Margen % (rentabilidad relativa).')
        dimension = st.selectbox('Agrupar por',['Canal','Categoria','Subcategoria','Marca','Producto_ID','PDV','Zona','Tipo_Cliente_Actual', 'Formato'])
        metric = st.selectbox('Ordenar por',['Venta_Neta','Margen','Margen_Pct'])
        n = st.slider('Cantidad de filas',5,100,20)
        table(ranking(d,dimension,metric,n),'ranking')
        st.subheader('Descuentos y rentabilidad')
        st.caption('Distribución de transacciones por tramos de descuento. Muestra cómo el descuento promedio afecta el margen % en cada tramo. Tramos: Sin descuento, ≤10%, 10–20%, 20–30%, >30%.')
        table(discounts(d),'descuentos')
        st.subheader('Ventas según contexto de campaña')
        st.caption('Grupos excluyentes para evitar doble conteo: Sin campaña, Una campaña, Varias campañas. No son conversiones atribuibles ni ROI.')
        table(summary(d,['Contexto_Campania']),'contexto_campania')
        st.subheader('Combinaciones de campañas coincidentes')
        st.caption('Ventas donde coinciden múltiples campañas por canal. Útil para detectar solapamientos; no implica atribución causal.')
        table(
            summary(d, ['Canal', 'Campanias', 'Tipo_Campania']),
            'combinaciones_campanias'
        )


if __name__=='__main__':
    main()
