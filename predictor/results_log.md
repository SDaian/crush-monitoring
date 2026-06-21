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
| 2026-06-20 | Ecuador vs Curaçao | 79.0 / 15.8 / 5.1 | ALTA | ⏳ no registrado | ⏳ |
| 2026-06-21 | Túnez vs Japón | 14.7 / 21.7 / 63.6 | ALTA | 0-4 (gana Japón) | ✅ |

## Calibración de xG (lo que de verdad importa)

| Partido | Equipo | λ modelo | xG real | Veredicto |
|---|---|---|---|---|
| Túnez vs Japón | Japón | 2.00 | 2.07 | ✅ casi exacto |
| Túnez vs Japón | Túnez | 0.855 | 0.05 | ❌ sobreestimado (Túnez fue nulo) |

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

**Resultado real:** ⏳ no registrado.

*(Corrección registrada: el árbitro de este partido NO era István Kovács; ese
dato venía de una sola fuente y resultó erróneo — Kovács dirigió Túnez-Japón.)*
