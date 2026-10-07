"""
doctor.py — Doctor de plantas (Entrega 3): diagnóstico por foto + síntomas,
ficha de cuidados por especie y consejo a partir de la bitácora.

La IA (ia.gemini) solo propone: nada de aquí escribe en la base. Las rutas
(routes.py) guardan el diagnóstico en la bitácora y el usuario decide si
aplica un ajuste. Todo lo que devuelve la IA pasa por sanitize_* antes de
llegar a la UI: rangos acotados, enums válidos y listas cortas.

Lo determinista (resumen del historial) se calcula aquí sin IA y se le pasa
como dato, para que el consejo hable de hechos ("regada cada 4 d con
intervalo de 9") y no de suposiciones.
"""
import json
import statistics
from datetime import date

SINTOMAS = {
    'hojas_amarillas': 'Hojas amarillas',
    'puntas_cafes':    'Puntas o bordes cafés/secos',
    'manchas':         'Manchas en las hojas',
    'hojas_caidas':    'Hojas caídas o lacias',
    'quemaduras':      'Hojas quemadas o decoloradas por sol',
    'plagas':          'Bichos, telarañas o algodoncillos',
    'tallo_blando':    'Tallo blando o negro en la base',
    'no_crece':        'No crece / hojas nuevas pequeñas',
    'hongos':          'Moho u hongos en la tierra',
    'enrolladas':      'Hojas enrolladas o arrugadas',
}

_LUZ_TXT = {'': 'sin especificar', 'baja': 'baja (lejos de ventanas)', 'media': 'media',
            'brillante': 'brillante indirecta', 'sol_directo': 'sol directo'}
_LUCES = ('baja', 'media', 'brillante', 'sol_directo')

MIN_RIEGOS_CONSEJO = 3


# ── Contexto ─────────────────────────────────────────────────────────────────

def resumen_historial(bitacora, intervalo_efectivo, hoy):
    """Hechos de la bitácora (filas con tipo, fecha, notas; cualquier orden).
    Intervalo real entre riegos (mediana de los últimos 120 días), veces que
    se pospuso por «aún húmeda» y últimos diagnósticos."""
    def _d(f):
        try:
            return date.fromisoformat(str(f)[:10])
        except ValueError:
            return None
    riegos = sorted({d for b in bitacora if b['tipo'] == 'riego' and (d := _d(b['fecha']))
                     and (hoy - d).days <= 120})
    gaps = [(b - a).days for a, b in zip(riegos, riegos[1:]) if (b - a).days > 0]
    revisiones = sum(1 for b in bitacora if b['tipo'] == 'revision'
                     and (d := _d(b['fecha'])) and (hoy - d).days <= 90)
    diags = sorted((b for b in bitacora if b['tipo'] == 'diagnostico'),
                   key=lambda b: str(b['fecha']), reverse=True)[:3]
    return {
        'n_riegos': len(riegos),
        'intervalo_real': round(statistics.median(gaps), 1) if gaps else None,
        'intervalo_configurado': intervalo_efectivo,
        'ultimo_riego_hace': (hoy - riegos[-1]).days if riegos else None,
        'revisiones_humeda': revisiones,
        'diagnosticos': [f"{str(b['fecha'])[:10]}: {b.get('notas') or ''}" for b in diags],
    }


def contexto_planta(p, temporada, hist):
    """Bloque de texto con todo lo que se sabe de la planta."""
    lineas = [
        f"Nombre: {p.get('nombre')}",
        f"Especie: {p.get('especie') or 'no registrada'}"
        + (f" (confirmada: {p['especie_cientifica']})" if p.get('especie_cientifica') else ''),
        f"Dónde vive: {'balcón (exterior, recibe clima)' if p.get('entorno') == 'balcon' else 'interior'}"
        + (f", {p['ubicacion']}" if p.get('ubicacion') else ''),
        f"Luz: {_LUZ_TXT.get(p.get('luz') or '', p.get('luz'))}",
        f"Ciudad: Guadalajara, Jalisco. Temporada actual: {temporada}",
        f"Riego configurado: cada {p.get('dias_riego')} d (efectivo por temporada: cada {p.get('riego_interval_efectivo')} d)",
        f"Trasplante: cada {p.get('meses_trasplante')} meses; último: {p.get('last_trasplante') or 'sin registro'}",
    ]
    if hist['intervalo_real'] is not None:
        lineas.append(f"Historial real: {hist['n_riegos']} riegos en 120 días, cada {hist['intervalo_real']} d en promedio "
                      f"(mediana); último hace {hist['ultimo_riego_hace']} d")
    elif hist['ultimo_riego_hace'] is not None:
        lineas.append(f"Último riego registrado: hace {hist['ultimo_riego_hace']} d")
    if hist['revisiones_humeda']:
        lineas.append(f"Veces que la tierra seguía húmeda al revisar (90 días): {hist['revisiones_humeda']}")
    for c in p.get('cuidados') or []:
        lineas.append(f"{c['label']}: cada {c['cada_dias']} d, último {c.get('last_fecha') or 'sin registro'}")
    if hist['diagnosticos']:
        lineas.append('Diagnósticos anteriores: ' + ' | '.join(hist['diagnosticos']))
    if p.get('notas'):
        lineas.append(f"Notas del usuario: {p['notas']}")
    return '\n'.join(lineas)


