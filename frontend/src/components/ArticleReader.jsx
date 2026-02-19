import { useState, useEffect, useCallback, useMemo } from 'react'
import './ArticleReader.css'

function ArticleReader({ articles, onArticlesUpdate, onArticleRead, hideReadArticles }) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [savedArticles, setSavedArticles] = useState(() => {
    const saved = localStorage.getItem('nzz_saved_articles')
    return saved ? JSON.parse(saved) : []
  })
  const [direction, setDirection] = useState(null)
  const [lastReadPosition, setLastReadPosition] = useState(() => {
    const saved = localStorage.getItem('nzz_last_read_position')
    return saved ? JSON.parse(saved) : null
  })

  const currentArticle = articles[currentIndex]

  // Passe currentIndex an wenn er ungültig wird (z.B. wenn Artikel ausgeblendet werden)
  useEffect(() => {
    if (currentIndex >= articles.length && articles.length > 0) {
      setCurrentIndex(articles.length - 1)
    }
  }, [articles.length, currentIndex])

  // Speichere markierte Artikel
  useEffect(() => {
    localStorage.setItem('nzz_saved_articles', JSON.stringify(savedArticles))
  }, [savedArticles])

  // Speichere aktuelle Leseposition bei jedem Artikel-Wechsel
  useEffect(() => {
    if (currentArticle) {
      const position = {
        articleId: currentArticle.id,
        date: currentArticle.date,
        category: currentArticle.category,
        timestamp: Date.now(),
        index: currentIndex
      }
      setLastReadPosition(position)
      localStorage.setItem('nzz_last_read_position', JSON.stringify(position))
    }
  }, [currentIndex, currentArticle])

  const handleNext = useCallback(() => {
    if (currentIndex < articles.length - 1) {
      // Markiere aktuellen Artikel als gelesen BEVOR wir zum nächsten navigieren
      if (currentArticle && onArticleRead) {
        onArticleRead(currentArticle.id)
      }

      setDirection('left')
      setTimeout(() => {
        // Wenn hideReadArticles aktiv ist, bleibe beim gleichen Index
        // (der nächste Artikel rutscht nach durch das Filtern)
        // Sonst gehe zum nächsten Index
        if (hideReadArticles) {
          setCurrentIndex(prev => prev) // Bleibe beim gleichen Index
        } else {
          setCurrentIndex(prev => prev + 1)
        }
        setDirection(null)
      }, 200)
    } else {
      // Am Ende der Liste angelangt
      alert('Du bist bereits beim ältesten Artikel')
    }
  }, [currentIndex, articles.length, currentArticle, onArticleRead, hideReadArticles])

  const handlePrevious = useCallback(() => {
    if (currentIndex > 0) {
      // Markiere aktuellen Artikel als gelesen BEVOR wir zum vorherigen navigieren
      if (currentArticle && onArticleRead) {
        onArticleRead(currentArticle.id)
      }

      setDirection('right')
      setTimeout(() => {
        setCurrentIndex(prev => prev - 1)
        setDirection(null)
      }, 200)
    } else {
      // Am Anfang der Liste angelangt (neuester Artikel)
      alert('Du bist bereits beim neuesten Artikel')
    }
  }, [currentIndex, currentArticle, onArticleRead])

  const toggleSave = useCallback(() => {
    if (!currentArticle) return

    const articleId = currentArticle.id || currentArticle.url
    setSavedArticles(prev => {
      if (prev.includes(articleId)) {
        return prev.filter(id => id !== articleId)
      } else {
        return [...prev, articleId]
      }
    })
  }, [currentArticle])

  const jumpToNewest = useCallback(() => {
    // Markiere aktuellen Artikel als gelesen BEVOR wir springen
    if (currentArticle && onArticleRead) {
      onArticleRead(currentArticle.id)
    }
    setCurrentIndex(0) // Index 0 = neuester Artikel (bereits nach Datum sortiert)
  }, [currentArticle, onArticleRead])

  const isSaved = currentArticle && savedArticles.includes(currentArticle.id || currentArticle.url)

  // Entferne doppelten Titel aus Content (wenn vorhanden)
  const cleanedContent = useMemo(() => {
    if (!currentArticle?.content || !currentArticle?.title) {
      return currentArticle?.content || ''
    }

    // Erstelle ein temporäres DOM-Element zum Parsen
    const tempDiv = document.createElement('div')
    tempDiv.innerHTML = currentArticle.content

    // Finde erstes Heading (h1, h2, h3)
    const firstHeading = tempDiv.querySelector('h1, h2, h3')

    // Wenn das erste Heading dem Titel entspricht, entferne es
    if (firstHeading) {
      const headingText = firstHeading.textContent.trim()
      const titleText = currentArticle.title.trim()

      // Robuster Vergleich: Entferne auch Zeilenumbrüche und mehrfache Leerzeichen
      const normalizeText = (text) => text.replace(/\s+/g, ' ').trim()

      if (normalizeText(headingText) === normalizeText(titleText)) {
        firstHeading.remove()
      }
    }

    return tempDiv.innerHTML
  }, [currentArticle])

  // Touch/Swipe Handling
  const [touchStart, setTouchStart] = useState(null)
  const [touchEnd, setTouchEnd] = useState(null)
  const minSwipeDistance = 50

  const onTouchStart = (e) => {
    setTouchStart(e.targetTouches[0].clientX)
  }

  const onTouchMove = (e) => {
    setTouchEnd(e.targetTouches[0].clientX)
  }

  const onTouchEnd = () => {
    if (!touchStart || !touchEnd) return
    const distance = touchStart - touchEnd
    const isLeftSwipe = distance > minSwipeDistance
    const isRightSwipe = distance < -minSwipeDistance

    if (isLeftSwipe) {
      handleNext()
    } else if (isRightSwipe) {
      handlePrevious()
    }

    setTouchStart(null)
    setTouchEnd(null)
  }

  // Tastatur-Navigation
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'ArrowRight' || e.key === ' ') {
        e.preventDefault()
        handleNext()
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault()
        handlePrevious()
      } else if (e.key === '*') {
        e.preventDefault()
        toggleSave()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleNext, handlePrevious, toggleSave, jumpToNewest])

  const deleteCurrentArticle = () => {
    const updatedArticles = articles.filter((_, idx) => idx !== currentIndex)
    onArticlesUpdate(updatedArticles)
    if (currentIndex >= updatedArticles.length && currentIndex > 0) {
      setCurrentIndex(currentIndex - 1)
    }
  }

  if (!currentArticle) {
    return (
      <div className="article-reader empty">
        <div className="empty-message">
          <span className="icon">🎉</span>
          <h3>Alle Artikel gelesen!</h3>
          <p>Es gibt keine weiteren Artikel in dieser Kategorie.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="article-reader">
      <div className="progress-bar">
        <div 
          className="progress-fill" 
          style={{ width: `${((currentIndex + 1) / articles.length) * 100}%` }}
        />
        <span className="progress-text">
          {currentIndex + 1} / {articles.length}
        </span>
      </div>

      <div 
        className={`article-card ${direction ? `slide-${direction}` : ''}`}
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
      >
        <div className="article-header">
          <span className="article-category">{currentArticle.category}</span>
          <button 
            className={`save-btn ${isSaved ? 'saved' : ''}`}
            onClick={toggleSave}
            title="Mit * markieren zum Behalten"
          >
            {isSaved ? '★' : '☆'}
          </button>
        </div>

        <h2 className="article-title">{currentArticle.title}</h2>
        
        <div className="article-meta">
          {currentArticle.date && (
            <span className="article-date">
              {new Date(currentArticle.date).toLocaleDateString('de-CH')}
            </span>
          )}
          <a 
            href={currentArticle.url} 
            target="_blank" 
            rel="noopener noreferrer"
            className="article-link"
          >
            Original öffnen ↗
          </a>
        </div>

        <div
          className="article-content"
          dangerouslySetInnerHTML={{ __html: cleanedContent }}
        />
      </div>

      <div className="article-controls">
        <button
          className="control-btn prev"
          onClick={handlePrevious}
          disabled={currentIndex === 0}
        >
          ← Zurück
        </button>

        <button
          className="control-btn jump-newest"
          onClick={jumpToNewest}
          disabled={currentIndex === 0}
          title="Zum neuesten Artikel springen"
        >
          🔝 Neuester Artikel
        </button>

        <button
          className="control-btn delete"
          onClick={deleteCurrentArticle}
          disabled={isSaved}
          title={isSaved ? 'Markierte Artikel können nicht gelöscht werden' : 'Artikel löschen'}
        >
          🗑 Löschen
        </button>

        <button
          className="control-btn save-toggle"
          onClick={toggleSave}
        >
          {isSaved ? '★ Markiert' : '☆ Markieren'}
        </button>

        <button
          className="control-btn next"
          onClick={handleNext}
          disabled={currentIndex >= articles.length - 1}
        >
          Weiter →
        </button>
      </div>

      <div className="swipe-hint">
        ← Swipe oder Pfeiltasten zum Navigieren | * zum Markieren →
      </div>
    </div>
  )
}

export default ArticleReader
