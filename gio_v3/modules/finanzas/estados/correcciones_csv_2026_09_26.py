"""
Correcciones del CSV «transacciones_CORREGIDO» (2026-09-26): el usuario
exportó sus movimientos, les puso un COMENTARIO a 148 y pidió aplicarlos.
Cada fila se identifica por id + fecha + monto (así una fila equivocada
nunca se toca aunque el id se reutilizara) y lleva solo los campos que
cambian. Interpretación de los comentarios:
  - «ME REGRESARON DINERO DE EXPENSE» (FIDEICOMISO F 1596) -> FINANZAS/Reembolsable
  - «SAQUE DINERO DE CETES» (SPEI RECIBIDO NAFIN) -> INVERSION CETES/RETIRO
  - «METI DINERO A INVERTIR EN GBM» -> INVERSION GBM/APORTACION
  - un número -> mi_parte (renta 11-13k con tu parte 6000/7000, cuentas
    divididas, Airbnbs)
  - «PARTE (DE) RENTA (DE) ROOMIE» -> VIVIENDA/Aportación renta
  - «ME REGRESO RENTA PARA QUE PAGARA EN OTRA CUENTA» -> FINANZAS/Transferencia recibida
  - préstamo de/a Pops -> PRESTAMOS (se cancelan)
  - «CLAUDE IA» / «SERVICIO AMAZON» (ajustes de tipo de cambio) -> DIGITAL
  - «REEMBOLSO TEMU» -> VIVIENDA/Artículos del hogar (resta al gasto)
  - «ESTE PAGO NO PROCEDIO» / «RETENIDO PERO NO COBRADO EN GARANTIA» ->
    FINANZAS/Reembolsable (fuera de gasto e ingreso)
Sin aplicar (se preguntó): id 302 VIVA AEROBUS A 09 MSI (2), comentario «1».
"""

