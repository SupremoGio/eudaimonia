import json, random
from flask import Blueprint, render_template, request, jsonify
from database import get_db
from datetime import date, timedelta
from utils import today_str, today_date

nutricion_bp = Blueprint('nutricion', __name__, template_folder='../../templates')

# ── Helpers de tiempo/semana ──────────────────────────────────────────────────

DAY_KEYS = {0: 'L', 1: 'M', 2: 'X', 3: 'J', 4: 'V', 5: 'S', 6: 'D'}

def get_week_start():
    td = today_date()
    return td - timedelta(days=td.weekday())

def get_today_key():
    return DAY_KEYS[today_date().weekday()]

# ── Menú semanal FODMAP (Semana de reseteo SII — Dr. González / Elizabeth) ────

PLAN_TEMPLATE = {
    'L': [
        {
            'slot': 'Desayuno', 'time': '07:30', 'xp': 12, 'tag': 'safe',
            'name': 'Huevos revueltos con espinacas y ejotes',
            'kcal': 450, 'protein': 30,
            'note': 'Desayuno rápido entre semana. Listo en 5–7 min.',
            'items': [
                {'t': '3 huevos revueltos con espinacas y ejotes picados', 'tag': 'safe'},
                {'t': '2 cdtas de aceite para cocinar', 'tag': 'safe'},
                {'t': '40 g de queso panela', 'tag': 'safe'},
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '1 kiwi', 'tag': 'safe'},
            ],
            'swap': 'Rota la fruta: kiwi ↔ mandarina ↔ papaya. Rota la verdura del huevo: espinacas+ejotes ↔ espinacas+calabacita.',
        },
        {
            'slot': 'Colación 1', 'time': '10:30', 'xp': 8, 'tag': 'safe',
            'name': 'Mandarina + naranja + tostadas de arroz',
            'kcal': 170, 'protein': 3,
            'note': 'Portátil y fácil de llevar a la oficina.',
            'items': [
                {'t': '1 mandarina + 1 naranja', 'tag': 'safe'},
                {'t': '2 tostadas de arroz', 'tag': 'safe'},
                {'t': 'Pepino con limón', 'tag': 'safe'},
            ],
            'swap': 'Intercambia verdura: pepino ↔ zanahoria ↔ jícama ↔ tomates cherry.',
        },
        {
            'slot': 'Comida', 'time': '13:30', 'xp': 14, 'tag': 'safe',
            'name': 'Tostadas de nopal con pollo deshebrado',
            'kcal': 500, 'protein': 38,
            'note': 'Del batch del domingo. Solo ensambla.',
            'items': [
                {'t': '3 tostadas de maíz horneadas', 'tag': 'safe'},
                {'t': '150 g de pollo deshebrado', 'tag': 'safe'},
                {'t': 'Nopales guisados con aceite infusionado de ajo/cebolla', 'tag': 'safe'},
            ],
            'swap': 'Puedes agregar salsa verde de tomatillo sin chile.',
        },
        {
            'slot': 'Pre-gym', 'time': '18:00', 'xp': 8, 'tag': 'safe',
            'name': 'Plátano firme + tostadas con crema de cacahuate',
            'kcal': 240, 'protein': 5,
            'note': '60–90 min antes de entrenar. Glucógeno sin pesar el estómago.',
            'items': [
                {'t': '1 plátano firme (poco maduro)', 'tag': 'caution', 'why': 'Firme = menos fructanos. Evita el maduro.'},
                {'t': '2 tostadas de arroz', 'tag': 'safe'},
                {'t': '1 cdta de crema de cacahuate sin azúcar', 'tag': 'safe'},
            ],
            'swap': 'Si no entrenas, omite la crema de cacahuate y reduce a 1 tostada.',
        },
        {
            'slot': 'Cena', 'time': '20:30', 'xp': 12, 'tag': 'safe',
            'name': 'Tacos de pollo con nopales asados',
            'kcal': 430, 'protein': 35,
            'note': 'Post-gym: proteína + carbo para recuperar. Ligera y fácil de digerir.',
            'items': [
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '120 g de pechuga asada', 'tag': 'safe'},
                {'t': '2 nopales asados', 'tag': 'safe'},
                {'t': 'Cilantro fresco + limón', 'tag': 'safe'},
                {'t': '1 taza de papaya', 'tag': 'safe'},
            ],
            'swap': 'Cambia papaya por naranja o kiwi si prefieres.',
        },
    ],
    'M': [
        {
            'slot': 'Desayuno', 'time': '07:30', 'xp': 12, 'tag': 'safe',
            'name': 'Huevos revueltos con calabacita y cilantro',
            'kcal': 445, 'protein': 30,
            'note': 'Misma base del lunes, diferente verdura.',
            'items': [
                {'t': '3 huevos revueltos con calabacita rallada y cilantro fresco', 'tag': 'safe'},
                {'t': '2 cdtas de aceite para cocinar', 'tag': 'safe'},
                {'t': '40 g de queso panela', 'tag': 'safe'},
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '1 mandarina', 'tag': 'safe'},
            ],
            'swap': 'Rota fruta: mandarina ↔ kiwi ↔ papaya.',
        },
        {
            'slot': 'Colación 1', 'time': '10:30', 'xp': 8, 'tag': 'safe',
            'name': 'Papaya + tostadas de arroz + zanahoria',
            'kcal': 165, 'protein': 3,
            'note': 'Portátil. Lleva la zanahoria cortada desde casa.',
            'items': [
                {'t': '1 taza de papaya', 'tag': 'safe'},
                {'t': '2 tostadas de arroz', 'tag': 'safe'},
                {'t': 'Bastones de zanahoria con limón', 'tag': 'safe'},
            ],
            'swap': 'Intercambia fruta low risk: papaya ↔ kiwi ↔ mandarina.',
        },
        {
            'slot': 'Comida', 'time': '13:30', 'xp': 14, 'tag': 'safe',
            'name': 'Arroz integral con pollo y calabacitas',
            'kcal': 530, 'protein': 40,
            'note': 'Del batch del domingo. Sin jitomate, sin cebolla.',
            'items': [
                {'t': '½ taza de arroz integral cocido', 'tag': 'safe'},
                {'t': 'Calabacitas guisadas con cilantro y aceite infusionado de ajo', 'tag': 'safe'},
                {'t': '150 g de pollo deshebrado', 'tag': 'safe'},
                {'t': '1 tortilla de maíz', 'tag': 'safe'},
                {'t': '2 cdtas de aceite de oliva', 'tag': 'safe'},
            ],
            'swap': 'Arroz integral ↔ arroz blanco; ambos son low risk.',
        },
        {
            'slot': 'Pre-gym', 'time': '18:00', 'xp': 8, 'tag': 'safe',
            'name': 'Kiwi + tostadas con crema de cacahuate',
            'kcal': 225, 'protein': 5,
            'note': 'Pre-gym ligero. El kiwi también ayuda al tránsito intestinal.',
            'items': [
                {'t': '1 kiwi', 'tag': 'safe'},
                {'t': '2 tostadas de arroz', 'tag': 'safe'},
                {'t': '1 cdta de crema de cacahuate sin azúcar', 'tag': 'safe'},
            ],
            'swap': 'Cambia kiwi por plátano firme si lo prefieres.',
        },
        {
            'slot': 'Cena', 'time': '20:30', 'xp': 12, 'tag': 'safe',
            'name': 'Entomatadas de pollo en salsa verde',
            'kcal': 420, 'protein': 34,
            'note': 'Salsa de tomatillo (sin jitomate, sin chile). Ligera post-gym.',
            'items': [
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '120 g de pollo deshebrado', 'tag': 'safe'},
                {'t': '½ taza de calabacita en cubos', 'tag': 'safe'},
                {'t': 'Salsa verde de tomatillo sin chile', 'tag': 'safe'},
                {'t': '¾ taza de piña', 'tag': 'safe'},
            ],
            'swap': 'Cambia piña por papaya o mandarina.',
        },
    ],
    'X': [
        {
            'slot': 'Desayuno', 'time': '07:30', 'xp': 12, 'tag': 'safe',
            'name': 'Huevos revueltos con espinacas y calabacita',
            'kcal': 445, 'protein': 30,
            'note': 'Rota las verduras del huevo para no aburrirte.',
            'items': [
                {'t': '3 huevos revueltos con espinacas y calabacita rallada', 'tag': 'safe'},
                {'t': '2 cdtas de aceite para cocinar', 'tag': 'safe'},
                {'t': '40 g de queso panela', 'tag': 'safe'},
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '1 taza de papaya', 'tag': 'safe'},
            ],
            'swap': 'Rota la fruta: papaya ↔ kiwi ↔ mandarina.',
        },
        {
            'slot': 'Colación 1', 'time': '10:30', 'xp': 8, 'tag': 'safe',
            'name': 'Mandarinas + tostadas con cacahuate + pepino',
            'kcal': 195, 'protein': 4,
            'note': 'Hoy lleva crema de cacahuate en la colación 1.',
            'items': [
                {'t': '2 mandarinas', 'tag': 'safe'},
                {'t': '2 tostadas de arroz con 1 cdta de crema de cacahuate', 'tag': 'safe'},
                {'t': 'Pepino con limón', 'tag': 'safe'},
            ],
            'swap': 'Intercambia pepino por zanahoria o jícama.',
        },
        {
            'slot': 'Comida', 'time': '13:30', 'xp': 14, 'tag': 'safe',
            'name': 'Picadillo de res con sopa de verduras',
            'kcal': 560, 'protein': 40,
            'note': 'Del batch del domingo. Sin jitomate, sin cebolla. Aceite infusionado para el sabor.',
            'items': [
                {'t': '1 taza de sopa de verduras (caldo de pollo con hierbas)', 'tag': 'safe'},
                {'t': '150 g de picadillo de res magro con zanahoria, papa y hierbas', 'tag': 'safe'},
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '2 cdtas de aceite infusionado de ajo/cebolla', 'tag': 'safe'},
            ],
            'swap': 'Cambia res magra por pollo deshebrado si lo prefieres.',
        },
        {
            'slot': 'Pre-gym', 'time': '18:00', 'xp': 8, 'tag': 'safe',
            'name': 'Plátano firme + tostadas de arroz',
            'kcal': 200, 'protein': 3,
            'note': 'Simple y efectivo. Sin crema hoy — el miércoles ya traías cacahuate en la colación 1.',
            'items': [
                {'t': '1 plátano firme (poco maduro)', 'tag': 'caution', 'why': 'Firme = menos fructanos.'},
                {'t': '2 tostadas de arroz', 'tag': 'safe'},
            ],
            'swap': 'Añade 1 cdta de crema de cacahuate si el entreno es intenso.',
        },
        {
            'slot': 'Cena', 'time': '20:30', 'xp': 12, 'tag': 'safe',
            'name': 'Toast de pollo y queso panela con blueberries',
            'kcal': 410, 'protein': 36,
            'note': 'Variación de tostadas horneadas. Ligera y rica en proteína.',
            'items': [
                {'t': '3 tostadas de maíz horneadas', 'tag': 'safe'},
                {'t': 'Cama de espinacas frescas', 'tag': 'safe'},
                {'t': '90 g de pechuga a las finas hierbas', 'tag': 'safe'},
                {'t': '40 g de queso panela', 'tag': 'safe'},
                {'t': 'Tomates cherry partidos', 'tag': 'safe'},
                {'t': '¾ taza de blueberries', 'tag': 'safe'},
            ],
            'swap': 'Cambia blueberries por fresas o moras.',
        },
    ],
    'J': [
        {
            'slot': 'Desayuno', 'time': '07:30', 'xp': 12, 'tag': 'safe',
            'name': 'Huevos revueltos con calabacita y cilantro',
            'kcal': 445, 'protein': 30,
            'note': 'Mismo base, diferente fruta que el martes.',
            'items': [
                {'t': '3 huevos revueltos con calabacita y cilantro fresco', 'tag': 'safe'},
                {'t': '2 cdtas de aceite para cocinar', 'tag': 'safe'},
                {'t': '40 g de queso panela', 'tag': 'safe'},
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '1 kiwi', 'tag': 'safe'},
            ],
            'swap': 'Rota fruta: kiwi ↔ mandarina ↔ papaya.',
        },
        {
            'slot': 'Colación 1', 'time': '10:30', 'xp': 8, 'tag': 'safe',
            'name': 'Mandarina + naranja + tostadas + jícama',
            'kcal': 175, 'protein': 3,
            'note': 'Jícama = fibra suave, baja en FODMAP.',
            'items': [
                {'t': '1 mandarina + 1 naranja', 'tag': 'safe'},
                {'t': '2 tostadas de arroz', 'tag': 'safe'},
                {'t': 'Jícama con limón', 'tag': 'safe'},
            ],
            'swap': 'Intercambia jícama por pepino o zanahoria.',
        },
        {
            'slot': 'Comida', 'time': '13:30', 'xp': 14, 'tag': 'safe',
            'name': 'Pollo en salsa verde con nopales y puré de papa',
            'kcal': 540, 'protein': 42,
            'note': 'Salsa de tomatillo sin chile. Los nopales son low risk y antiinflamatorios.',
            'items': [
                {'t': '½ taza de sopa de pasta con verduras', 'tag': 'safe'},
                {'t': '150 g de pechuga en salsa verde de tomatillo sin chile', 'tag': 'safe'},
                {'t': '2 tazas de nopales cocidos', 'tag': 'safe'},
                {'t': '½ taza de puré de papa (sin leche, con aceite infusionado)', 'tag': 'safe'},
            ],
            'swap': 'Cambia pasta por arroz blanco si prefieres.',
        },
        {
            'slot': 'Pre-gym', 'time': '18:00', 'xp': 8, 'tag': 'safe',
            'name': 'Papaya + tostadas con crema de cacahuate',
            'kcal': 230, 'protein': 5,
            'note': 'La papaya también contiene enzimas digestivas. Buen pre-gym.',
            'items': [
                {'t': '1 papaya chica (½ taza aprox.)', 'tag': 'safe'},
                {'t': '2 tostadas de arroz', 'tag': 'safe'},
                {'t': '1 cdta de crema de cacahuate sin azúcar', 'tag': 'safe'},
            ],
            'swap': 'Cambia papaya por kiwi o plátano firme.',
        },
        {
            'slot': 'Cena', 'time': '20:30', 'xp': 12, 'tag': 'safe',
            'name': 'Tacos de pollo con nopales y naranja',
            'kcal': 415, 'protein': 34,
            'note': 'Mismo esquema que el lunes. Post-gym ligero.',
            'items': [
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '120 g de pechuga a la plancha', 'tag': 'safe'},
                {'t': '2 nopales asados', 'tag': 'safe'},
                {'t': 'Cilantro fresco', 'tag': 'safe'},
                {'t': '1 naranja', 'tag': 'safe'},
            ],
            'swap': 'Cambia naranja por papaya o kiwi.',
        },
    ],
    'V': [
        {
            'slot': 'Desayuno', 'time': '07:30', 'xp': 12, 'tag': 'safe',
            'name': 'Huevos revueltos con espinacas y ejotes',
            'kcal': 450, 'protein': 30,
            'note': 'Cierra la semana con el desayuno del lunes. Ya lo dominas.',
            'items': [
                {'t': '3 huevos revueltos con espinacas y ejotes picados', 'tag': 'safe'},
                {'t': '2 cdtas de aceite para cocinar', 'tag': 'safe'},
                {'t': '40 g de queso panela', 'tag': 'safe'},
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '1 mandarina', 'tag': 'safe'},
            ],
            'swap': 'Rota fruta: mandarina ↔ kiwi ↔ papaya.',
        },
        {
            'slot': 'Colación 1', 'time': '10:30', 'xp': 8, 'tag': 'safe',
            'name': 'Mandarinas + tostadas + zanahoria',
            'kcal': 165, 'protein': 3,
            'note': 'Último día de la semana laboral. Mantén el ritmo.',
            'items': [
                {'t': '2 mandarinas', 'tag': 'safe'},
                {'t': '2 tostadas de arroz', 'tag': 'safe'},
                {'t': 'Bastones de zanahoria con limón', 'tag': 'safe'},
            ],
            'swap': 'Intercambia zanahoria por pepino o jícama.',
        },
        {
            'slot': 'Comida', 'time': '13:30', 'xp': 14, 'tag': 'safe',
            'name': 'Albóndigas de res en caldo con arroz',
            'kcal': 545, 'protein': 40,
            'note': 'Sin jitomate, sin cebolla. Caldo de hierbas + aceite infusionado.',
            'items': [
                {'t': '½ taza de arroz blanco o integral', 'tag': 'safe'},
                {'t': '150 g de albóndigas de res magra en caldo de hierbas', 'tag': 'safe'},
                {'t': 'Calabacita y zanahoria en el caldo', 'tag': 'safe'},
                {'t': '1 tortilla de maíz', 'tag': 'safe'},
                {'t': '2 cdtas de aceite infusionado', 'tag': 'safe'},
            ],
            'swap': 'Cambia res por pollo molido si lo prefieres.',
        },
        {
            'slot': 'Pre-gym', 'time': '18:00', 'xp': 8, 'tag': 'safe',
            'name': 'Plátano firme + tostadas con crema de cacahuate',
            'kcal': 240, 'protein': 5,
            'note': 'Viernes de gym. Mismo pre-gym del lunes: funciona, no cambies.',
            'items': [
                {'t': '1 plátano firme (poco maduro)', 'tag': 'caution', 'why': 'Firme = menos fructanos.'},
                {'t': '2 tostadas de arroz', 'tag': 'safe'},
                {'t': '1 cdta de crema de cacahuate sin azúcar', 'tag': 'safe'},
            ],
            'swap': 'Cambia plátano por kiwi o papaya chica.',
        },
        {
            'slot': 'Cena', 'time': '20:30', 'xp': 12, 'tag': 'safe',
            'name': 'Tostadas de nopal con pollo y naranja',
            'kcal': 410, 'protein': 33,
            'note': 'Cierra la semana ligero. Mañana puedes cocinar con calma.',
            'items': [
                {'t': '3 tostadas de maíz horneadas', 'tag': 'safe'},
                {'t': '120 g de pollo deshebrado', 'tag': 'safe'},
                {'t': 'Nopales guisados con aceite infusionado', 'tag': 'safe'},
                {'t': '1 naranja', 'tag': 'safe'},
            ],
            'swap': 'Añade salsa verde de tomatillo sin chile al gusto.',
        },
    ],
    'S': [
        {
            'slot': 'Desayuno', 'time': '07:30', 'xp': 12, 'tag': 'safe',
            'name': 'Huevos en salsa verde (sábado con calma)',
            'kcal': 455, 'protein': 31,
            'note': 'Sábado hay más tiempo. Salsa de tomatillo sin chile.',
            'items': [
                {'t': '3 huevos revueltos con calabacita rallada', 'tag': 'safe'},
                {'t': '2 cdtas de aceite para cocinar', 'tag': 'safe'},
                {'t': 'Salsa verde de tomatillo sin chile (bañar encima)', 'tag': 'safe'},
                {'t': '40 g de queso panela', 'tag': 'safe'},
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '1 kiwi', 'tag': 'safe'},
            ],
            'swap': 'Rota fruta: kiwi ↔ papaya ↔ mandarina.',
        },
        {
            'slot': 'Colación 1', 'time': '10:30', 'xp': 8, 'tag': 'safe',
            'name': 'Papaya + mandarina + tostadas con cacahuate',
            'kcal': 205, 'protein': 4,
            'note': 'Sábado hay tiempo para preparar la colación con calma.',
            'items': [
                {'t': '1 taza de papaya + 1 mandarina', 'tag': 'safe'},
                {'t': '2 tostadas de arroz con 1 cdta de crema de cacahuate', 'tag': 'safe'},
                {'t': 'Pepino con limón', 'tag': 'safe'},
            ],
            'swap': 'Intercambia pepino por jícama o zanahoria.',
        },
        {
            'slot': 'Comida', 'time': '13:30', 'xp': 14, 'tag': 'safe',
            'name': 'Picadillo con sopa de verduras',
            'kcal': 555, 'protein': 40,
            'note': 'Similar al miércoles. Aprovecha el batch del domingo pasado o cocina hoy.',
            'items': [
                {'t': 'Sopa de verduras con caldo de pollo y hierbas', 'tag': 'safe'},
                {'t': '150 g de picadillo de res con zanahoria, papa y hierbas', 'tag': 'safe'},
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '2 cdtas de aceite infusionado de ajo/cebolla', 'tag': 'safe'},
            ],
            'swap': 'Cambia res por pollo deshebrado si no hiciste batch.',
        },
        {
            'slot': 'Colación 2', 'time': '18:00', 'xp': 8, 'tag': 'safe',
            'name': 'Plátano + tostadas + zanahoria (pre-gym o tarde)',
            'kcal': 210, 'protein': 4,
            'note': 'Sábado puede no haber gym. Ajusta la cantidad si no entrenas.',
            'items': [
                {'t': '1 plátano firme', 'tag': 'caution', 'why': 'Firme = menos fructanos.'},
                {'t': '2 tostadas de arroz', 'tag': 'safe'},
                {'t': 'Bastones de zanahoria', 'tag': 'safe'},
            ],
            'swap': 'Si no entrenas, reduce a 1 tostada y omite el plátano.',
        },
        {
            'slot': 'Cena', 'time': '20:30', 'xp': 12, 'tag': 'safe',
            'name': 'Entomatadas de pollo en salsa verde',
            'kcal': 420, 'protein': 34,
            'note': 'Mismo esquema del martes. Sábado puedes hacerlo con más calma.',
            'items': [
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '120 g de pollo deshebrado', 'tag': 'safe'},
                {'t': '½ taza de calabacita en cubos', 'tag': 'safe'},
                {'t': 'Salsa verde de tomatillo sin chile', 'tag': 'safe'},
                {'t': '¾ taza de piña', 'tag': 'safe'},
            ],
            'swap': 'Cambia piña por papaya o mandarina.',
        },
    ],
    'D': [
        {
            'slot': 'Desayuno', 'time': '07:30', 'xp': 12, 'tag': 'safe',
            'name': 'Huevos divorciados (domingo con calma)',
            'kcal': 480, 'protein': 32,
            'note': 'El desayuno especial del domingo. Salsas SIN chile.',
            'items': [
                {'t': '3 huevos (estilo divorciados)', 'tag': 'safe'},
                {'t': 'Salsa verde de tomatillo SIN chile', 'tag': 'safe'},
                {'t': 'Salsa roja SIN chile (jitomate asado con cilantro)', 'tag': 'caution', 'why': 'Jitomate en salsa concentrada — apunta si te cae mal.'},
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '40 g de queso panela', 'tag': 'safe'},
                {'t': '2 tazas de verduras al gusto', 'tag': 'safe'},
                {'t': '1 taza de papaya', 'tag': 'safe'},
            ],
            'swap': 'Si el jitomate te cayó mal esta semana, usa solo salsa verde.',
        },
        {
            'slot': 'Colación 1', 'time': '10:30', 'xp': 8, 'tag': 'safe',
            'name': 'Kiwis + tostadas con cacahuate + jícama',
            'kcal': 210, 'protein': 5,
            'note': 'Aprovecha la mañana del domingo para el batch cooking.',
            'items': [
                {'t': '2 kiwis', 'tag': 'safe'},
                {'t': '2 tostadas de arroz con 1 cdta de crema de cacahuate', 'tag': 'safe'},
                {'t': 'Jícama con limón', 'tag': 'safe'},
            ],
            'swap': 'Intercambia kiwi por mandarina o papaya.',
        },
        {
            'slot': 'Comida', 'time': '13:30', 'xp': 14, 'tag': 'safe',
            'name': 'Tostadas de nopal con pollo (día de prep)',
            'kcal': 510, 'protein': 39,
            'note': 'Aprovecha que cocinas para hacer el batch de la semana.',
            'items': [
                {'t': '3 tostadas de maíz horneadas', 'tag': 'safe'},
                {'t': '150 g de pollo deshebrado', 'tag': 'safe'},
                {'t': 'Nopales guisados con aceite infusionado de ajo/cebolla', 'tag': 'safe'},
                {'t': 'Salsa verde de tomatillo (opcional)', 'tag': 'safe'},
                {'t': '2 cdtas de aceite de oliva', 'tag': 'safe'},
                {'t': '1 naranja', 'tag': 'safe'},
            ],
            'swap': 'Puedes añadir ½ taza de arroz blanco si tienes más hambre.',
        },
        {
            'slot': 'Colación 2', 'time': '17:00', 'xp': 8, 'tag': 'safe',
            'name': 'Mandarina + tostadas con cacahuate + pepino',
            'kcal': 190, 'protein': 4,
            'note': 'Colación 2 extra del domingo. Diferente horario — sin gym.',
            'items': [
                {'t': '1 mandarina', 'tag': 'safe'},
                {'t': '2 tostadas de arroz con 1 cdta de crema de cacahuate', 'tag': 'safe'},
                {'t': 'Pepino con limón', 'tag': 'safe'},
            ],
            'swap': 'Intercambia mandarina por kiwi o fresas.',
        },
        {
            'slot': 'Cena', 'time': '20:00', 'xp': 12, 'tag': 'safe',
            'name': 'Toast de espinaca con pollo y blueberries',
            'kcal': 415, 'protein': 37,
            'note': 'Cena temprana el domingo para entrar bien a la semana.',
            'items': [
                {'t': '3 tostadas de maíz horneadas', 'tag': 'safe'},
                {'t': 'Cama de espinacas frescas', 'tag': 'safe'},
                {'t': '90 g de pechuga a las finas hierbas', 'tag': 'safe'},
                {'t': '40 g de queso panela', 'tag': 'safe'},
                {'t': 'Tomates cherry partidos', 'tag': 'safe'},
                {'t': '1 cda de olivas verdes', 'tag': 'safe'},
                {'t': '¾ taza de blueberries', 'tag': 'safe'},
                {'t': '1 cdta de aceite de oliva', 'tag': 'safe'},
            ],
            'swap': 'Cambia blueberries por fresas o moras.',
        },
    ],
}

