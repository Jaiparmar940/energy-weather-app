import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getCorrelationSummaries, getNodes, getRegions } from '../lib/dataClient';
import type { CorrelationRecord, Node } from '../types';
import CorrelationBarChart from '../components/charts/CorrelationBarChart';
import CorrelationTrendChart from '../components/charts/CorrelationTrendChart';

function ToggleList({
  title,
  items,
  selected,
  onChange,
  getLabel,
}: {
  title: string;
  items: string[];
  selected: Set<string>;
  onChange: (next: Set<string>) => void;
  getLabel?: (id: string) => string;
}) {
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <strong>{title}</strong>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            type="button"
            onClick={() => onChange(new Set(items))}
            style={{ padding: '6px 10px' }}
          >
            Select all
          </button>
          <button
            type="button"
            onClick={() => onChange(new Set())}
            style={{ padding: '6px 10px' }}
          >
            Clear
          </button>
        </div>
      </div>
      <div
        style={{
          marginTop: 10,
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: 8,
          maxHeight: 220,
          overflow: 'auto',
          paddingRight: 4,
        }}
      >
        {items.map((id) => {
          const checked = selected.has(id);
          return (
            <label key={id} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                type="checkbox"
                checked={checked}
                onChange={(e) => {
                  const next = new Set(selected);
                  if (e.target.checked) next.add(id);
                  else next.delete(id);
                  onChange(next);
                }}
              />
              <span style={{ fontFamily: 'var(--mono)' }}>{getLabel ? getLabel(id) : id}</span>
            </label>
          );
        })}
      </div>
    </div>
  );
}

