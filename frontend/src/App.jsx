import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import SearchBar from './components/SearchBar';
import CaseGrid from './components/CaseGrid';
import CaseReaderModal from './components/CaseReaderModal';
import { getRandomCases, searchCases } from './services/api';

export default function App() {
  const [cases, setCases] = useState([]);
  const [selectedCase, setSelectedCase] = useState(null);
  const [loading, setLoading] = useState(false);
  const [isSearch, setIsSearch] = useState(false);
  const [currentQuery, setCurrentQuery] = useState('');

  // Initialisation : charge 6 affaires aléatoires au démarrage
  useEffect(() => {
    fetchRandomCases();
  }, []);

  const fetchRandomCases = async () => {
    setLoading(true);
    setIsSearch(false);
    setCurrentQuery('');
    try {
      const data = await getRandomCases(30);
      setCases(data || []);
    } catch (err) {
      console.warn("Échec du chargement aléatoire, fallback recherche :", err);
      // Fallback si l'endpoint random n'est pas encore rechargé par uvicorn
      handleSearch("expulsion locative loyer impayé clause résolutoire");
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async (queryText) => {
    if (!queryText.trim()) return;
    setLoading(true);
    setIsSearch(true);
    setCurrentQuery(queryText);
    try {
      const data = await searchCases(queryText.trim(), 30);
      setCases(data.results || []);
    } catch (err) {
      console.error("Erreur de recherche :", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FBFBFA] text-[#111317] flex flex-col font-sans selection:bg-neutral-900 selection:text-white">
      
      {/* 1. Header Minimaliste (Style Retouch AI) */}
      <Navbar onRefreshRandom={fetchRandomCases} loading={loading} />

      {/* 2. Hero & Barre de Recherche Centrale */}
      <main className="flex-1 pb-16 space-y-4">
        <SearchBar onSearch={handleSearch} loading={loading} />

        {/* 3. Grille de Découverte / Résultats (3 Colonnes) */}
        <CaseGrid
          cases={cases}
          onSelectCase={(c) => setSelectedCase(c)}
          isSearch={isSearch}
          query={currentQuery}
          onResetSearch={fetchRandomCases}
        />
      </main>

      {/* 4. Lecteur Immersif (Modal Focus avec Fond Flou) */}
      {selectedCase && (
        <CaseReaderModal
          caseItem={selectedCase}
          onClose={() => setSelectedCase(null)}
        />
      )}

      {/* 5. Footer Épuré */}
      <footer className="border-t border-paper-300 bg-white py-6 px-4 text-center text-xs text-ink-400">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2 font-mono text-[11px]">
          <p>© 2026 JurisConsult AI • Tribunal judiciaire de Paris • Master 2 IA</p>
          <p className="text-ink-400">Données certifiées Open Data Judilibre</p>
        </div>
      </footer>

    </div>
  );
}
