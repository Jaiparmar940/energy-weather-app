import { useQuery } from '@tanstack/react-query';
import { getModelMetrics } from '../lib/dataClient';
import ModelRmseBarChart from '../components/charts/ModelRmseBarChart';

export default function ModelsPage() {
  const { data: metrics, isLoading } = useQuery({
    queryKey: ['model-metrics'],
    queryFn: () => getModelMetrics(),
  });

  return (
    <div>
      <h2>Prediction Model Accuracy</h2>
      <p>
        Compare how well weather-based models explain demand and pricing in data-center-heavy versus
        non–data-center-heavy regions, and how much additional signal comes from data-center proxies.
      </p>
      {isLoading || !metrics ? (
        <p>Loading model performance metrics…</p>
      ) : (
        <>
          <ModelRmseBarChart metrics={metrics} />
          <table>
          <thead>
            <tr>
              <th>Region</th>
              <th>Period</th>
              <th>Target</th>
              <th>Model</th>
              <th>RMSE</th>
              <th>MAE</th>
              <th>R²</th>
            </tr>
          </thead>
          <tbody>
            {metrics.slice(0, 50).map((m, idx) => (
              <tr key={idx}>
                <td>{m.regionId}</td>
                <td>{m.period}</td>
                <td>{m.target}</td>
                <td>{m.modelType}</td>
                <td>{m.rmse.toFixed(3)}</td>
                <td>{m.mae.toFixed(3)}</td>
                <td>{m.r2.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </>
      )}
    </div>
  );
}

