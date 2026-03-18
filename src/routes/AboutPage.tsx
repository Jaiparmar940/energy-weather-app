export default function AboutPage() {
  return (
    <div>
      <h2>About This Project</h2>
      <p>
        This web app explores how the historical relationship between weather patterns and grid
        demand/pricing is changing in regions with rapid data center growth.
      </p>
      <section>
        <h3>Research questions</h3>
        <ul>
          <li>
            To what extent has the correlation between weather patterns and grid demand shifted in
            regions with high data center growth?
          </li>
          <li>
            How does the accuracy of energy usage prediction models differ between data-center-heavy
            and non–data-center-heavy regions?
          </li>
        </ul>
      </section>
      <section>
        <h3>Data sources</h3>
        <ul>
          <li>EIA Open Data for regional demand and ISO-level context.</li>
          <li>NOAA NCEI Integrated Surface Database (ISD) for weather features.</li>
          <li>
            PJM Dataminer for high-resolution load, pricing, and generation-by-fuel-type in
            data-center-intensive regions.
          </li>
        </ul>
      </section>
      <section>
        <h3>Methodology (high level)</h3>
        <p>
          Offline scripts join PJM, NOAA, and optional EIA datasets at an hourly or five-minute
          cadence, engineer weather and grid features, and label regions as data-center-heavy versus
          non–data-center-heavy. The app loads precomputed correlation summaries and model
          performance metrics to visualize how these relationships evolve across time periods.
        </p>
      </section>
    </div>
  );
}

