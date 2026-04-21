import type { HypothesisMetricResult } from '../../types';

interface Props {
  figLabel: string;
  result?: HypothesisMetricResult;
  /** e.g. "mean |corr|" or "mean nRMSE" */
  differenceDescription: string;
}

export default function MeanDifferenceCiFigure({ figLabel, result, differenceDescription }: Props) {
  if (!result) {
    return (
      <div style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 12 }}>
        <div style={{ fontWeight: 600 }}>{figLabel}</div>
        <p style={{ marginTop: 8 }}>Loading inferential summary…</p>
      </div>
    );
  }

  const ciL = result.diffCiLower;
  const ciU = result.diffCiUpper;
  const hasCi =
    ciL != null && ciU != null && Number.isFinite(ciL) && Number.isFinite(ciU) && ciU >= ciL;

  const caption = hasCi
    ? `Inferential (bootstrap): 95% CI for ${differenceDescription} (DC mean − non-DC mean). This interval does not, by itself, establish practical importance; see Table 1 for permutation p-value when eligible.`
    : `Inferential CI not shown: ${result.resultLabel}. ${result.warnings[0] ?? 'See Table 1 warnings.'}`;

  const w = 420;
  const h = 140;
  const padL = 52;
  const padR = 16;
  const padT = 32;
  const padB = 28;
  const innerW = w - padL - padR;

  const est = result.signedDifference;

  let domainMin = -1;
  let domainMax = 1;
  if (hasCi && ciL != null && ciU != null) {
    const span = Math.max(ciU - ciL, Math.abs(est) * 0.2, 1e-9);
    domainMin = Math.min(0, ciL, est) - span * 0.12;
    domainMax = Math.max(0, ciU, est) + span * 0.12;
  } else if (Number.isFinite(est)) {
    const pad = Math.max(Math.abs(est) * 0.25, 1e-6);
    domainMin = Math.min(0, est) - pad;
    domainMax = Math.max(0, est) + pad;
  }

  const denom = Math.max(domainMax - domainMin, 1e-12);
  const xScale = (v: number) => ((v - domainMin) / denom) * innerW;

  const x0 = padL + xScale(0);
  const xEst = padL + (Number.isFinite(est) ? xScale(est) : innerW / 2);
  const xLo = hasCi && ciL != null ? padL + xScale(ciL) : padL;
  const xHi = hasCi && ciU != null ? padL + xScale(ciU) : padL + innerW;

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 12 }}>
      <div style={{ fontWeight: 600 }}>{figLabel}</div>
      <p style={{ marginTop: 6, fontSize: '0.9rem', opacity: 0.9 }}>{caption}</p>
      <p style={{ marginTop: 4, fontSize: '0.85rem' }}>
        Point estimate (DC − non-DC): <strong>{Number.isFinite(est) ? est.toFixed(4) : '—'}</strong>
        {' · '}
        <strong>n</strong> (DC / non-DC): {result.nDc} / {result.nNonDc}
      </p>
      <svg width="100%" viewBox={`0 0 ${w} ${h}`} style={{ marginTop: 8, maxWidth: 520 }}>
        <text x={padL} y={18} fontSize={11} fill="currentColor" opacity={0.8}>
          Difference (DC − non-DC)
        </text>
        <line x1={x0} x2={x0} y1={padT} y2={h - padB} stroke="#64748b" strokeWidth={1} strokeDasharray="4 3" />
        <text x={x0 + 4} y={padT + 12} fontSize={10} fill="#64748b">
          0
        </text>
        {hasCi && ciL != null && ciU != null ? (
          <line x1={xLo} x2={xHi} y1={h / 2} y2={h / 2} stroke="#94a3b8" strokeWidth={6} strokeLinecap="round" />
        ) : (
          <text x={padL} y={h / 2 - 10} fontSize={11} fill="currentColor" opacity={0.75}>
            No bootstrap CI plotted (small group or export missing CI).
          </text>
        )}
        {Number.isFinite(est) ? <circle cx={xEst} cy={h / 2} r={6} fill="#0f172a" /> : null}
        {hasCi && ciL != null && ciU != null ? (
          <text x={padL} y={h - 8} fontSize={10} fill="currentColor" opacity={0.85}>
            95% CI: [{ciL.toFixed(4)}, {ciU.toFixed(4)}]
          </text>
        ) : null}
      </svg>
    </div>
  );
}
