"""python -m scripts.audit ruta.xlsx — no modifica el archivo."""
import argparse
from pathlib import Path
from src.pipeline import load, DataError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('excel',type=Path)
    args = parser.parse_args()
    try:
        d = load(args.excel.read_bytes())
    except (OSError, DataError) as exc:
        parser.exit(1,f'Error: {exc}\n')
    print(d.audit.to_string(index=False))
    print('\nCausas de rechazo:')
    print(d.rejected.Motivo.value_counts().to_string())
    print('\nRango analítico:',d.sales.Fecha.min(), '→',d.sales.Fecha.max())


if __name__=='__main__':
    main()