_REGLAS = """REGLAS:
- Habla de ESTA planta: menciona su especie, si está en interior o balcón, la temporada y su historial cuando sea relevante.
- Prohibido el consejo genérico ("dale buena luz", "riega adecuadamente", "cuida tu planta"): da cantidades, frecuencias, lugares y señales concretas.
- Si algo no se puede saber con lo que hay, dilo; no inventes.
- Todo en español de México, directo."""


def prompt_diagnostico(contexto, sintomas, texto, con_foto):
    sint = ', '.join(SINTOMAS[s] for s in sintomas if s in SINTOMAS) or 'ninguno marcado'
    foto = ("Se adjunta una FOTO actual de la planta: descríbela en 'en_la_foto' y úsala como evidencia principal. "
            "Si está borrosa, oscura o no se ve la planta, pon pedir_mejor_foto=true.") if con_foto else \
           "No hay foto: diagnostica con los síntomas y el historial, y baja la confianza."
    return f"""Eres un horticultor experto en plantas de interior y de balcón, con experiencia en el clima de Guadalajara.
Diagnostica qué le pasa a esta planta.

PLANTA:
{contexto}

SÍNTOMAS MARCADOS: {sint}
LO QUE CUENTA EL USUARIO: {texto or '(nada)'}
{foto}

{_REGLAS}
- Ordena las causas de más a menos probable; las probabilidades suman ~100. Cruza los síntomas con el historial (p. ej. riego más frecuente que el configurado + hojas amarillas bajas = exceso de riego).
- Acciones paso a paso, cada una con cuándo hacerla.
- Si conviene cambiar la frecuencia de riego o la luz, ponlo en ajustes_sugeridos; si no, déjalo vacío.

Responde SOLO con JSON:
{{"resumen":"una frase con el diagnóstico principal","urgencia":"baja|media|alta","confianza":"alta|media|baja",
"en_la_foto":"qué se ve en la foto (vacío si no hay)",
"causas":[{{"causa":"...","probabilidad":70,"evidencia":"qué síntoma/dato la apoya"}}],
"acciones":[{{"paso":"...","cuando":"hoy|esta semana|este mes"}}],
"vigilar":["señal concreta y en cuánto tiempo"],
"ajustes_sugeridos":{{"dias_riego":11,"luz":"baja|media|brillante|sol_directo"}},
"pedir_mejor_foto":false}}"""


def prompt_ficha(especie, entorno, luz, con_foto):
    ident = ("Se adjunta una FOTO: identifica la especie a partir de ella"
             + (f" (el usuario cree que es «{especie}»)" if especie else '') + ".") if con_foto else \
            f"Especie indicada por el usuario: «{especie}»."
    return f"""Eres un horticultor experto en plantas de interior y de balcón en Guadalajara, Jalisco (clima subtropical de altura: seco casi todo el año, lluvias de junio a septiembre, calor fuerte en abril-mayo).
{ident}
Vive en: {'balcón' if entorno == 'balcon' else 'interior'}. Luz: {_LUZ_TXT.get(luz or '', luz)}.

Da su ficha de cuidados para ESE entorno y esa luz (valores base; la app ya ajusta el riego por temporada).
{_REGLAS}
- Si no reconoces la especie, confianza "baja" y valores conservadores.
- fertilizar_cada_dias en temporada de crecimiento (la app lo pausa de noviembre a febrero); null si no conviene fertilizarla.

Responde SOLO con JSON:
{{"especie":"nombre científico","nombre_comun":"nombre común en México","confianza":"alta|media|baja",
"dias_riego":9,"meses_trasplante":18,"fertilizar_cada_dias":30,
"luz_ideal":"baja|media|brillante|sol_directo","humedad":"frase corta","toxica_mascotas":true,
"nota_entorno":"lo más importante de cuidarla en {('balcón' if entorno == 'balcon' else 'interior')} en Guadalajara, 1-2 frases"}}"""


