import { useState, useEffect } from 'react'
import './App.css'
import ArticleReader from './components/ArticleReader'
import CategorySelector from './components/CategorySelector'
import DateNavigator from './components/DateNavigator'
import ZipLoader from './components/ZipLoader'

function App() {
  const [articles, setArticles] = useState([])
  const [currentCategory, setCurrentCategory] = useState('all')
  const [currentDate, setCurrentDate] = useState('all')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [availableServerDates, setAvailableServerDates] = useState([])
  const [loadDateFunc, setLoadDateFunc] = useState(null)

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

  const handleArticlesLoaded = (newArticles) => {
    setArticles(newArticles)
    setError(null)
  }

  const handleArticleUpdate = (updatedArticles) => {
    setArticles(updatedArticles)
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
    // Kategorie-Filter
    const matchCategory = currentCategory === 'all' || a.category === currentCategory

    // Datums-Filter
    let matchDate = true
    if (currentDate !== 'all') {
      try {
        const articleDate = new Date(a.date).toISOString().split('T')[0]
        matchDate = articleDate === currentDate
      } catch {
        matchDate = false
      }
    }

    return matchCategory && matchDate
  })

  const categories = [...new Set(articles.map(a => a.category))]

  return (
    <div className="app">
      <header className="app-header">
        <h1>📰 NZZ Reader</h1>
        <ZipLoader
          onArticlesLoaded={handleArticlesLoaded}
          onLoading={setIsLoading}
          onError={setError}
          onAvailableDatesLoaded={setAvailableServerDates}
          onLoadDateReady={(func) => setLoadDateFunc(() => func)}
        />
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

      {articles.length > 0 && (
        <CategorySelector
          categories={categories}
          currentCategory={currentCategory}
          onCategoryChange={setCurrentCategory}
          articleCount={filteredArticles.length}
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
        />
      )}
    </div>
  )
}

export default App
