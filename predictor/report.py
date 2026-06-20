"""Render a MatchResult as the full Spanish report, in the required order:

  1. Contexto del partido
  2. Como se calibro (datos duros + razonamiento del xG)
  3. Tabla 1X2
  4. Validacion vs mercado y supercomputadoras
  5. Mercados de goles
  6. Marcadores mas probables
  7. Indice de confianza
  8. Recomendacion para el prode
  9. Advertencias de incertidumbre
"""

from __future__ import annotations

from .match import MatchResult
from .simulate import convergence_report


def _pct(x: float) -> str:
    return f"{x:6.1%}"


def render(result: MatchResult, include_convergence: bool = True) -> str:
    m = result.markets
    meta = result.meta
    out = []

    out.append("=" * 64)
    out.append(f"  {meta.home}  vs  {meta.away}".upper())
    out.append("=" * 64)

    # 1. Contexto
    out.append("\n[1] CONTEXTO DEL PARTIDO")
    out.append(f"  Sede:  {meta.venue or 'n/d'}")
    out.append(f"  Fecha: {meta.date or 'n/d'}")
    out.append(f"  Fase:  {meta.stage or 'n/d'}")
    if meta.stakes:
        out.append(f"  Que se juega: {meta.stakes}")

    # 2. Calibracion
    out.append("\n[2] COMO SE CALIBRO (razonamiento del xG)")
    out.append("  " + result.calibration.reasoning().replace("\n", "\n  "))
    out.append(
        f"\n  => lambda final: {meta.home} {m.xg_home:.2f} | "
        f"{meta.away} {m.xg_away:.2f}  (xG del modelo)"
    )

    # 3. 1X2
    out.append("\n[3] 1X2 (probabilidades)")
    out.append(f"  Gana {meta.home:<18} {_pct(m.p_home)}")
    out.append(f"  Empate{'':<17} {_pct(m.p_draw)}")
    out.append(f"  Gana {meta.away:<18} {_pct(m.p_away)}")

    # 4. Validacion
    out.append("\n[4] VALIDACION vs MERCADO / SUPERCOMPUTADORA")
    if result.market_fair or result.supercomputer:
        out.append(f"  {'Fuente':<18} |  Local | Empate | Visit.")
        out.append("  " + "-" * 46)
        out.append(
            f"  {'Modelo propio':<18} | {_pct(m.p_home)} | {_pct(m.p_draw)} | {_pct(m.p_away)}"
        )
        if result.market_fair:
            f = result.market_fair
            out.append(
                f"  {'Mercado (de-vig)':<18} | {_pct(f['home'])} | {_pct(f['draw'])} | "
                f"{_pct(f['away'])}   (margen casa {f['overround']*100:.1f}%)"
            )
        if result.supercomputer:
            s = result.supercomputer
            out.append(
                f"  {'Supercomputadora':<18} | {_pct(s[0])} | {_pct(s[1])} | {_pct(s[2])}"
            )
        if result.market_divergence is not None:
            flag = "OK (alineado)" if result.market_divergence <= 0.07 else "REVISAR calibracion (>7 pts)"
            out.append(
                f"  Divergencia max modelo vs mercado: "
                f"{result.market_divergence*100:.1f} pts -> {flag}"
            )
    else:
        out.append("  (sin odds de mercado ni supercomputadora cargadas)")

    # 5. Mercados de goles
    out.append("\n[5] MERCADOS DE GOLES")
    out.append(f"  Goles esperados totales: {m.exp_total_goals:.2f}")
    for ln in sorted(m.over):
        out.append(
            f"  Over {ln}: {_pct(m.over[ln])}   |  Under {ln}: {_pct(m.under[ln])}"
        )
    out.append(f"  Ambos marcan (BTTS): Si {_pct(m.btts_yes)} | No {_pct(m.btts_no)}")
    out.append(
        f"  Valla invicta: {meta.home} {_pct(m.clean_sheet_home)} | "
        f"{meta.away} {_pct(m.clean_sheet_away)}"
    )

    # 6. Marcadores
    out.append("\n[6] MARCADORES MAS PROBABLES")
    for (h, a), p in m.top_scorelines:
        out.append(f"  {h}-{a}: {_pct(p)}")

    # Extra markets
    if result.corners:
        c = result.corners
        out.append("\n[5b] CORNERS (mercado ruidoso, orientativo)")
        out.append(f"  Total esperado: {c['expected_total']}")
        for ln in sorted(c["over"]):
            out.append(f"  Over {ln}: {_pct(c['over'][ln])} | Under {ln}: {_pct(c['under'][ln])}")
        out.append(f"  Nota: {c['_caveat']}")
    if result.cards:
        cd = result.cards
        out.append("\n[5c] TARJETAS (el mercado mas impredecible)")
        out.append(
            f"  Amarillas esperadas: {cd['expected_yellows']} "
            f"(base arbitro {cd['referee_base']})"
        )
        for ln in sorted(cd["over"]):
            out.append(f"  Over {ln}: {_pct(cd['over'][ln])} | Under {ln}: {_pct(cd['under'][ln])}")
        out.append(f"  Nota: {cd['_caveat']}")

    # 7. Confianza
    out.append("\n[7] INDICE DE CONFIANZA")
    out.append(f"  Nivel: {result.confidence_level}")
    out.append(f"  Motivo: {result.confidence_reason}")
    out.append(
        "  (La confianza es sobre el RESULTADO esperado, no sobre si se acierta. "
        "Un batacazo no baja la nota: era el escenario improbable ya contemplado.)"
    )

    # 8. Recomendacion prode
    out.append("\n[8] RECOMENDACION PARA EL PRODE")
    r = result.recommendation
    out.append(f"  Resultado sugerido: {r['result']} ({r['result_prob']:.0%})")
    out.append(f"  Marcador sugerido:  {r['scoreline']} ({r['scoreline_prob']:.0%})")

    # 9. Advertencias
    out.append("\n[9] ADVERTENCIAS DE INCERTIDUMBRE")
    out.append("  - El futbol tiene varianza irreducible enorme: esto son distribuciones,")
    out.append("    no predicciones cerradas. 'Lo mas probable' nunca es 'lo seguro'.")
    if result.confidence_level == "BAJA":
        out.append("  - Partido PAREJO: el modelo no tiene lectura fuerte. Cuidado en el prode.")
    out.append("  - Las combinadas multiplican el riesgo; tarjetas/corners son casi azar puro.")
    out.append("  - La casa tiene ventaja a largo plazo. Aposta solo lo que estes dispuesto a perder.")
    out.append("  - Recalibra con los XI confirmados (~60 min antes): pueden mover los lambda.")

    if include_convergence:
        out.append("\n[+] " + convergence_report(
            result.score_matrix, (m.p_home, m.p_draw, m.p_away)
        ).replace("\n", "\n  "))

    return "\n".join(out)
