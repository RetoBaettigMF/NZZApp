import { useState, useEffect } from 'react'
import './App.css'
import ArticleReader from './components/ArticleReader'
import CategorySelector from './components/CategorySelector'
import ZipLoader from './components/ZipLoader'

function App() {
  const [articles, setArticles] = useState([])
  const [currentCategory, setCurrentCategory] = useState('all')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

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

  const filteredArticles = currentCategory === 'all' 
    ? articles 
    : articles.filter(a => a.category === currentCategory)

  const categories = [...new Set(articles.map(a => a.category))]

  return (
    <div className="app">
      <header className="app-header">
        <h1>📰 NZZ Reader</h1>
        <ZipLoader 
          onArticlesLoaded={handleArticlesLoaded}
          onLoading={setIsLoading}
          onError={setError}
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
