# Componentes (macros de `_ui/macros.html`)

Generado por `gio_v3/scripts/gen_componentes_md.py`. No se edita a mano: el comentario
`{# … #}` sobre cada macro es la fuente. Antes de crear un componente, revisa `/_ui` (catálogo vivo,
en desarrollo) y esta lista.

```jinja
{% import '_ui/macros.html' as ui %}
```

| Macro | Para qué |
|---|---|
| [`button`](#button) | Botón o enlace (href) con variante primary/secondary/ghost/danger, tamaño sm/md/lg, busy y block. |
| [`iconbtn`](#iconbtn) | Botón de solo ícono: el label es obligatorio (va en aria-label). |
| [`card`](#card) | Tarjeta eu-card (variante interactive/featured/inset/flush); se usa con call. |
| [`stat`](#stat) | Cifra con etiqueta, ícono y delta (↑/↓) o una línea de contexto. |
| [`badge`](#badge) | Insignia: variante de color, tinte de categoría (cat) o de estado (status). |
| [`chip`](#chip) | Chip de filtro o selección con aria-pressed y contador opcional. |
| [`field`](#field) | Campo con <label for>: text, money, textarea; ayuda o error (aria-invalid + aria-describedby). |
| [`progress`](#progress) | Barra de progreso (role=progressbar) por variante o tinte de categoría. |
| [`xpbar`](#xpbar) | Barra de XP hacia la meta, con su aria-label «N de M XP». |
| [`activity`](#activity) | Fila de actividad de Acta marcable (aria-pressed) con su XP/EC. |
| [`row`](#row) | Fila de lista: ícono, título, subtítulo y monto; enlace si lleva href. |
| [`modal`](#modal) | Modal (role=dialog, aria-labelledby) que abre y cierra euModal / euDialog; se usa con call. |
| [`skel`](#skel) | Esqueleto de carga para contenido que llena JS: el envoltorio aria-busy desaparece cuando el script reemplaza el contenedor. |
| [`empty`](#empty) | Vacío (handoff Estados vacíos): un macro, cuatro tipos. |
| [`rank`](#rank) | Insignias de clasificación del día (sprite: _ui/rank_sprite.html) rank acepta el código del motor (carbon/iron/gold/diamond) o el del sprite (carbon/hierro/oro/ |
| [`ranks`](#ranks) | Escalera Carbón → Hierro → Oro → Diamante con el rango actual resaltado. |
| [`tower`](#tower) | Torre estoica: columna dórica de 10 tambores que se llena hasta el nivel actual (antes dashboard/_greek_column.html). |
| [`criterion`](#criterion) | Criterio del siguiente rango (engine.get_daily_classification → criteria[]): ícono cumplido/pendiente · etiqueta + pista · una barrita por unidad de `need` · cu |
| [`page_head`](#page_head) | Encabezado de pantalla (handoff Navegación): h1 = nombre del menú (nav_title, o `title` en el detalle de una entidad), antetítulo = un dato vivo del módulo en e |

## `button`

```jinja
ui.button(label, variant='primary', size='md', icon=None, href=None, busy=False, block=False, type='button', extra='')
```

Botón o enlace (href) con variante primary|secondary|ghost|danger, tamaño sm|md|lg, busy y block.

## `iconbtn`

```jinja
ui.iconbtn(icon, label, variant='', pressed=None)
```

Botón de solo ícono: el label es obligatorio (va en aria-label).

## `card`

```jinja
ui.card(variant='', tag='div', href=None)
```

Tarjeta eu-card (variante interactive|featured|inset|flush); se usa con call.

## `stat`

```jinja
ui.stat(label, value, icon=None, delta=None, delta_dir='up', meta=None)
```

Cifra con etiqueta, ícono y delta (↑/↓) o una línea de contexto.

## `badge`

```jinja
ui.badge(text, variant='', cat=None, status=False, icon=None)
```

Insignia: variante de color, tinte de categoría (cat) o de estado (status).

## `chip`

```jinja
ui.chip(label, pressed=False, count=None, icon=None)
```

Chip de filtro o selección con aria-pressed y contador opcional.

## `field`

```jinja
ui.field(name, label, type='text', value='', placeholder='', help=None, error=None, money=False)
```

Campo con <label for>: text, money, textarea; ayuda o error (aria-invalid + aria-describedby).

## `progress`

```jinja
ui.progress(value, max=100, variant='brand', thin=False, cat=None, label=None)
```

Barra de progreso (role=progressbar) por variante o tinte de categoría.

## `xpbar`

```jinja
ui.xpbar(value, max, label='XP')
```

Barra de XP hacia la meta, con su aria-label «N de M XP».

## `activity`

```jinja
ui.activity(a, done=False)
```

Fila de actividad de Acta marcable (aria-pressed) con su XP/EC.

## `row`

```jinja
ui.row(title, sub=None, icon=None, cat=None, href=None, amount=None, amount_pos=False)
```

Fila de lista: ícono, título, subtítulo y monto; enlace si lleva href.

## `modal`

```jinja
ui.modal(id, title, eyebrow=None, cls='')
```

Modal (role=dialog, aria-labelledby) que abre y cierra euModal / euDialog; se usa con call.

## `skel`

```jinja
ui.skel(rows=3, h=56)
```

Esqueleto de carga para contenido que llena JS: el envoltorio aria-busy desaparece cuando el script reemplaza el contenedor.

## `empty`

```jinja
ui.empty(icon, title, text, cta=None, cta_href=None, cta_icon=None, kbd=None, compact=False, kind='period', steps=None, example_href=None, last=None, ghost=None, drop_filter=None, xp=None, eyebrow=None, cta_attrs=None, cta_class='')
```

Vacío (handoff Estados vacíos): un macro, cuatro tipos. El tipo decide tono, tamaño y acción. · period (por defecto, = lo de siempre): sin datos en este periodo. Con ghost ('bars'|'rows') deja la forma del contenido en fantasma y con last muestra el último periodo con datos junto a la acción. · setup: primer uso del módulo. Ocupa el lugar del contenido: eyebrow, qué hará con datos, 1–3 steps, la acción y «Ver un ejemplo» (example_href, normalmente ?demo=1). · filter: una línea. drop_filter={label, count, href} dice qué filtro sobra y cuántos hay sin él; sin href, el JS de la página lo maneja (.js-empty-drop / .js-empty-hint). · done: todo hecho, tono positivo, compacto y con xp opcional. cta_attrs: atributos extra del botón (p. ej. {'data-quick': 'peso'}); cta_class: clases extra (p. ej. la .js-… que el JS del módulo ya escucha). Con un setup en pantalla, la primera escritura exitosa recarga la página (fetch global del layout) para pasar del vacío al contenido.

## `rank`

```jinja
ui.rank(rank, size=48, label=None, locked=False, cls='')
```

── Insignias de clasificación del día (sprite: _ui/rank_sprite.html) ── rank acepta el código del motor (carbon/iron/gold/diamond) o el del sprite (carbon/hierro/oro/diamante). Sin label = decorativa.

## `ranks`

```jinja
ui.ranks(current, size=44, sm=False)
```

Escalera Carbón → Hierro → Oro → Diamante con el rango actual resaltado.

## `tower`

```jinja
ui.tower(level, height=112, next_name=None)
```

── Torre estoica: columna dórica de 10 tambores que se llena hasta el nivel actual (antes dashboard/_greek_column.html). Degradado en el sprite.

## `criterion`

```jinja
ui.criterion(c)
```

Criterio del siguiente rango (engine.get_daily_classification → criteria[]): ícono cumplido/pendiente · etiqueta + pista · una barrita por unidad de `need` · cuenta have/need. Estilos en dashboard.css (.dash-crit*).

## `page_head`

```jinja
ui.page_head(eyebrow=None, title=None, cls='', id=None)
```

Encabezado de pantalla (handoff Navegación): h1 = nombre del menú (nav_title, o `title` en el detalle de una entidad), antetítulo = un dato vivo del módulo en el tinte del módulo (omitido si no hay), acciones a la derecha vía {% call %}. En móvil el h1 queda solo para lectores de pantalla: la barra superior ya lo muestra.