CORRECCIONES = [
    (3650, '2023-01-03', 215.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000004451 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (3915, '2023-01-12', 7065.16, {'categoria': 'CETES', 'subcategoria': 'RETIRO', 'tipo': 'INVERSION'}),  # SPEI RECIBIDONAFIN · «SAQUE DINERO DE CETES»
    (3921, '2023-01-17', 4000.0, {'categoria': 'CETES', 'subcategoria': 'RETIRO', 'tipo': 'INVERSION'}),  # SPEI RECIBIDONAFIN · «SAQUE DINERO DE CETES»
    (3934, '2023-02-01', 6942.23, {'categoria': 'CETES', 'subcategoria': 'RETIRO', 'tipo': 'INVERSION'}),  # SPEI RECIBIDONAFIN · «SAQUE DINERO DE CETES»
    (3936, '2023-02-02', 4000.0, {'categoria': 'CETES', 'subcategoria': 'RETIRO', 'tipo': 'INVERSION'}),  # SPEI RECIBIDONAFIN · «SAQUE DINERO DE CETES»
    (3896, '2023-02-17', 4000.0, {'categoria': 'CETES', 'subcategoria': 'RETIRO', 'tipo': 'INVERSION'}),  # SPEI RECIBIDONAFIN · «SAQUE DINERO DE CETES»
    (3782, '2023-06-16', 10500.0, {'categoria': 'CETES', 'subcategoria': 'RETIRO', 'tipo': 'INVERSION'}),  # SPEI RECIBIDONAFIN · «SAQUE DINERO DE CETES»
    (3756, '2023-07-14', 2700.0, {'categoria': 'CETES', 'subcategoria': 'RETIRO', 'tipo': 'INVERSION'}),  # SPEI RECIBIDONAFIN · «SAQUE DINERO DE CETES»
    (3720, '2023-09-11', 15000.0, {'categoria': 'CETES', 'subcategoria': 'RETIRO', 'tipo': 'INVERSION'}),  # SPEI RECIBIDONAFIN · «SAQUE DINERO DE CETES»
    (28, '2023-09-28', 5560.4, {'mi_parte': 1390.1}),  # HOTEL STADIA SUITE QRO · «1390.1»
    (3746, '2023-10-06', 15000.0, {'categoria': 'CETES', 'subcategoria': 'RETIRO', 'tipo': 'INVERSION'}),  # SPEI RECIBIDONAFIN · «SAQUE DINERO DE CETES»
    (3704, '2023-10-30', 22827.58, {'categoria': 'CETES', 'subcategoria': 'RETIRO', 'tipo': 'INVERSION'}),  # SPEI RECIBIDONAFIN · «SAQUE DINERO DE CETES»
    (3660, '2023-11-07', 4000.0, {'categoria': 'CETES', 'subcategoria': 'RETIRO', 'tipo': 'INVERSION'}),  # SPEI RECIBIDONAFIN · «SAQUE DINERO DE CETES»
    (3663, '2023-11-09', 10000.0, {'categoria': 'CETES', 'subcategoria': 'RETIRO', 'tipo': 'INVERSION'}),  # SPEI RECIBIDONAFIN · «SAQUE DINERO DE CETES»
    (3318, '2023-12-13', 9500.0, {'categoria': 'CETES', 'subcategoria': 'RETIRO', 'tipo': 'INVERSION'}),  # SPEI RECIBIDONAFIN · «SAQUE DINERO DE CETES»
    (3343, '2024-01-03', 2076.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000000433 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (3353, '2024-01-08', 5070.71, {'categoria': 'CETES', 'subcategoria': 'RETIRO', 'tipo': 'INVERSION'}),  # SPEI RECIBIDONAFIN · «SAQUE DINERO DE CETES»
    (3363, '2024-01-18', 4000.0, {'categoria': 'CETES', 'subcategoria': 'RETIRO', 'tipo': 'INVERSION'}),  # SPEI RECIBIDONAFIN · «SAQUE DINERO DE CETES»
    (3371, '2024-02-01', 818.57, {'categoria': 'CETES', 'subcategoria': 'RETIRO', 'tipo': 'INVERSION'}),  # SPEI RECIBIDONAFIN · «SAQUE DINERO DE CETES»
    (3375, '2024-02-02', 4000.0, {'categoria': 'CETES', 'subcategoria': 'RETIRO', 'tipo': 'INVERSION'}),  # SPEI RECIBIDONAFIN · «SAQUE DINERO DE CETES»
    (3409, '2024-04-11', 3000.0, {'categoria': 'CETES', 'subcategoria': 'RETIRO', 'tipo': 'INVERSION'}),  # SPEI RECIBIDONAFIN · «SAQUE DINERO DE CETES»
    (3437, '2024-05-09', 15000.0, {'categoria': 'CETES', 'subcategoria': 'RETIRO', 'tipo': 'INVERSION'}),  # SPEI RECIBIDONAFIN · «SAQUE DINERO DE CETES»
    (3446, '2024-05-14', 2944.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000000864 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (3453, '2024-05-24', 5000.0, {'categoria': 'CETES', 'subcategoria': 'RETIRO', 'tipo': 'INVERSION'}),  # SPEI RECIBIDONAFIN · «SAQUE DINERO DE CETES»
    (3458, '2024-05-28', 4640.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH2EXPENSEANIVERSARIO FIDEICOMISO F 15 · «ME REGRESARON DINERO DE EXPENSE»
    (3469, '2024-06-04', 2414.94, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000000932 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (3483, '2024-06-11', 13000.0, {'categoria': 'CETES', 'subcategoria': 'RETIRO', 'tipo': 'INVERSION'}),  # SPEI RECIBIDONAFIN · «SAQUE DINERO DE CETES»
    (3484, '2024-06-11', 1000.0, {'categoria': 'CETES', 'subcategoria': 'RETIRO', 'tipo': 'INVERSION'}),  # SPEI RECIBIDONAFIN · «SAQUE DINERO DE CETES»
    (3508, '2024-07-02', 1561.68, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000001026 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (3517, '2024-07-08', 4000.0, {'categoria': 'CETES', 'subcategoria': 'RETIRO', 'tipo': 'INVERSION'}),  # SPEI RECIBIDONAFIN · «SAQUE DINERO DE CETES»
    (3524, '2024-07-12', 8400.0, {'categoria': 'CETES', 'subcategoria': 'RETIRO', 'tipo': 'INVERSION'}),  # SPEI RECIBIDONAFIN · «SAQUE DINERO DE CETES»
    (3533, '2024-07-16', 542.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000001056 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (3564, '2024-08-12', 12000.0, {'categoria': 'CETES', 'subcategoria': 'RETIRO', 'tipo': 'INVERSION'}),  # SPEI RECIBIDONAFIN · «SAQUE DINERO DE CETES»
    (3569, '2024-08-13', 1815.63, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000001131 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (536, '2024-08-23', 4176.24, {'mi_parte': 1044.06}),  # HTL COURT BY MARRIOTT · «1044.06»
    (3606, '2024-08-30', 738.7, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000001188 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (3106, '2024-09-09', 518.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000001221 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (3107, '2024-09-09', 11000.0, {'mi_parte': 6000.0}),  # PAGO TARJETA DE TERCEROS · «6000»
    (3111, '2024-09-11', 13000.0, {'categoria': 'PRESTAMOS', 'subcategoria': ''}),  # PAGO CUENTA DE TERCERO BNET TRANSF A GIO · «ME PRESTO DINERO POPS»
    (3114, '2024-09-12', 13000.0, {'categoria': 'PRESTAMOS', 'subcategoria': ''}),  # PAGO CUENTA DE TERCERO BNET DEUDA · «PAGUE PRESTAMO A POPS»
    (3117, '2024-09-13', 512.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000001239 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (3147, '2024-09-30', 6000.0, {'categoria': 'VIVIENDA', 'subcategoria': 'Aportación renta', 'tipo': 'INGRESO'}),  # SPEI RECIBIDOSANTANDER · «PARTE DE RENTA DE ROOMIE»
    (3152, '2024-10-04', 527.5, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000001300 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (3061, '2024-10-08', 11000.0, {'categoria': 'FINANZAS', 'subcategoria': 'Transferencia recibida'}),  # SPEI RECIBIDOBANORTE · «ME REGRESO RENTA PARA QUE PAGARA EN OTRA CUENTA»
    (3163, '2024-10-08', 11000.0, {'mi_parte': 6000.0}),  # PAGO TARJETA DE TERCEROS · «6000»
    (3066, '2024-10-11', 738.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000001317 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (3076, '2024-10-18', 372.5, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000001356 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (3093, '2024-11-01', 2215.6, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000001380 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (3094, '2024-11-01', 6000.0, {'categoria': 'VIVIENDA', 'subcategoria': 'Aportación renta', 'tipo': 'INGRESO'}),  # SPEI RECIBIDOSANTANDER · «PARTE DE RENTA DE ROOMIE»
    (2589, '2024-11-12', 11000.0, {'mi_parte': 6000.0}),  # PAGO TARJETA DE TERCEROS · «6000»
    (2593, '2024-11-15', 4365.55, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000001417 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (2601, '2024-11-29', 477.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000001465 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (2607, '2024-12-02', 6000.0, {'categoria': 'VIVIENDA', 'subcategoria': 'Aportación renta', 'tipo': 'INGRESO'}),  # SPEI RECIBIDOSANTANDER · «PARTE DE RENTA DE ROOMIE»
    (2611, '2024-12-03', 11000.0, {'mi_parte': 6000.0}),  # PAGO TARJETA DE TERCEROS · «6000»
    (2613, '2024-12-06', 6138.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000001490 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (2697, '2024-12-20', 715.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000001541 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (2639, '2025-01-03', 6000.0, {'categoria': 'VIVIENDA', 'subcategoria': 'Aportación renta', 'tipo': 'INGRESO'}),  # SPEI RECIBIDOSANTANDER · «PARTE DE RENTA DE ROOMIE»
    (743, '2025-01-05', 1323.0, {'mi_parte': 264.6}),  # LA PARROQUIA DE VERACR · «264.6»
    (746, '2025-01-07', 2187.2, {'mi_parte': 729.06}),  # AIRBNB HMSEAJRBBK · «729.06»
    (2654, '2025-01-09', 11000.0, {'mi_parte': 6000.0}),  # PAGO TARJETA DE TERCEROS · «6000»
    (2657, '2025-01-10', 3500.9, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000001583 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (2665, '2025-01-22', 642.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000001608 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (2669, '2025-01-30', 6000.0, {'categoria': 'VIVIENDA', 'subcategoria': 'Aportación renta', 'tipo': 'INGRESO'}),  # SPEI RECIBIDOSANTANDER · «PARTE DE RENTA DE ROOMIE»
    (3015, '2025-02-07', 11000.0, {'mi_parte': 6000.0}),  # PAGO TARJETA DE TERCEROS · «6000»
    (3029, '2025-02-26', 445.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000001702 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (3031, '2025-02-27', 7158.0, {'categoria': 'VIVIENDA', 'subcategoria': 'Aportación renta', 'tipo': 'INGRESO'}),  # SPEI RECIBIDOSANTANDER · «PARTE DE RENTA DE ROOMIE»
    (2984, '2025-03-07', 11000.0, {'mi_parte': 6000.0}),  # PAGO TARJETA DE TERCEROS · «6000»
    (2989, '2025-03-12', 1239.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000001774 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (3006, '2025-03-28', 6500.0, {'categoria': 'VIVIENDA', 'subcategoria': 'Aportación renta', 'tipo': 'INGRESO'}),  # SPEI RECIBIDOSANTANDER · «PARTE DE RENTA DE ROOMIE»
    (886, '2025-03-29', 8748.78, {'mi_parte': 2916.3}),  # AIRBNB HMSEAJRBBK · «2916.3»
    (896, '2025-04-01', 3309.9, {'mi_parte': 1103.3}),  # AIRBNB HMEMWDDDET · «1103.3»
    (2942, '2025-04-07', 11000.0, {'mi_parte': 6000.0}),  # PAGO TARJETA DE TERCEROS · «6000»
    (2946, '2025-04-09', 441.3, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000001908 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (916, '2025-04-11', 4048.0, {'mi_parte': 1349.33}),  # LA CHURRASCA PREMIUM · «1349.33»
    (2949, '2025-04-11', 500.0, {'mi_parte': 100.0}),  # SPEI ENVIADO ARCUS FI · «100»
    (922, '2025-04-15', 2310.0, {'mi_parte': 770.0}),  # AFRICAM · «770»
    (929, '2025-04-16', 1058.2, {'mi_parte': 352.73}),  # REST ANGELOPOLIS 2 · «352.73»
    (2966, '2025-04-23', 480.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000001969 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (2972, '2025-04-30', 6500.0, {'categoria': 'VIVIENDA', 'subcategoria': 'Aportación renta', 'tipo': 'INGRESO'}),  # SPEI RECIBIDOSANTANDER · «PARTE DE RENTA DE ROOMIE»
    (2973, '2025-04-30', 4828.01, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000002002 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (2906, '2025-05-07', 11000.0, {'mi_parte': 6000.0}),  # PAGO TARJETA DE TERCEROS · «6000»
    (2938, '2025-06-04', 442.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000002102 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (2866, '2025-06-09', 11000.0, {'mi_parte': 6000.0}),  # PAGO TARJETA DE TERCEROS · «6000»
    (2873, '2025-06-11', 124.9, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000002123 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (1085, '2025-06-27', 3949.44, {'mi_parte': 394.94}),  # REST CENTRO · «394.94»
    (2897, '2025-07-02', 1805.2, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000002194 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (1102, '2025-07-06', -8910.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SHERATON MEXICO C CONCLUIDA, 8054954410 · «RETENIDO PERO NO COBRADO EN GARANTIA»
    (2830, '2025-07-08', 11000.0, {'mi_parte': 6000.0}),  # PAGO TARJETA DE TERCEROS · «6000»
    (1113, '2025-07-10', 920.0, {'mi_parte': 400.0}),  # REST BABALU · «400»
    (2847, '2025-07-23', 735.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000002245 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (2797, '2025-08-08', 11000.0, {'mi_parte': 6000.0}),  # PAGO TARJETA DE TERCEROS · «6000»
    (1190, '2025-08-15', -1.69, {'categoria': 'DIGITAL', 'subcategoria': 'Suscripciones IA/productividad', 'tipo': 'GASTO'}),  # AJUSTE TIPO CAMBIO CODE TRIAL PRO MON · «CLAUDE IA»
    (2818, '2025-09-03', 4913.61, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000002406 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (2769, '2025-09-08', 11000.0, {'mi_parte': 6000.0}),  # PAGO TARJETA DE TERCEROS · «6000»
    (2773, '2025-09-10', 835.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # DEPOSITO DE TERCERO FIDEICOMISO F 1596 B · «ME REGRESARON DINERO DE EXPENSE»
    (2791, '2025-10-01', 2788.71, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000002498 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (2740, '2025-10-08', 12000.0, {'mi_parte': 6000.0}),  # PAGO TARJETA DE TERCEROS · «6000»
    (2754, '2025-10-22', 389.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000002569 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (1408, '2025-11-10', 13000.0, {'mi_parte': 7000.0}),  # PAGO TARJETA DE TERCEROS · «7000»
    (1411, '2025-11-11', -2345.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # ELPALACIOHIERRO COM · «ESTE PAGO NO PROCEDIO»
    (1418, '2025-11-13', -2345.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # ELPALACIOHIERRO COM · «ESTE PAGO NO PROCEDIO»
    (1435, '2025-11-19', 1823.07, {'mi_parte': 400.0}),  # AIRBNB HM5JWB2R2P · «400»
    (1470, '2025-11-26', 4759.25, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000002685 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (1501, '2025-12-08', 12000.0, {'mi_parte': 6000.0}),  # PAGO TARJETA DE TERCEROS · «6000»
    (1513, '2025-12-11', 1265.55, {'mi_parte': 316.3}),  # BOSTONS PIZZA · «316.3»
    (1519, '2025-12-11', 920.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000002731 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (1530, '2025-12-14', 7292.25, {'mi_parte': 2430.6}),  # AIRBNB HM5JWB2R2P · «2430.6»
    (1545, '2025-12-19', 4740.0, {'mi_parte': 1580.0}),  # MERCADOPAGO BOLETOMO GUADALAJARA_ JAL · «1580»
    (1569, '2025-12-23', 779.9, {'mi_parte': 155.98}),  # KARNITAS LA TERRAZA · «155.98»
    (1573, '2025-12-24', 945.0, {'mi_parte': 189.0}),  # CLUB DEP GOLF BLACK G · «189»
    (1575, '2025-12-24', 937.2, {'mi_parte': 187.4}),  # MERPAGO TIENDACHARLY · «187.4»
    (1587, '2025-12-27', 1958.0, {'mi_parte': 400.0}),  # PIZZERIA PINOCHO · «400»
    (1588, '2025-12-27', 1553.2, {'mi_parte': 517.73}),  # REST BDM PVR · «517.73»
    (1589, '2025-12-28', 996.6, {'mi_parte': 193.2}),  # REST LOS TARASCOS · «193.2»
    (1602, '2026-01-01', 1421.0, {'mi_parte': 399.97}),  # LA PARROQUIA DE VERACR · «399.97»
    (1625, '2026-01-07', 4479.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH20000002821 FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (1626, '2026-01-08', 12000.0, {'mi_parte': 6000.0}),  # PAGO TARJETA DE TERCEROS · «6000»
    (1723, '2026-02-09', 12000.0, {'mi_parte': 6000.0}),  # PAGO TARJETA DE TERCEROS · «6000»
    (1726, '2026-02-10', 454.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH2PAGOGDLAC FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (1774, '2026-02-23', -120.57, {'categoria': 'VIVIENDA', 'subcategoria': 'Artículos del hogar', 'tipo': 'GASTO'}),  # TEMU.COM · «REEMBOLSO TEMU»
    (1838, '2026-03-09', 12000.0, {'mi_parte': 6000.0}),  # BNET 8B PAGO TARJETA DE TERCEROS · «6000»
    (1872, '2026-03-15', 1133.0, {'mi_parte': 300.0}),  # REST LA TIENDITA VNV · «300»
    (1958, '2026-04-08', 12000.0, {'mi_parte': 6000.0}),  # 766236 PAGO TARJETA DE TERCEROS · «6000»
    (2006, '2026-04-23', 3142.39, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # GIOVANY SITH2PAGOGDLAC FIDEICOMISO F 159 · «ME REGRESARON DINERO DE EXPENSE»
    (2057, '2026-05-06', 690.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (2066, '2026-05-08', 12000.0, {'mi_parte': 6000.0}),  # PAGO TARJETA DE TERCEROS MBAN · «6000»
    (2104, '2026-05-20', 10143.5, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH2PAGOGDLAC FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (2142, '2026-06-08', 12000.0, {'mi_parte': 6000.0}),  # PAGO TARJETA DE TERCEROS MBAN · «6000»
    (2232, '2026-06-18', 709.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH26924487 / 418249678465540 FIDEICOMI · «ME REGRESARON DINERO DE EXPENSE»
    (2247, '2026-06-18', 709.0, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (2293, '2026-06-19', -0.88, {'categoria': 'DIGITAL', 'subcategoria': 'Suscripciones IA/productividad', 'tipo': 'GASTO'}),  # AJUSTE TIPO CAMBIO ANTHROPIC CLAUDE SU · «CLAUDE IA»
    (2311, '2026-07-08', 12000.0, {'mi_parte': 6000.0}),  # PAGO TARJETA DE TERCEROS MBAN · «6000»
    (2374, '2026-07-20', 15000.0, {'categoria': 'GBM', 'subcategoria': 'APORTACION', 'tipo': 'INVERSION'}),  # SPEI ENVIADO GBM · «METI DINERO A INVERTIR EN GBM»
    (2371, '2026-07-22', 7163.62, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (2379, '2026-07-22', 7163.62, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH27049535 / 441169685063080 FIDEICOMI · «ME REGRESARON DINERO DE EXPENSE»
    (2488, '2026-08-02', 1593.0, {'mi_parte': 301.0}),  # REST LA PARROQUIA DE V · «301»
    (2384, '2026-08-03', 25000.0, {'categoria': 'GBM', 'subcategoria': 'APORTACION', 'tipo': 'INVERSION'}),  # SPEI ENVIADO GBM 601 2206260INVERSION · «METI DINERO A INVERTIR EN GBM»
    (2433, '2026-08-07', 12000.0, {'mi_parte': 6000.0}),  # PAGO TARJETA DE TERCEROS MBAN · «6000»
    (2495, '2026-08-07', 2500.0, {'categoria': 'VIVIENDA', 'subcategoria': 'Aportación renta', 'tipo': 'INGRESO'}),  # SPEI RECIBIDONUBANK 638 0070826TRANSFERE · «PARTE RENTA ROOMIE»
    (2442, '2026-08-12', 3799.4, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH27126324 / 455274138436900 FIDEICOMI · «ME REGRESARON DINERO DE EXPENSE»
    (2494, '2026-08-12', 3799.4, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (2422, '2026-08-14', 1000.0, {'categoria': 'VIVIENDA', 'subcategoria': 'Aportación renta', 'tipo': 'INGRESO'}),  # SPEI RECIBIDONUBANK 638 0140826TRANSFERE · «PARTE RENTA ROOMIE»
    (2523, '2026-08-18', 986.5, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # SITH27151900 / 459166576549320 FIDEICOMI · «ME REGRESARON DINERO DE EXPENSE»
    (2529, '2026-08-18', 986.5, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
    (2564, '2026-08-19', -2.09, {'categoria': 'DIGITAL', 'subcategoria': 'Suscripciones entretenimiento', 'tipo': 'GASTO'}),  # AJUSTE TIPO CAMBIO ANTHROPIC CLAUDE SU · «SERVICIO AMAZON»
    (2577, '2026-09-07', 12000.0, {'mi_parte': 6000.0}),  # PAGO TARJETA DE TERCEROS MBAN · «6000»
    (2570, '2026-09-11', 1200.0, {'categoria': 'VIVIENDA', 'subcategoria': 'Aportación renta', 'tipo': 'INGRESO'}),  # SPEI RECIBIDONUBANK 638 0110926TRANSFERE · «PARTE RENTA ROOMIE»
    (2580, '2026-09-15', 4174.94, {'categoria': 'FINANZAS', 'subcategoria': 'Reembolsable'}),  # FIDEICOMISO F 1596 · «ME REGRESARON DINERO DE EXPENSE»
]
_CAMPOS = ('categoria', 'subcategoria', 'tipo', 'mi_parte')


def aplicar(db) -> tuple[int, int]:
    """Aplica las correcciones; devuelve (actualizadas, no encontradas).
    Idempotente: una fila que ya tiene esos valores no cuenta."""
    ok = faltan = 0
    for mid, fecha, monto, cambios in CORRECCIONES:
        row = db.execute(
            "SELECT * FROM est_movimientos WHERE id=? AND substr(fecha, 1, 10)=? AND ABS(ABS(monto) - ?) < 0.01",
            (mid, fecha, abs(monto)),
        ).fetchone()
        if not row:
            faltan += 1
            continue
        cols = [c for c in _CAMPOS if c in cambios and row[c] != cambios[c]]
        if not cols:
            continue
        db.execute(f"UPDATE est_movimientos SET {', '.join(f'{c}=?' for c in cols)} WHERE id=?",
                   (*[cambios[c] for c in cols], mid))
        ok += 1
    return ok, faltan
