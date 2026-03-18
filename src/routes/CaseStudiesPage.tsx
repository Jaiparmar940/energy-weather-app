import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getNodes, getCaseStudySeries } from '../lib/dataClient';

export default function CaseStudiesPage() {
  const { data: nodes } = useQuery({
    queryKey: ['nodes'],
    queryFn: getNodes,
  });

  const [selectedNodeId, setSelectedNodeId] = useState<string | undefined>(undefined);

  const { data: series, isLoading } = useQuery({
    queryKey: ['case-study', selectedNodeId],
    queryFn: () => (selectedNodeId ? getCaseStudySeries(selectedNodeId) : Promise.resolve([])),
    enabled: !!selectedNodeId,
  });

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
            <option value="">Select a node…</option>
            {nodes?.map((n) => (
              <option key={n.id} value={n.id}>
                {n.name} {n.isDataCenterHeavy ? '(DC-heavy)' : ''}
              </option>
            ))}
          </select>
        </label>
      </section>
      <section>
        {selectedNodeId == null ? (
          <p>Select a node to load a case study time series.</p>
        ) : isLoading || !series ? (
          <p>Loading case study series…</p>
        ) : (
          <ul>
            {series.map((s) => (
              <li key={s.period}>
                Period {s.period}: {s.points.length} points loaded.
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

