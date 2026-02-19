import { useState, useEffect, useRef } from 'react'
import './App.css'
import ArticleReader from './components/ArticleReader'
import DateNavigator from './components/DateNavigator'
import ZipLoader from './components/ZipLoader'

function App() {
  const [articles, setArticles] = useState([])
  const [currentDate, setCurrentDate] = useState('all')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [availableServerDates, setAvailableServerDates] = useState([])
  const [loadDateFunc, setLoadDateFunc] = useState(null)
  const [hideReadArticles, setHideReadArticles] = useState(() => {
    const saved = localStorage.getItem('nzz_hide_read_articles')
    return saved === 'true'
  })
  const [readArticles, setReadArticles] = useState(() => {
    const saved = localStorage.getItem('nzz_read_articles')
    return saved ? JSON.parse(saved) : []
  })
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef(null)

  // Schließe Menü beim Klick außerhalb
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setMenuOpen(false)
      }
    }

    if (menuOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [menuOpen])

  // Lade Artikel aus LocalStorage beim Start
  useEffect(() => {
    const saved = localStorage.getItem('nzz_articles')
    if (saved) {
      try {
        setArticles(JSON.parse(saved))
      } catch (e) {
        console.error('Fehler beim Laden der Artikel:', e)
      }
    }
  }, [])

  // Speichere Artikel in LocalStorage
  useEffect(() => {
    if (articles.length > 0) {
      localStorage.setItem('nzz_articles', JSON.stringify(articles))
    }
  }, [articles])

  // Speichere hideReadArticles Präferenz
  useEffect(() => {
    localStorage.setItem('nzz_hide_read_articles', hideReadArticles.toString())
  }, [hideReadArticles])

  // Speichere gelesene Artikel
  useEffect(() => {
    localStorage.setItem('nzz_read_articles', JSON.stringify(readArticles))
  }, [readArticles])

  const handleArticlesLoaded = (newArticles) => {
    setArticles(newArticles)
    setError(null)
  }

  const handleArticleUpdate = (updatedArticles) => {
    setArticles(updatedArticles)
  }

  const handleArticleRead = (articleId) => {
    setReadArticles(prev => {
      if (!prev.includes(articleId)) {
        return [...prev, articleId]
      }
      return prev
    })
  }

  const handleDateChange = async (newDate) => {
    setCurrentDate(newDate)

    // Prüfe ob Artikel für dieses Datum bereits lokal vorhanden sind
    const articlesForDate = articles.filter(a => {
      try {
        const articleDate = new Date(a.date).toISOString().split('T')[0]
        return articleDate === newDate
      } catch {
        return false
      }
    })

    // Wenn keine Artikel lokal vorhanden, vom Server laden
    if (articlesForDate.length === 0 && loadDateFunc) {
      await loadDateFunc(newDate)
    }
  }

  // Extrahiere einzigartige Daten aus Artikeln
  const availableDates = [...new Set(articles.map(a => {
    try {
      return new Date(a.date).toISOString().split('T')[0]
    } catch {
      return new Date().toISOString().split('T')[0]
    }
  }))].sort((a, b) => new Date(b) - new Date(a)) // Neueste zuerst

  // Setze initial auf neuestes Datum
  useEffect(() => {
    if (availableDates.length > 0 && currentDate === 'all') {
      setCurrentDate(availableDates[0])
    }
  }, [availableDates.length])

  const filteredArticles = articles.filter(a => {
    // Datums-Filter
    if (currentDate !== 'all') {
      try {
        const articleDate = new Date(a.date).toISOString().split('T')[0]
        if (articleDate !== currentDate) return false
      } catch {
        return false
      }
    }

    // Gelesene Artikel Filter
    if (hideReadArticles && readArticles.includes(a.id)) {
      return false
    }

    return true
  })

  return (
    <div className="app">
      <header className="app-header">
        <h1>📰 NZZ Reader</h1>
        <div className="header-controls" ref={menuRef}>
          <ZipLoader
            onArticlesLoaded={handleArticlesLoaded}
            onLoading={setIsLoading}
            onError={setError}
            onAvailableDatesLoaded={setAvailableServerDates}
            onLoadDateReady={(func) => setLoadDateFunc(() => func)}
          />
          <button
            className="hamburger-btn"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Menü"
          >
            ☰
          </button>
          {menuOpen && (
            <div className="dropdown-menu">
            <label className="menu-toggle">
              <input
                type="checkbox"
                checked={hideReadArticles}
                onChange={(e) => setHideReadArticles(e.target.checked)}
              />
              <span className="toggle-slider"></span>
              <span className="toggle-label">Gelesene Artikel ausblenden</span>
            </label>
            {hideReadArticles && (
              <button
                className="reset-read-btn"
                onClick={() => {
                  setReadArticles([])
                  setMenuOpen(false)
                }}
                title="Alle Artikel als ungelesen markieren"
              >
                🔄 Zurücksetzen
              </button>
            )}
            </div>
          )}
        </div>
      </header>

      {error && (
        <div className="error-banner">
          {error}
        </div>
      )}

      {isLoading && (
        <div className="loading-overlay">
          <div className="spinner"></div>
          <p>Lade Artikel...</p>
        </div>
      )}

      {articles.length > 0 && availableDates.length > 0 && (
        <DateNavigator
          availableDates={availableDates}
          availableServerDates={availableServerDates}
          currentDate={currentDate}
          onDateChange={handleDateChange}
        />
      )}

      {articles.length === 0 && !isLoading ? (
        <div className="welcome">
          <div className="welcome-icon">📰</div>
          <h2>Willkommen beim NZZ Reader</h2>
          <p>Lade die neuesten Artikel, um zu beginnen.</p>
          <p className="hint">Die Artikel werden automatisch vom Server geladen.</p>
        </div>
      ) : (
        <ArticleReader
          articles={filteredArticles}
          onArticlesUpdate={handleArticleUpdate}
          onArticleRead={handleArticleRead}
          hideReadArticles={hideReadArticles}
        />
      )}
    </div>
  )
}

export default App
