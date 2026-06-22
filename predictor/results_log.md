# Registro de resultados — Predicción vs Realidad (Mundial 2026)

Bitácora para medir la **calibración** del modelo a lo largo del torneo. La idea
no es contar "aciertos" (el favorito gana seguido y tiene poco mérito), sino ver
si los **xG y las probabilidades** estuvieron bien puestos, y separar lo
acertado por buenas razones de lo que fue varianza.

Leyenda: ✅ acertado por la razón correcta · 🟡 acertado pero por azar/margen ·
❌ fallado · ⏳ resultado pendiente.

---

## Resumen 1X2

| Fecha | Partido | Modelo (L/X/V) | Confianza | Resultado real | 1X2 |
|---|---|---|---|---|---|
| 2026-06-20 | Ecuador vs Curaçao | 79.0 / 15.8 / 5.1 | ALTA | 0-0 (empate) | 🟡 |
| 2026-06-21 | Túnez vs Japón | 14.7 / 21.7 / 63.6 | ALTA | 0-4 (gana Japón) | ✅ |
| 2026-06-21 | España vs Arabia | 82.0 / 13.4 / 4.7 | ALTA | 4-0 (gana España) | ✅ |
| 2026-06-21 | Egipto vs N. Zelanda | 58.2 / 24.4 / 17.4 | MEDIA | ⏳ por jugarse | ⏳ |
| 2026-06-21 | Bélgica vs Irán | 67.9 / 21.9 / 10.2 | ALTA | 0-0 (empate) | 🟡 |
| 2026-06-21 | Uruguay vs Cabo Verde | 63.4 / 24.6 / 12.0 | ALTA | 2-2 (empate) | 🟡 |

### Patrón emergente: favoritos vs bloque bajo (clave)

En estas fechas hubo TRES 0-0 de favoritos frustrados por bloques bajos:
Ecuador-Curaçao (J1), Cabo Verde-España (J1) y Bélgica-Irán (J2). Pero también
dos goleadas (España 4-0, Japón 4-0). **Conclusión honesta:** "favorito rompe al
bloque" tiene varianza enorme y NI mi bottom-up NI seguir al mercado acierta
consistentemente. Mi bottom-up subestima al favorito ~8-9pts (lo corrijo al
mercado), pero el empate (~22-25%) se materializa seguido. La lectura correcta no
es "¿gana el favorito?" sino "el empate/Under vale más de lo que parece cuando
el rival es un bloque bajo PROBADO". No sobre-actualizar con n pequeño.

**Nota Bélgica-Irán 0-0:** el 1X2 no acertó (favorito al 68% no ganó; el empate
21.9% entró), PERO los reads de valor SÍ: con Irán en 5-4-1 marqué BTTS No (61%),
Under 3.5 (76%) y "pocos goles" — todos ganaron. Acierto de proceso en los
mercados de goles aunque el favorito no rompiera el cero.

**Nota Uruguay-Cabo Verde 2-2 (refinamiento CLAVE del patrón):** Cabo Verde
frustró a OTRO favorito (3er punto del debutante), confirmando el patrón. PERO
fue 2-2, no 0-0 — y eso obliga a refinar dos cosas:
1. "Bloque bajo" ≠ "inofensivo": subestimé el ataque de Cabo Verde (λ 0.60;
   marcaron 2, incluido un golazo). Cuando el partido se abre y el favorito se
   estira, el bloque SÍ genera y convierte. Su xG-for no es fijo ~0.
2. El vehículo correcto de la tesis "favorito frustrado" es el EMPATE / doble
   oportunidad, NO el Under/BTTS-No. Acá recomendé Under 2.5 (60%) y BTTS No
   (62%) y AMBOS perdieron (2-2 = Over + BTTS Sí); el empate, en cambio, entró.
   Lección: expresar "favorito no rompe al bloque" vía RESULTADO, no vía goles.

## Calibración de xG (lo que de verdad importa)

| Partido | Equipo | λ modelo | xG real | Veredicto |
|---|---|---|---|---|
| Túnez vs Japón | Japón | 2.00 | 2.07 | ✅ casi exacto |
| Túnez vs Japón | Túnez | 0.855 | 0.05 | ❌ sobreestimado (Túnez fue nulo) |
| España vs Arabia | España | 2.60 | 4 goles, 21 remates | ❌ subestimada (mi lean anti-mercado falló) |

---

## 2026-06-21 · España 4-0 Arabia Saudita (Grupo H, Fecha 2)

**Predicción del modelo:** España 82.0% / Empate 13.4% / Arabia 4.7%. Me puse
DELIBERADAMENTE ~4-7 pts por DEBAJO del mercado (86.4%), con tesis de "España
roma sin 9, viene de 0-0 con Cabo Verde, valor en el empate".

