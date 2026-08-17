from flask import Blueprint, redirect

tw_bp = Blueprint('tw', __name__)


@tw_bp.route('/tw')
@tw_bp.route('/logoi')
def legacy_redirect():
    return redirect('/', 301)
