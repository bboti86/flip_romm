'use client';

import { useState } from 'react';

export default function Home() {
  const [name, setName] = useState('');
  const [gamesText, setGamesText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<{
    addedGames: string[];
    missingGames: string[];
    collectionId: number;
  } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResults(null);

    try {
      const res = await fetch('/api/collections/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name, gamesText }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || 'Something went wrong');
      }

      setResults(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="container">
      <h1>RomM Collection Creator</h1>
      <p className="subtitle">Easily generate RomM collections from a list of games</p>

      <div className="glass-card">
        {error && <div className="error-msg">{error}</div>}
        
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="collectionName">Collection Name</label>
            <input
              id="collectionName"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. My Favorite RPGs"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="gamesList">List of Games</label>
            <textarea
              id="gamesList"
              value={gamesText}
              onChange={(e) => setGamesText(e.target.value)}
              placeholder="Paste your games here (one per line)...&#10;e.g.&#10;Super Mario World (SNES)&#10;Chrono Trigger"
              required
            />
          </div>

          <button type="submit" className="btn" disabled={loading || !name || !gamesText}>
            {loading ? 'Analyzing & Creating...' : 'Create Collection'}
            {loading && <div className="loader"></div>}
          </button>
        </form>
      </div>

      {results && (
        <div className="results">
          <div className="result-box success">
            <h3>✅ Added ROMs ({results.addedGames.length})</h3>
            <ul className="game-list">
              {results.addedGames.length > 0 ? (
                results.addedGames.map((game, idx) => (
                  <li key={idx} className="game-item">{game}</li>
                ))
              ) : (
                <li className="game-item text-secondary">No games matched.</li>
              )}
            </ul>
          </div>

          <div className="result-box missing">
            <h3>⚠️ Missing ROMs ({results.missingGames.length})</h3>
            <ul className="game-list">
              {results.missingGames.length > 0 ? (
                results.missingGames.map((game, idx) => (
                  <li key={idx} className="game-item">{game}</li>
                ))
              ) : (
                <li className="game-item text-secondary">All games found!</li>
              )}
            </ul>
          </div>
        </div>
      )}
    </main>
  );
}
