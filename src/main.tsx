import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import './index.css';
import App from './App.tsx';
import OverviewPage from './routes/OverviewPage.tsx';
import CorrelationsPage from './routes/CorrelationsPage.tsx';
import ModelsPage from './routes/ModelsPage.tsx';
import CaseStudiesPage from './routes/CaseStudiesPage.tsx';
import AboutPage from './routes/AboutPage.tsx';

const queryClient = new QueryClient();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<App />}>
            <Route index element={<OverviewPage />} />
            <Route path="correlations" element={<CorrelationsPage />} />
            <Route path="models" element={<ModelsPage />} />
            <Route path="case-studies" element={<CaseStudiesPage />} />
            <Route path="about" element={<AboutPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
