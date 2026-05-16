"""
Entry point desde la raíz del repo.
Equivalente a: cd gio_v3 && python run.py
"""
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'gio_v3'))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gio_v3'))

from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
