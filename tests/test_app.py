from pathlib import Path
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1]/'app.py'


def test_app_navigation():
    app = AppTest.from_file(str(APP),default_timeout=90).run()
    assert not app.exception
    app.sidebar.checkbox[0].check().run()
    assert not app.exception
    assert len(app.dataframe)>=3
    for page in ['Desempeño y campañas','Clientes y acciones','Preguntar','Metodología','Resumen ejecutivo']:
        app.radio[0].set_value(page).run()
        assert not app.exception, page
    app.sidebar.multiselect[0].set_value(['Web']).run()
    assert not app.exception
