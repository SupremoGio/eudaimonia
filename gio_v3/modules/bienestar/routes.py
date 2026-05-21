from flask import Blueprint, redirect

bienestar_bp = Blueprint('bienestar', __name__, template_folder='../../templates')

@bienestar_bp.route('/')
def index():
    return redirect('/bienestar/salud')