def prompt_consejo(contexto):
    return f"""Eres un horticultor experto. Revisa el historial REAL de cuidados de esta planta y di si el usuario la está cuidando bien.

PLANTA:
{contexto}

{_REGLAS}
- Compara el intervalo real de riego con el configurado y con lo que necesita la especie en su entorno y temporada.
- Si se pospuso varias veces porque seguía húmeda, probablemente el intervalo es corto.
- Propón como máximo UN ajuste numérico (dias_riego) y solo si está justificado por los datos.

Responde SOLO con JSON:
{{"observacion":"qué muestran los datos, con números","recomendacion":"qué hacer, concreto",
"ajuste":{{"campo":"dias_riego","valor":11,"razon":"..."}} o null}}"""


# ── Validación de respuestas ─────────────────────────────────────────────────

def _txt(v, n=300):
    return str(v or '').strip()[:n]


def _enum(v, opciones, default):
    v = str(v or '').strip().lower()
    return v if v in opciones else default


def _int(v, lo, hi):
    try:
        n = int(round(float(v)))
    except (TypeError, ValueError):
        return None
    return n if lo <= n <= hi else None


def sanitize_diagnostico(d):
    causas = []
    for c in (d.get('causas') or [])[:4]:
        if isinstance(c, dict) and c.get('causa'):
            causas.append({'causa': _txt(c['causa'], 120), 'evidencia': _txt(c.get('evidencia'), 240),
                           'probabilidad': max(0, min(100, _int(c.get('probabilidad'), -1000, 1000) or 0))})
    causas.sort(key=lambda c: -c['probabilidad'])
    acciones = []
    for a in (d.get('acciones') or [])[:6]:
        if isinstance(a, dict) and a.get('paso'):
            acciones.append({'paso': _txt(a['paso'], 240),
                             'cuando': _enum(a.get('cuando'), ('hoy', 'esta semana', 'este mes'), 'esta semana')})
    aj_in = d.get('ajustes_sugeridos') if isinstance(d.get('ajustes_sugeridos'), dict) else {}
    ajustes = {}
    if (dr := _int(aj_in.get('dias_riego'), 1, 45)) is not None:
        ajustes['dias_riego'] = dr
    if str(aj_in.get('luz') or '') in _LUCES:
        ajustes['luz'] = aj_in['luz']
    vigilar = d.get('vigilar') or []
    if isinstance(vigilar, str):
        vigilar = [vigilar]
    return {
        'resumen': _txt(d.get('resumen'), 200) or 'Sin diagnóstico claro',
        'urgencia': _enum(d.get('urgencia'), ('baja', 'media', 'alta'), 'media'),
        'confianza': _enum(d.get('confianza'), ('alta', 'media', 'baja'), 'baja'),
        'en_la_foto': _txt(d.get('en_la_foto'), 300),
        'causas': causas,
        'acciones': acciones,
        'vigilar': [_txt(v, 200) for v in vigilar[:4] if v],
        'ajustes_sugeridos': ajustes,
        'pedir_mejor_foto': bool(d.get('pedir_mejor_foto')),
    }


def sanitize_ficha(d):
    fert = d.get('fertilizar_cada_dias')
    tox = d.get('toxica_mascotas')
    return {
        'especie': _txt(d.get('especie'), 80),
        'nombre_comun': _txt(d.get('nombre_comun'), 80),
        'confianza': _enum(d.get('confianza'), ('alta', 'media', 'baja'), 'baja'),
        'dias_riego': _int(d.get('dias_riego'), 1, 45) or 7,
        'meses_trasplante': _int(d.get('meses_trasplante'), 6, 48) or 12,
        'fertilizar_cada_dias': _int(fert, 7, 90) if fert is not None else None,
        'luz_ideal': _enum(d.get('luz_ideal'), _LUCES, ''),
        'humedad': _txt(d.get('humedad'), 120),
        'toxica_mascotas': tox if isinstance(tox, bool) else None,
        'nota_entorno': _txt(d.get('nota_entorno'), 300),
    }


def sanitize_consejo(d):
    aj = d.get('ajuste') if isinstance(d.get('ajuste'), dict) else None
    ajuste = None
    if aj and aj.get('campo') == 'dias_riego' and (v := _int(aj.get('valor'), 1, 45)) is not None:
        ajuste = {'campo': 'dias_riego', 'valor': v, 'razon': _txt(aj.get('razon'), 240)}
    return {
        'observacion': _txt(d.get('observacion'), 400),
        'recomendacion': _txt(d.get('recomendacion'), 400),
        'ajuste': ajuste,
    }


def clave_ficha(especie_norm, entorno, luz):
    return json.dumps([especie_norm, entorno, luz or ''], ensure_ascii=False)
