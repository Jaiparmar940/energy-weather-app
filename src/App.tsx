import { Outlet, Link } from 'react-router-dom';
import './App.css';

function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>Energy, Weather & Data Centers</h1>
        </div>
        <nav className="app-nav">
          <Link to="/">Overview</Link>
          <Link to="/correlations">Correlations</Link>
          <Link to="/models">Models</Link>
          <Link to="/case-studies">Case Studies</Link>
          <Link to="/about">About</Link>
        </nav>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}

export default App;