function QuantitativeChangeSection({
  records,
  nodeById,
}: {
  records: CorrelationRecord[];
  nodeById: Map<string, Node>;
}) {
  const withYear = records.filter((r) => typeof r.year === 'number' && r.nodeId);
  if (withYear.length === 0) {
    return <p>No year-tagged correlations in the current selection.</p>;
  }

  type Key = string;
  interface Entry {
    key: Key;
    nodeId: string;
    regionId: string;
    variable: string;
    target: string;
    firstYear: number;
    lastYear: number;
    firstCorr: number;
    lastCorr: number;
    strengthFirst: number;
    strengthLast: number;
    deltaStrength: number;
    slopeStrengthPerYear: number;
  }

  const groups = new Map<Key, CorrelationRecord[]>();
  withYear.forEach((r) => {
    const key = `${r.nodeId}|${r.variable}|${r.target}`;
    const arr = groups.get(key) ?? [];
    arr.push(r);
    groups.set(key, arr);
  });

  const entries: Entry[] = [];
  groups.forEach((rows, key) => {
    const sorted = [...rows].sort(
      (a, b) => (a.year as number) - (b.year as number),
    );
    const first = sorted[0];
    const last = sorted[sorted.length - 1];
    if (first.year === last.year) return;
    const firstStrength = Math.abs(first.correlation);
    const lastStrength = Math.abs(last.correlation);

    // Simple linear regression slope of |corr| vs year.
    const xs = sorted.map((r) => r.year as number);
    const ys = sorted.map((r) => Math.abs(r.correlation));
    const n = xs.length;
    const xMean = xs.reduce((a, b) => a + b, 0) / n;
    const yMean = ys.reduce((a, b) => a + b, 0) / n;
    let num = 0;
    let den = 0;
    for (let i = 0; i < n; i += 1) {
      const dx = xs[i] - xMean;
      num += dx * (ys[i] - yMean);
      den += dx * dx;
    }
    const slope = den > 0 ? num / den : 0;

    const entry: Entry = {
      key,
      nodeId: String(first.nodeId),
      regionId: first.regionId,
      variable: first.variable,
      target: first.target,
      firstYear: first.year as number,
      lastYear: last.year as number,
      firstCorr: first.correlation,
      lastCorr: last.correlation,
      strengthFirst: firstStrength,
      strengthLast: lastStrength,
      deltaStrength: lastStrength - firstStrength,
      slopeStrengthPerYear: slope,
    };
    entries.push(entry);
  });

  if (entries.length === 0) {
    return <p>No node/variable combination has correlations in multiple years for this selection.</p>;
  }

  const topIncrease = [...entries]
    .sort((a, b) => b.deltaStrength - a.deltaStrength)
    .slice(0, 10);
  const topDecrease = [...entries]
    .sort((a, b) => a.deltaStrength - b.deltaStrength)
    .slice(0, 10);

  const variableStats = (() => {
    const byVar = new Map<
      string,
      { count: number; sumDelta: number; sumSlope: number }
    >();
    entries.forEach((e) => {
      const key = e.variable;
      const cur = byVar.get(key) ?? { count: 0, sumDelta: 0, sumSlope: 0 };
      cur.count += 1;
      cur.sumDelta += e.deltaStrength;
      cur.sumSlope += e.slopeStrengthPerYear;
      byVar.set(key, cur);
    });
    const rows = Array.from(byVar.entries()).map(([variable, v]) => ({
      variable,
      count: v.count,
      avgDelta: v.sumDelta / v.count,
      avgSlope: v.sumSlope / v.count,
    }));
    rows.sort((a, b) => a.variable.localeCompare(b.variable));
    const totalCount = entries.length;
    const totalDelta = entries.reduce((sum, e) => sum + e.deltaStrength, 0);
    const totalSlope = entries.reduce((sum, e) => sum + e.slopeStrengthPerYear, 0);
    rows.push({
      variable: 'All variables',
      count: totalCount,
      avgDelta: totalDelta / totalCount,
      avgSlope: totalSlope / totalCount,
    });
    return rows;
  })();

  const renderTable = (rows: Entry[]) => (
    <table>
      <thead>
        <tr>
          <th>Node ID</th>
          <th>Node Name</th>
          <th>Region</th>
          <th>Variable</th>
          <th>Target</th>
          <th>Start year</th>
          <th>Corr (start)</th>
          <th>|Corr| (start)</th>
          <th>End year</th>
          <th>Corr (end)</th>
          <th>|Corr| (end)</th>
          <th>Δ |Corr|</th>
          <th>Slope(|Corr|)/year</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((e) => {
          const node = nodeById.get(e.nodeId);
          return (
            <tr key={e.key}>
              <td>{e.nodeId}</td>
              <td>{node?.name ?? '—'}</td>
              <td>{e.regionId}</td>
              <td>{e.variable}</td>
              <td>{e.target}</td>
              <td>{e.firstYear}</td>
              <td>{e.firstCorr.toFixed(3)}</td>
              <td>{e.strengthFirst.toFixed(3)}</td>
              <td>{e.lastYear}</td>
              <td>{e.lastCorr.toFixed(3)}</td>
              <td>{e.strengthLast.toFixed(3)}</td>
              <td>{e.deltaStrength.toFixed(3)}</td>
              <td>{e.slopeStrengthPerYear.toFixed(4)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );

  return (
    <div>
      <p style={{ marginBottom: 8 }}>
        Based on <strong>{withYear.length}</strong> year-tagged correlation points across{' '}
        <strong>{groups.size}</strong> node/variable/target combinations.
      </p>
      <table>
        <thead>
          <tr>
            <th>Variable</th>
            <th>Combinations</th>
            <th>Avg Δ|corr|</th>
            <th>Avg slope(|corr|)/year</th>
          </tr>
        </thead>
        <tbody>
          {variableStats.map((row) => (
            <tr key={row.variable}>
              <td>{row.variable}</td>
              <td>{row.count}</td>
              <td>{row.avgDelta.toFixed(3)}</td>
              <td>{row.avgSlope.toFixed(4)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ marginTop: 12 }}>
        <h4>Largest increases in |correlation|</h4>
        {renderTable(topIncrease)}
      </div>
      <div style={{ marginTop: 16 }}>
        <h4>Largest decreases in |correlation|</h4>
        {renderTable(topDecrease)}
      </div>
    </div>
  );
}
function CorrelationTable({
  data,
  nodeById,
}: {
  data: CorrelationRecord[];
  nodeById: Map<string, Node>;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const sorted = useMemo(
    () => [...data].sort((a, b) => Math.abs(b.correlation) - Math.abs(a.correlation)),
    [data],
  );
  const previewCount = 12;
  const visible = isExpanded ? sorted : sorted.slice(0, previewCount);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 12 }}>
        <p style={{ margin: 0 }}>
          Showing <strong>{visible.length}</strong> of <strong>{sorted.length}</strong> rows.
        </p>
        {sorted.length > previewCount ? (
          <button
            type="button"
            onClick={() => setIsExpanded((v) => !v)}
            style={{ padding: '6px 10px' }}
          >
            {isExpanded ? 'Show fewer' : 'Show all'}
          </button>
        ) : null}
      </div>
      <table>
        <thead>
          <tr>
            <th>Node ID</th>
            <th>Node Name</th>
            <th>DC-heavy?</th>
            <th>Region</th>
            <th>Year</th>
            <th>Period</th>
            <th>Bucket</th>
            <th>Variable</th>
            <th>Target</th>
            <th>Correlation</th>
          </tr>
        </thead>
        <tbody>
          {visible.map((row, idx) => {
            const node = row.nodeId ? nodeById.get(row.nodeId) : undefined;
            return (
              <tr key={idx}>
                <td>{row.nodeId ?? '—'}</td>
                <td>{node?.name ?? '—'}</td>
                <td>{node ? (node.isDataCenterHeavy ? 'Yes' : 'No') : '—'}</td>
                <td>{row.regionId}</td>
                <td>{row.year ?? '—'}</td>
                <td>{row.period}</td>
                <td>{row.isDataCenterHeavyBucket}</td>
                <td>{row.variable}</td>
                <td>{row.target}</td>
                <td>{row.correlation.toFixed(3)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function CorrelationsPage() {
  const { data: regions } = useQuery({
    queryKey: ['regions'],
    queryFn: getRegions,
  });

  const { data: nodes } = useQuery({
    queryKey: ['nodes'],
    queryFn: getNodes,
  });

  const { data: correlations, isLoading } = useQuery({
    queryKey: ['correlations'],
    queryFn: () => getCorrelationSummaries(),
  });

  const nodeById = useMemo(() => {
    const map = new Map<string, Node>();
    (nodes ?? []).forEach((n) => map.set(n.id, n));
    return map;
  }, [nodes]);

  const availableNodeIds = useMemo(() => {
    const s = new Set<string>();
    (correlations ?? []).forEach((r) => {
      if (r.nodeId) s.add(r.nodeId);
    });
    return Array.from(s).sort();
  }, [correlations]);

  const availableVariables = useMemo(() => {
    const s = new Set<string>();
    (correlations ?? []).forEach((r) => s.add(r.variable));
    return Array.from(s).sort();
  }, [correlations]);

  const availableYears = useMemo(() => {
    const s = new Set<number>();
    (correlations ?? []).forEach((r) => {
      if (typeof r.year === 'number') s.add(r.year);
    });
    return Array.from(s).sort((a, b) => a - b);
  }, [correlations]);

  const [selectedNodeIds, setSelectedNodeIds] = useState<Set<string>>(new Set());
  const [selectedVariables, setSelectedVariables] = useState<Set<string>>(new Set());
  const [dcFilter, setDcFilter] = useState<'all' | 'dc' | 'nonDc'>('all');
  const [fromYear, setFromYear] = useState<number | undefined>(undefined);
  const [toYear, setToYear] = useState<number | undefined>(undefined);

  const filtered = useMemo(() => {
    const base = correlations ?? [];
    return base.filter((r) => {
      if (dcFilter !== 'all') {
        if (!r.nodeId) return false;
        const node = nodeById.get(r.nodeId);
        if (!node) return false;
        if (dcFilter === 'dc' && !node.isDataCenterHeavy) return false;
        if (dcFilter === 'nonDc' && node.isDataCenterHeavy) return false;
      }
      if (selectedNodeIds.size > 0) {
        if (!r.nodeId || !selectedNodeIds.has(r.nodeId)) return false;
      }
      if (selectedVariables.size > 0) {
        if (!selectedVariables.has(r.variable)) return false;
      }
      if (fromYear !== undefined && typeof r.year === 'number' && r.year < fromYear) {
        return false;
      }
      if (toYear !== undefined && typeof r.year === 'number' && r.year > toYear) {
        return false;
      }
      return true;
    });
  }, [correlations, selectedNodeIds, selectedVariables, dcFilter, nodeById, fromYear, toYear]);

  const nodeIdsForPicker = useMemo(() => {
    if (dcFilter === 'all') return availableNodeIds;
    return availableNodeIds.filter((id) => {
      const node = nodeById.get(id);
      if (!node) return false;
      return dcFilter === 'dc' ? node.isDataCenterHeavy : !node.isDataCenterHeavy;
    });
  }, [availableNodeIds, dcFilter, nodeById]);

  return (
    <div>
      <h2>Correlation Explorer</h2>
      <p>
        Inspect how the strength of the relationship between weather variables and grid demand/pricing
        changes across regions, time periods, and data-center intensity.
      </p>
      <section>
        <h3>Regions loaded</h3>
        <p>{regions ? regions.map((r) => r.name).join(', ') : 'Loading…'}</p>
      </section>
      <section>
        <h3>Filters</h3>
        <p>
          Select which <strong>nodes</strong> and <strong>variables</strong> to include. Leaving a filter
          empty means “include all.”
        </p>
        <div className="definitionCard" style={{ marginTop: 8, marginBottom: 12 }}>
          <div className="definitionHeader">
            <strong>Variable definitions</strong>
            <span style={{ fontSize: '0.85rem', opacity: 0.85 }}>
              Degree-hour base temperature: <span style={{ fontFamily: 'var(--mono)' }}>18°C</span>
            </span>
          </div>
          <div className="definitionGrid">
            <div className="definitionItem">
              <span className="definitionPill">TEMP_C</span>
              <div style={{ marginTop: 8 }}>
                Hourly air temperature (°C) from NOAA ISD station observations mapped to a node.
              </div>
            </div>
            <div className="definitionItem">
              <span className="definitionPill">DEW_C</span>
              <div style={{ marginTop: 8 }}>Dew point temperature (°C) from NOAA ISD.</div>
            </div>
            <div className="definitionItem">
              <span className="definitionPill">RH_PCT</span>
              <div style={{ marginTop: 8 }}>
                Relative humidity (%) estimated from TEMP_C and DEW_C (Magnus approximation).
              </div>
            </div>
            <div className="definitionItem">
              <span className="definitionPill">WIND_MS</span>
              <div style={{ marginTop: 8 }}>Wind speed (m/s) parsed from NOAA ISD wind group.</div>
            </div>
            <div className="definitionItem">
              <span className="definitionPill">SLP_HPA</span>
              <div style={{ marginTop: 8 }}>Sea-level pressure (hPa).</div>
            </div>
            <div className="definitionItem">
              <span className="definitionPill">PRECIP_MM</span>
              <div style={{ marginTop: 8 }}>
                Precipitation depth (mm) from NOAA ISD hourly precipitation group when present.
              </div>
            </div>
            <div className="definitionItem">
              <span className="definitionPill">CDH</span>
              <div style={{ marginTop: 8 }}>Cooling Degree Hours (proxy for cooling demand).</div>
              <div className="definitionFormula">max(0, TEMP_C - 18)</div>
            </div>
            <div className="definitionItem">
              <span className="definitionPill">HDH</span>
              <div style={{ marginTop: 8 }}>Heating Degree Hours (proxy for heating demand).</div>
              <div className="definitionFormula">max(0, 18 - TEMP_C)</div>
            </div>
          </div>
        </div>
        <div style={{ marginTop: 12, border: '1px solid var(--border)', borderRadius: 8, padding: 12 }}>
          <strong>Data center intensity</strong>
          <div style={{ marginTop: 8, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                type="radio"
                name="dcFilter"
                checked={dcFilter === 'all'}
                onChange={() => setDcFilter('all')}
              />
              <span>All nodes</span>
            </label>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                type="radio"
                name="dcFilter"
                checked={dcFilter === 'dc'}
                onChange={() => setDcFilter('dc')}
              />
              <span>DC-heavy only</span>
            </label>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                type="radio"
                name="dcFilter"
                checked={dcFilter === 'nonDc'}
                onChange={() => setDcFilter('nonDc')}
              />
              <span>Non‑DC only</span>
            </label>
          </div>
          <div style={{ marginTop: 10, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <label style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <span>From year</span>
              <select
                value={fromYear ?? ''}
                onChange={(e) =>
                  setFromYear(e.target.value ? Number(e.target.value) : undefined)
                }
              >
                <option value="">(min)</option>
                {availableYears.map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </select>
            </label>
            <label style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <span>To year</span>
              <select
                value={toYear ?? ''}
                onChange={(e) => setToYear(e.target.value ? Number(e.target.value) : undefined)}
              >
                <option value="">(max)</option>
                {availableYears.map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
        <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <ToggleList
            title="Nodes"
            items={nodeIdsForPicker}
            selected={selectedNodeIds}
            onChange={setSelectedNodeIds}
            getLabel={(id) => {
              const node = nodeById.get(id);
              const name = node?.name ? ` (${node.name})` : '';
              return `${id}${name}`;
            }}
          />
          <ToggleList
            title="Variables"
            items={availableVariables}
            selected={selectedVariables}
            onChange={setSelectedVariables}
          />
        </div>
        <p style={{ marginTop: 8 }}>
          Showing <strong>{filtered.length}</strong> of <strong>{correlations?.length ?? 0}</strong>{' '}
          correlation rows.
        </p>
      </section>
      <section>
        <h3>Correlation over time (by year)</h3>
        <p>
          This view shows how correlation changes across years for the selected nodes/variables. If you
          don’t see multiple years yet, run the export script for several years with{' '}
          <code>--append</code>.
        </p>
        {isLoading || !correlations ? <p>Loading…</p> : <CorrelationTrendChart records={filtered} />}
      </section>
      <section>
        <h3>Quantitative change over time</h3>
        <p>
          For the selected filters and year window, this summarizes how much correlation changes between
          the earliest and latest year where data is available for each node/variable/target.
        </p>
        {isLoading || !correlations ? (
          <p>Loading…</p>
        ) : (
          <QuantitativeChangeSection records={filtered} nodeById={nodeById} />
        )}
      </section>
      <section>
        <h3>Top absolute correlations (sample)</h3>
        {isLoading || !correlations ? (
          <p>Loading correlation summaries…</p>
        ) : (
          <>
            <CorrelationBarChart records={filtered} />
            <CorrelationTable data={filtered} nodeById={nodeById} />
          </>
        )}
      </section>
    </div>
  );
}

