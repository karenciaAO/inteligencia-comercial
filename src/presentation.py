"""Presentación: tablas numéricas y las dos líneas mensuales del notebook."""
import pandas as pd
import plotly.graph_objects as go

MONTHS = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']


def line_chart(monthly, metric):
    fig = go.Figure()
    colors = ['#087F8C','#3757A6','#B36A23','#8056A1']
    for pos, (year, rows) in enumerate(monthly.groupby('Año')):
        y = rows.set_index('Mes')[metric].reindex(range(1,13))
        fig.add_trace(go.Scatter(x=list(range(1,13)),y=y, mode='lines+markers',
                      name=str(year),connectgaps=False,line=dict(color=colors[pos%len(colors)],width=3),
                      hovertemplate='%{y:,.0f}<extra>%{fullData.name}</extra>'))
        for label, month in [('Máximo',y.idxmax()),('Mínimo',y.idxmin())]:
            fig.add_trace(go.Scatter(x=[month],y=[y.loc[month]],mode='markers',
                          marker=dict(color='#C62828',size=10),showlegend=False,
                          hovertemplate=f'{label} {year}: %{{y:,.0f}}<extra></extra>'))
    fig.update_layout(height=400,margin=dict(l=15,r=15,t=35,b=20),
                      title='Venta neta mensual' if metric=='Venta_Neta' else 'Margen mensual',
                      xaxis=dict(tickmode='array',tickvals=list(range(1,13)),ticktext=MONTHS),
                      yaxis=dict(rangemode='tozero',tickformat=',.0f'),
                      paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',legend_title='Año')
    return fig


def safe_csv(df):
    """Neutraliza fórmulas al abrir las descargas en Excel."""
    d = df.copy()
    for c in d.select_dtypes(include=['object','string']).columns:
        d[c] = d[c].map(lambda v: "'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v)
    return d.to_csv(index=False).encode('utf-8-sig')