**Resultado real:** España 4-0, con 21 remates. España salió a arrasar (3-0 a
los 27'). **Mi lean contrarian FALLÓ de lleno: el mercado tenía razón y yo no.**

**Lectura honesta:**
- ✅ 1X2: ganó el favorito (poco mérito, era el escenario fácil).
- ❌ Mi sesgo "España no golea / valor en el empate" se comió una goleada. El
  0-0 con Cabo Verde no era la norma, era el outlier; sobre-corregí por él.
- 📌 Lección simétrica a Túnez-Japón: allá el mercado y yo coincidíamos y salió
  bien; acá me separé del consenso y el consenso ganó. Separarse del mercado
  es donde está el valor PERO también donde más se paga estar equivocado.
- 💸 Apuesta del usuario (combi 6 patas, cuota 10.0, €30): cerró (cash out) en
  **€214.29** (ganancia +€184). Aguantó más allá del cash out EV-óptimo del
  descanso (~€80) y la varianza lo premió; de-riskeó bien cerrando a 85' con
  4-0 (cierre justo-a-generoso). Buen RESULTADO; el proceso fue +varianza, no
  +EV — un buen final no valida retroactivamente el camino más riesgoso.

---

## 2026-06-21 · Túnez 0-4 Japón (Grupo F, partido N.°1000)

**Predicción del modelo:** Japón 63.6% / Empate 21.7% / Túnez 14.7% (alineado con
el mercado, divergencia ~2 pts). Confianza ALTA. Sugerido: gana Japón, marcador
0-2. xG: Japón 2.00, Túnez 0.855.

**Resultado real:** Túnez 0-4 Japón. Goles: Kamada 4', Ueda 31' y 83', Ito 69'.
**Stats reales:** posesión 36-55; remates 2 (0 al arco) vs 10 (4 al arco);
**xG 0.05 vs 2.07**; Japón >5 córners; Túnez eliminado.

**Lectura honesta:**
- ✅ **Japón gana / valla invicta / dominio de córners:** lectura estructural
  correcta. Mi λ de Japón (2.00) clavó el xG real (2.07): las chances creadas
  fueron exactamente las modeladas.
- ✅ **Túnez no marca:** acertado, y de hecho **más seguro** de lo que decía el
  modelo. Túnez generó 0.05 de xG (2 remates, 0 al arco): fue aún más inofensivo
  que lo que yo (y el mercado) supusimos.
- ❌ **Sobreestimé a Túnez:** le di λ 0.855 esperando algo del "rebote Renard" y
  de que se abriera; no generó nada. Lección: a un equipo golpeado y sin nueve,
  el "debe atacar" no se traduce en xG.
- 🟡 **El 0-4 fue varianza de definición, no del modelo:** Japón convirtió 4 con
  2.07 de xG (≈2× su rendimiento esperado). Mi marcador sugerido (0-2) reflejaba
  el escenario central correcto; la goleada estaba en la cola (Japón por 4+ = 8.3%).
- 📌 **Nota de apuestas:** la combinada final (BTTS No + Japón gana + Japón +4
  córners + Japón mayor córners) ganó las 4 patas. Pero seguía siendo **−EV** por
  el modelo (~−17% a cuota 3.60): ganar no la vuelve buena retroactivamente.
  Acierto del proceso: **no** haber sumado "Under 3.5", que habría perdido
  (total = 4 goles).

**Nota de proceso:** favorito clarísimo que ganó como se esperaba (poco mérito en
el resultado); el valor estuvo en calibrar bien a Japón y en depurar la
combinada. El modelo fue transparente con lo que no controla (la magnitud).

---

## 2026-06-20 · Ecuador vs Curaçao (Grupo E)

**Predicción del modelo:** Ecuador 79.0% / Empate 15.8% / Curaçao 5.1%. Confianza
ALTA (alineado con mercado, Opta 86.1). Sugerido: gana Ecuador, marcador 2-0.
xG: Ecuador 2.30, Curaçao 0.44.

**Resultado real:** Ecuador 0-0 Curaçao. Eloy Room (arquero de Curaçao) hizo
~15 atajadas, una de las mejores actuaciones individuales en la historia del
Mundial. Ecuador 75% posesión, 642 pases, y no pudo romper el cero.

**Lectura honesta:**
- 🟡 1X2: el favorito NO ganó. El empate (que el modelo daba 26% — más que el
  mercado) se dio. Mi escepticismo sobre "favorito romo vs bloque bajo" quedó
  VALIDADO acá (a diferencia de España, donde el mismo escepticismo falló).
- El marcador sugerido (2-0) erró, pero el modelo ya marcaba mucho riesgo de
  empate y yo estaba por debajo del mercado en la goleada.
- 📌 Dato de apuestas (prop de pases): Piero Hincapié terminó con 72 pases
  (62/72, 86%) según Opta — el "142" que circulaba era Hincapié+Pacho COMBINADO.

*(Corrección registrada: el árbitro de este partido NO era István Kovács; ese
dato venía de una sola fuente y resultó erróneo — Kovács dirigió Túnez-Japón.)*
