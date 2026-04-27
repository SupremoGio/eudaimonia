from flask import Blueprint, redirect

tw_bp = Blueprint('tw', __name__)


@tw_bp.route('/tw')
@tw_bp.route('/logoi')
@tw_bp.route('/paideia')
@tw_bp.route('/eurythmia')
def legacy_redirect():
    return redirect('/', 301)
