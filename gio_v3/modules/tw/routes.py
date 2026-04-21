from flask import Blueprint, render_template

tw_bp = Blueprint('tw', __name__, template_folder='../../templates')


@tw_bp.route('/tw')
def index():
    return render_template('tw/index.html')


@tw_bp.route('/logoi')
def logoi():
    return render_template('tw/proximamente.html',
        pg='logoi',
        pilar='Logoi',
        concepto='Razón aplicada',
        anterior='Programación',
        icon='cpu',
        color='#a78bfa',
        desc='tus proyectos de código, aprendizaje técnico y desarrollo de software'
    )


@tw_bp.route('/paideia')
def paideia():
    return render_template('tw/proximamente.html',
        pg='paideia',
        pilar='Paideia',
        concepto='Formación continua',
        anterior='Aprendizaje · Libros',
        icon='book-open',
        color='#67e8f9',
        desc='tus lecturas, cursos, notas y progreso intelectual'
    )


@tw_bp.route('/eurythmia')
def eurythmia():
    return render_template('tw/proximamente.html',
        pg='eurythmia',
        pilar='Eurythmia',
        concepto='Armonía en movimiento',
        anterior='Baile',
        icon='music',
        color='#f9a8d4',
        desc='tu práctica de baile, ritmo corporal y expresión en movimiento'
    )