TEMPTATIONS_MAP = {
    'cafe':    {'label': 'Café de más',       'glyph': '☕', 'pen': 5},
    'pan':     {'label': 'Pan / harina',      'glyph': '🥖', 'pen': 12},
    'galleta': {'label': 'Galleta / dulce',   'glyph': '🍪', 'pen': 12},
    'lacteo':  {'label': 'Lácteo',            'glyph': '🥛', 'pen': 10},
    'frijol':  {'label': 'Frijol / legumbre', 'glyph': '🫘', 'pen': 8},
    'alcohol': {'label': 'Alcohol',           'glyph': '🍷', 'pen': 12},
    'otro':    {'label': 'Otro disparador',   'glyph': '⚑',  'pen': 8},
}

STOIC_SLIP = [
    'No te castigues; corrige. Mañana es otro asalto.',
    'El desliz registrado ya es virtud: has vuelto a mirar.',
    'No es la caída, sino la prontitud en levantarte.',
    'Ningún hombre es libre si no es dueño de sí mismo.',
    'Recomienza. Cada acto es una vida entera.',
]

# ── DB helpers ────────────────────────────────────────────────────────────────

def seed_week(db, week_str):
    for day_key, meals in PLAN_TEMPLATE.items():
        for m in meals:
            db.execute(
                """INSERT INTO nutricion_semana
                   (week_start,day_key,slot,time_str,name,kcal,protein,tag,note,items_json,swap,xp)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                [week_str, day_key, m['slot'], m['time'], m['name'],
                 m['kcal'], m['protein'], m['tag'], m.get('note', ''),
                 json.dumps(m.get('items', [])), m.get('swap', ''), m['xp']]
            )
    db.commit()


def get_or_seed_week(db, week_str):
    rows = db.execute(
        'SELECT * FROM nutricion_semana WHERE week_start=? ORDER BY id', [week_str]
    ).fetchall()
    if not rows:
        seed_week(db, week_str)
        rows = db.execute(
            'SELECT * FROM nutricion_semana WHERE week_start=? ORDER BY id', [week_str]
        ).fetchall()
    return rows


def rows_to_week(rows):
    week = {k: [] for k in ['L', 'M', 'X', 'J', 'V', 'S', 'D']}
    for r in rows:
        week[r['day_key']].append({
            'id': r['id'],
            'slot': r['slot'],
            'time': r['time_str'],
            'xp': r['xp'],
            'tag': r['tag'],
            'name': r['name'],
            'kcal': r['kcal'],
            'protein': r['protein'],
            'note': r['note'] or '',
            'items': json.loads(r['items_json'] or '[]'),
            'swap': r['swap'] or '',
            'custom': bool(r['custom']),
            'done': bool(r['done']),
            'symptom': r['symptom'],
            'sym_tags': json.loads(r['sym_tags_json'] or '[]'),
        })
    for k in week:
        week[k].sort(key=lambda m: m['time'])
    return week


def get_streak(db):
    row = db.execute(
        "SELECT value FROM app_settings WHERE key='nutricion_streak'"
    ).fetchone()
    return int(row['value']) if row else 0


def set_streak(db, val):
    db.execute(
        "INSERT OR REPLACE INTO app_settings(key,value) VALUES('nutricion_streak',?)", [str(val)]
    )


def get_xp_today(db):
    today = today_str()
    row = db.execute(
        "SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger WHERE source='nutricion' AND date=?", [today]
    ).fetchone()
    return int(row['s'])


def get_ec_today(db):
    today = today_str()
    row = db.execute(
        "SELECT COALESCE(SUM(amount),0) as s FROM coins_ledger WHERE source='nutricion' AND date=?", [today]
    ).fetchone()
    return int(row['s'])


def award_xp(db, amount, ref_id=None, desc=''):
    db.execute(
        "INSERT INTO xp_ledger(amount,source,reference_id,description,date,created_at) VALUES(?,?,?,?,?,datetime('now'))",
        [amount, 'nutricion', ref_id, desc, today_str()]
    )


def award_ec(db, amount, desc=''):
    db.execute(
        "INSERT INTO coins_ledger(amount,source,description,date,created_at) VALUES(?,?,?,?,datetime('now'))",
        [amount, 'nutricion', desc, today_str()]
    )


# ── Rutas ─────────────────────────────────────────────────────────────────────

@nutricion_bp.route('/')
def index():
    week_start = get_week_start()
    week_str = week_start.isoformat()
    today_key = get_today_key()
    today = today_str()

    with get_db() as db:
        rows = get_or_seed_week(db, week_str)
        week = rows_to_week(rows)

        slips = [dict(r) for r in db.execute(
            'SELECT * FROM nutricion_deslices WHERE date=? ORDER BY id', [today]
        ).fetchall()]

        bristol_row = db.execute(
            'SELECT valor FROM nutricion_bristol WHERE date=? ORDER BY id DESC LIMIT 1', [today]
        ).fetchone()

        xp_today = get_xp_today(db)
        ec_today = get_ec_today(db)
        streak = get_streak(db)

    state = {
        'week': week,
        'today': today_key,
        'week_start': week_str,
        'xp_today': xp_today,
        'ec_today': ec_today,
        'streak': streak,
        'slips': slips,
        'bristol': bristol_row['valor'] if bristol_row else None,
    }

    return render_template('nutricion/index.html', state=state)


@nutricion_bp.route('/api/cumplir', methods=['POST'])
def cumplir():
    data = request.get_json()
    meal_id = data['meal_id']

    with get_db() as db:
        meal = db.execute('SELECT * FROM nutricion_semana WHERE id=?', [meal_id]).fetchone()
        if not meal or meal['done']:
            return jsonify({'error': 'not found or already done'}), 400

        db.execute('UPDATE nutricion_semana SET done=1 WHERE id=?', [meal_id])
        award_xp(db, meal['xp'], ref_id=meal_id, desc=meal['slot'])

        week_str = get_week_start().isoformat()
        today_key = get_today_key()
        today = today_str()

        today_meals = db.execute(
            'SELECT * FROM nutricion_semana WHERE week_start=? AND day_key=?',
            [week_str, today_key]
        ).fetchall()

        all_done = all(m['done'] or m['id'] == meal_id for m in today_meals)
        slip_count = db.execute(
            'SELECT COUNT(*) as c FROM nutricion_deslices WHERE date=?', [today]
        ).fetchone()['c']

        bonus_xp = 0
        bonus_ec = 0
        new_streak = get_streak(db)

        if all_done and slip_count == 0:
            bonus_xp = 30
            bonus_ec = 8
            award_xp(db, 30, desc='día limpio bonus')
            award_ec(db, 8, desc='día cerrado')
            new_streak += 1
            set_streak(db, new_streak)

        db.commit()

        return jsonify({
            'xp_earned': meal['xp'],
            'bonus_xp': bonus_xp,
            'bonus_ec': bonus_ec,
            'total_xp': get_xp_today(db),
            'total_ec': get_ec_today(db),
            'streak': new_streak,
            'all_done': all_done and slip_count == 0,
        })


@nutricion_bp.route('/api/sintoma', methods=['POST'])
def sintoma():
    data = request.get_json()
    meal_id = data['meal_id']
    feeling = data['feeling']
    tags = data.get('tags', [])

    with get_db() as db:
        db.execute(
            'UPDATE nutricion_semana SET symptom=?, sym_tags_json=? WHERE id=?',
            [feeling, json.dumps(tags), meal_id]
        )
        award_xp(db, 5, ref_id=meal_id, desc='registro síntoma')
        db.commit()
        return jsonify({'xp_earned': 5, 'total_xp': get_xp_today(db)})


@nutricion_bp.route('/api/desliz', methods=['POST'])
def desliz():
    data = request.get_json()
    trig_id = data['trig_id']
    over = data.get('over', False)
    note = data.get('note', '')

    trig = TEMPTATIONS_MAP.get(trig_id, TEMPTATIONS_MAP['otro'])
    pen = round(trig['pen'] * (1.5 if over else 1))

    with get_db() as db:
        today = today_str()
        db.execute(
            'INSERT INTO nutricion_deslices(date,trig_id,label,glyph,pen,over,note) VALUES(?,?,?,?,?,?,?)',
            [today, trig_id, trig['label'], trig['glyph'], pen, 1 if over else 0, note]
        )
        award_xp(db, -pen, desc=f'desliz {trig["label"]}')
        set_streak(db, 0)
        db.commit()
        return jsonify({
            'pen': pen,
            'msg': random.choice(STOIC_SLIP),
            'total_xp': get_xp_today(db),
            'streak': 0,
            'slip': {
                'id': db.execute('SELECT last_insert_rowid() as i').fetchone()['i'],
                'label': trig['label'],
                'glyph': trig['glyph'],
                'pen': pen,
                'over': over,
                'note': note,
            }
        })


@nutricion_bp.route('/api/bristol', methods=['POST'])
def bristol():
    data = request.get_json()
    valor = data['valor']
    today = today_str()
    with get_db() as db:
        db.execute('DELETE FROM nutricion_bristol WHERE date=?', [today])
        db.execute('INSERT INTO nutricion_bristol(date,valor) VALUES(?,?)', [today, valor])
        db.commit()
    return jsonify({'ok': True})


@nutricion_bp.route('/api/comida', methods=['POST'])
def add_comida():
    data = request.get_json()
    week_str = get_week_start().isoformat()
    day_key = data.get('day', get_today_key())
    slot = data['slot']
    xp = 8 if 'Colación' in slot else 12

    with get_db() as db:
        db.execute(
            """INSERT INTO nutricion_semana
               (week_start,day_key,slot,time_str,name,kcal,protein,tag,note,items_json,swap,xp,custom)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1)""",
            [week_str, day_key, slot, data.get('time', '12:00'), data['name'],
             data.get('kcal', 0), data.get('protein', 0), data.get('tag', 'safe'),
             data.get('note', 'Comida personalizada.'),
             json.dumps(data.get('items', [])), data.get('swap', ''), xp]
        )
        db.commit()
        meal_id = db.execute('SELECT last_insert_rowid() as i').fetchone()['i']
        r = db.execute('SELECT * FROM nutricion_semana WHERE id=?', [meal_id]).fetchone()
        return jsonify({'meal': {
            'id': r['id'], 'slot': r['slot'], 'time': r['time_str'], 'xp': r['xp'],
            'tag': r['tag'], 'name': r['name'], 'kcal': r['kcal'], 'protein': r['protein'],
            'note': r['note'], 'items': json.loads(r['items_json'] or '[]'),
            'swap': r['swap'], 'custom': True, 'done': False, 'symptom': None, 'sym_tags': [],
        }})


@nutricion_bp.route('/api/comida/<int:meal_id>', methods=['DELETE'])
def delete_comida(meal_id):
    with get_db() as db:
        r = db.execute('SELECT name FROM nutricion_semana WHERE id=?', [meal_id]).fetchone()
        db.execute('DELETE FROM nutricion_semana WHERE id=?', [meal_id])
        db.commit()
    return jsonify({'ok': True, 'name': r['name'] if r else ''})


@nutricion_bp.route('/api/repetir', methods=['POST'])
def repetir():
    data = request.get_json()
    src_day = data['src_day']
    week_str = get_week_start().isoformat()
    today_key = get_today_key()

    with get_db() as db:
        src = db.execute(
            'SELECT * FROM nutricion_semana WHERE week_start=? AND day_key=?', [week_str, src_day]
        ).fetchall()

        for dk in ['L', 'M', 'X', 'J', 'V']:
            if dk == today_key:
                continue
            db.execute(
                'DELETE FROM nutricion_semana WHERE week_start=? AND day_key=?', [week_str, dk]
            )
            for m in src:
                db.execute(
                    """INSERT INTO nutricion_semana
                       (week_start,day_key,slot,time_str,name,kcal,protein,tag,note,items_json,swap,xp,custom)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    [week_str, dk, m['slot'], m['time_str'], m['name'],
                     m['kcal'], m['protein'], m['tag'], m['note'],
                     m['items_json'], m['swap'], m['xp'], m['custom']]
                )
        db.commit()

        rows = db.execute(
            'SELECT * FROM nutricion_semana WHERE week_start=? ORDER BY id', [week_str]
        ).fetchall()
        return jsonify({'week': rows_to_week(rows)})
