import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getNodes, getCaseStudySeries, getCorrelationSummaries } from '../lib/dataClient';
import type { Node } from '../types';

function isDcLikely(node: Node): boolean {
  if (node.classificationLabel) {
    return node.classificationLabel === 'high_likelihood' || node.classificationLabel === 'medium_likelihood';
  }
  return node.isDataCenterHeavy;
}

export default function CaseStudiesPage() {
  const { data: nodes } = useQuery({
    queryKey: ['nodes'],
    queryFn: getNodes,
  });

  const { data: correlations } = useQuery({
    queryKey: ['correlations-for-case-studies'],
    queryFn: () => getCorrelationSummaries(),
  });

  const [selectedNodeId, setSelectedNodeId] = useState<string | undefined>(undefined);

  const availableNodeIds = useMemo(() => {
    const ids = new Set<string>();
    (correlations ?? []).forEach((r) => {
      if (r.nodeId) ids.add(r.nodeId);
    });
    return ids;
  }, [correlations]);

  const caseStudyNodes = useMemo(() => {
    if (!nodes) return [];
    return nodes
      .filter((n) => availableNodeIds.has(n.id))
      .sort((a, b) => {
        const dcA = isDcLikely(a) ? 0 : 1;
        const dcB = isDcLikely(b) ? 0 : 1;
        if (dcA !== dcB) return dcA - dcB;
        return a.name.localeCompare(b.name);
      });
  }, [nodes, availableNodeIds]);

  useEffect(() => {
    if (!selectedNodeId && caseStudyNodes.length > 0) {
      setSelectedNodeId(caseStudyNodes[0].id);
    }
  }, [selectedNodeId, caseStudyNodes]);

  const { data: series, isLoading } = useQuery({
    queryKey: ['case-study', selectedNodeId],
    queryFn: () => (selectedNodeId ? getCaseStudySeries(selectedNodeId) : Promise.resolve([])),
    enabled: !!selectedNodeId,
  });

  const selectedNode = useMemo(
    () => caseStudyNodes.find((n) => n.id === selectedNodeId),
    [caseStudyNodes, selectedNodeId],
  );

  const totalPoints = useMemo(
    () => (series ?? []).reduce((sum, s) => sum + s.points.length, 0),
    [series],
  );

  const preview = useMemo(() => {
    const rows = (series ?? []).flatMap((s) =>
      s.points.slice(0, 5).map((p) => ({ period: s.period, ...p })),
    );
    return rows.slice(0, 12);
  }, [series]);

  return (
    <div>
      <h2>Case Studies</h2>
      <p>
        Dive into specific nodes or subregions to see how weather and grid demand/pricing co-evolve
        over time, and how this differs for data-center-heavy nodes.
      </p>
      <section>
        <label>
          Node:
          <select
            value={selectedNodeId ?? ''}
            onChange={(e) => setSelectedNodeId(e.target.value || undefined)}
          >
            {caseStudyNodes.length === 0 ? (
              <option value="">No nodes with case-study data</option>
            ) : null}
            {caseStudyNodes.map((n) => (
              <option key={n.id} value={n.id}>
                {n.name} [{n.regionId}] {isDcLikely(n) ? '(DC-likely)' : '(non-DC)'}
              </option>
            ))}
          </select>
        </label>
        <p style={{ marginTop: 8 }}>
          Available nodes with case-study data: <strong>{caseStudyNodes.length}</strong>
        </p>
      </section>
      <section>
        {caseStudyNodes.length === 0 ? (
          <p>No case-study files are currently available. Re-run export generation to populate them.</p>
        ) : selectedNodeId == null ? (
          <p>Select a node to load a case study time series.</p>
        ) : isLoading || !series ? (
          <p>Loading case study series…</p>
        ) : series.length === 0 ? (
          <p>No case-study series found for this node yet.</p>
        ) : (
          <>
            <p>
              Node <strong>{selectedNode?.name ?? selectedNodeId}</strong> in{' '}
              <strong>{selectedNode?.regionId ?? 'unknown region'}</strong> has{' '}
              <strong>{series.length}</strong> period series and <strong>{totalPoints}</strong> total points.
            </p>
            <ul>
              {series.map((s) => (
                <li key={s.period}>
                  Period {s.period}: {s.points.length} points loaded.
                </li>
              ))}
            </ul>
            <h4>Preview rows</h4>
            <table>
              <thead>
                <tr>
                  <th>Period</th>
                  <th>Timestamp</th>
                  <th>Load</th>
                  <th>LMP</th>
                  <th>Temperature</th>
                  <th>CDH</th>
                  <th>HDH</th>
                </tr>
              </thead>
              <tbody>
                {preview.map((row, idx) => (
                  <tr key={`${row.period}-${row.timestamp}-${idx}`}>
                    <td>{row.period}</td>
                    <td>{row.timestamp}</td>
                    <td>{row.load.toFixed(2)}</td>
                    <td>{row.lmp?.toFixed(2) ?? '—'}</td>
                    <td>{row.temperature?.toFixed(2) ?? '—'}</td>
                    <td>{row.cdh?.toFixed(2) ?? '—'}</td>
                    <td>{row.hdh?.toFixed(2) ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </section>
    </div>
  );
}

