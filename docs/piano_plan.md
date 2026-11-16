# Prioridad piano · 2026-11-16 → 2027-02-16

Durante 3 meses el piano es la prioridad. Lo aplica la migración `piano_prioridad_2026_11`, en `gio_v3/database.py`, que corre una sola vez al arrancar. El modelo de hábitos (`activity_defs`) no tiene campo de notas ni fechas de pausa, así que las descripciones y el plan viven aquí.

## Hábitos nuevos (Eurythmia)

| Hábito | Clave | Tipo | Cuándo | Recompensa | Qué es |
|---|---|---|---|---|---|
| Piano – Flowkey 10 min | `piano_flowkey` | touch | diario · noche | 2 pts | 1 lección nueva del curso de Flowkey de la semana + 5–10 min de repaso o canción en loop. |
| Piano – Pianoforall (sesión profunda) | `piano_pianoforall` | ancla | lun/mié/vie · tarde | los pts y EC que tenía el ancla de CCNA (8 pts · 3 EC en la lista base) | 30–35 min (45 desde la semana 5): 5 de repaso, 10 de videos nuevos, 15–20 de práctica. No avanzar de lección hasta tocarla limpia. |
| Grabar pieza al terminar un libro de Pianoforall | `piano_grabar_libro` | ocasional | sin horario | los pts del bonus «Gol» (2 pts) | Una grabación al cerrar cada libro. |
| Baile — sesión profunda | `ancla_baile` | ancla | jue/sáb · noche | XP y EC de la sesión | Se completa al guardar la sesión en `/eurythmia/`, igual que el resto del baile. |

- **Se marcan a mano en Acta:** los hábitos de piano (`EURY_MANUAL_KEYS` en `modules/actividades/activity_defs.py`).
- **Baile:** el resto de Eurythmia se marca con una sesión real en Eurythmia (`eury_proxy`).
- **Ancla y touch, sin enlace automático:** completar el ancla de piano no marca el touch de Flowkey. Se decidió no hacerlo porque el motor ya premia las anclas extra bajando los touches que pide para Oro, y el mismo esfuerzo contaría dos veces.

## Logoi en pausa

**Desactivados** (`active=0`; el historial se conserva):
- CCNA / Programación — sesión profunda
- Lección SoloLearn / Mimo
- Leer programación
- Lección 100 Días Python
- Subir proyecto a GitHub

**«Resolver 5 problemas reales»** pasa a ocasional (sin racha).

**Reactivación:** el 2027-02-16 aparece un recordatorio único en Perfil › Recordatorios y en la campana. Se reactiva a mano desde Acta › editar hábitos:
- se vuelven a activar los 5 hábitos de arriba;
- «Resolver 5 problemas reales» regresa a touch;
- se decide qué pasa con los hábitos de piano.

## Calendario de anclas

| Día | Anclas |
|---|---|
| Lunes | Piano · Inglés |
| Martes | Francés · Leer psicología |
| Miércoles | Piano · Fútbol |
| Jueves | Inglés · Baile |
| Viernes | Piano · Francés |
| Sábado | Baile |
| Domingo | Leer psicología |

Además está **Ejercicio Gym**, que es un ancla diaria.

## Plan de 13 semanas

| Semanas | Pianoforall | Flowkey |
|---|---|---|
| 1–3 | Libro 1 · Party Time | Introducción al piano |
| 4–5 | Libro 2 · Blues & Rock'n'Roll | Tocar con ambas manos |
| 6–8 | Libro 3 · Chord Magic | Lectura de partituras + escalas |
| 9–10 | Libro 4 · Advanced Chord Magic | Dominar acordes |
| 11–13 | Libro 5 · Ballad Style | Improvisar con acordes + 1 canción lenta |

- **Desde la semana 5,** la sesión de Pianoforall sube a 45 min.
- **Al terminar cada libro,** marca «Grabar pieza».
