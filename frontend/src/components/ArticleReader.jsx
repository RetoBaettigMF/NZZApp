import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import './ArticleReader.css'

const FONT_SIZES = ['0.85rem', '1rem', '1.2rem', '1.5rem']

function ArticleReader({ articles, onArticlesUpdate, onArticleRead, hideReadArticles, fontSizeLevel = 1 }) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [savedArticles, setSavedArticles] = useState(() => {
    const saved = localStorage.getItem('nzz_saved_articles')
    return saved ? JSON.parse(saved) : []
  })
  const [swipeX, setSwipeX] = useState(0)
  const [isSwiping, setIsSwiping] = useState(false)
  const [isAnimating, setIsAnimating] = useState(false)
  const [showSummary, setShowSummary] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [ttsError, setTtsError] = useState(null)
  const [entranceDir, setEntranceDir] = useState(null)
  const cardRef = useRef(null)
  const touchStartX = useRef(null)
  const swipeXRef = useRef(0)
  const lastTapRef = useRef(0)
  const utteranceRef = useRef(null)
  const autoPlayRef = useRef(false)
  const currentIndexRef = useRef(0)
  const handleNextRef = useRef(null)
  const speakArticleRef = useRef(null)
  const wakeLockRef = useRef(null)
  const iosWatchdogRef = useRef(null)

  const currentArticle = articles[currentIndex]
  currentIndexRef.current = currentIndex

  const acquireWakeLock = async () => {
    try {
      wakeLockRef.current = await navigator.wakeLock?.request('screen')
    } catch (e) {}
  }

  const releaseWakeLock = () => {
    wakeLockRef.current?.release()
    wakeLockRef.current = null
    clearInterval(iosWatchdogRef.current)
    iosWatchdogRef.current = null
  }

  const getReadableText = useCallback((article) => {
    const body = (article.rawContent || '')
      .replace(/#{1,6}\s/g, '')
      .replace(/\*\*(.*?)\*\*/g, '$1')
      .replace(/\*(.*?)\*/g, '$1')
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
      .replace(/[-*]\s/g, '')
      .replace(/\n{2,}/g, '. ')
      .trim()
    return `${article.title}. ${body}`
  }, [])

  const speakArticle = useCallback((article, textOverride = null) => {
    if (!('speechSynthesis' in window)) {
      setTtsError('Vorlesen wird auf diesem Gerät nicht unterstützt.')
      setTimeout(() => setTtsError(null), 4000)
      return
    }
    acquireWakeLock()
    const synth = window.speechSynthesis
    synth.cancel()
    const text = textOverride ?? getReadableText(article)
    const utterance = new SpeechSynthesisUtterance(text)
    // Voice selection: de-CH → de-DE fallback
    const voices = synth.getVoices()
    const voice = voices.find(v => v.lang === 'de-CH') || voices.find(v => v.lang === 'de-DE')
    if (voice) utterance.voice = voice
    utterance.lang = 'de-CH'
    utterance.rate = 1.0
    utterance.onend = () => {
      clearInterval(iosWatchdogRef.current)
      iosWatchdogRef.current = null
      if (currentIndexRef.current < articles.length - 1) {
        autoPlayRef.current = true
        handleNextRef.current?.()
      } else {
        releaseWakeLock()
        setIsPlaying(false)
      }
    }
    utterance.onerror = (e) => {
      clearInterval(iosWatchdogRef.current)
      iosWatchdogRef.current = null
      releaseWakeLock()
      setIsPlaying(false)
      setTtsError(`Vorlesen fehlgeschlagen: ${e.error || 'Unbekannter Fehler'}`)
      setTimeout(() => setTtsError(null), 4000)
    }
    utteranceRef.current = utterance
    synth.speak(utterance)
    setIsPlaying(true)
    setTtsError(null)
    // iOS watchdog: prevent speech from stopping on long texts
    if (iosWatchdogRef.current) clearInterval(iosWatchdogRef.current)
    iosWatchdogRef.current = setInterval(() => {
      if (synth.speaking && !synth.paused) {
        synth.pause()
        synth.resume()
      }
    }, 10000)
  }, [getReadableText, articles.length])

  speakArticleRef.current = speakArticle

  const toggleAudio = useCallback(() => {
    if (!('speechSynthesis' in window)) {
      setTtsError('Vorlesen wird auf diesem Gerät nicht unterstützt.')
      setTimeout(() => setTtsError(null), 4000)
      return
    }
    const synth = window.speechSynthesis
    if (isPlaying) {
      synth.cancel()
      releaseWakeLock()
      setIsPlaying(false)
      return
    }
    const text = showSummary && currentArticle?.summary
      ? currentArticle.summary.replace(/\n/g, ' ').trim()
      : null
    speakArticle(currentArticle, text)
  }, [isPlaying, currentArticle, speakArticle, showSummary])

  // Scroll to top on article change, stop audio (oder auto-weiter vorlesen)
  useEffect(() => {
    window.speechSynthesis.cancel()
    window.scrollTo(0, 0)
    document.documentElement.scrollTop = 0
    if (cardRef.current) {
      cardRef.current.scrollTop = 0
    }
    setTimeout(() => {
      window.scrollTo(0, 0)
      document.documentElement.scrollTop = 0
    }, 10)
    if (autoPlayRef.current) {
      autoPlayRef.current = false
      const article = articles[currentIndex]
      if (article) setTimeout(() => speakArticleRef.current(article), 150)
    } else {
      releaseWakeLock()
      setIsPlaying(false)
    }
  }, [currentIndex])

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
      localStorage.setItem('nzz_last_read_position', JSON.stringify(position))
    }
  }, [currentIndex, currentArticle])

  const updateSwipeX = (x) => {
    swipeXRef.current = x
    setSwipeX(x)
  }

  const markRead = useCallback(() => {
    if (currentArticle && onArticleRead) {
      onArticleRead(currentArticle.id)
    }
  }, [currentArticle, onArticleRead])

  // Animiert die Karte nach links/rechts aus dem Bildschirm, dann wird onComplete aufgerufen
  const animateAway = useCallback((direction, onComplete) => {
    const targetX = direction === 'left' ? -window.innerWidth : window.innerWidth
    setIsAnimating(true)
    updateSwipeX(targetX)
    setTimeout(() => {
      const entranceDirection = direction === 'left' ? 'right' : 'left'
      onComplete()
      setEntranceDir(entranceDirection)
      updateSwipeX(0)
      setTimeout(() => {
        setIsAnimating(false)
        setEntranceDir(null)
      }, 280)
    }, 250)
  }, [])

  const handleNext = useCallback(() => {
    if (isAnimating) return
    if (currentIndex < articles.length - 1) {
      animateAway('left', () => {
        markRead()
        if (!hideReadArticles) {
          setCurrentIndex(prev => prev + 1)
        }
      })
    } else {
      alert('Du bist bereits beim ältesten Artikel')
    }
  }, [currentIndex, articles.length, isAnimating, animateAway, markRead, hideReadArticles])

  handleNextRef.current = handleNext

  const handlePrevious = useCallback(() => {
    if (isAnimating) return
    if (currentIndex > 0) {
      animateAway('right', () => {
        markRead()
        setCurrentIndex(prev => prev - 1)
      })
    } else {
      alert('Du bist bereits beim neuesten Artikel')
    }
  }, [currentIndex, isAnimating, animateAway, markRead])

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
    markRead()
    setCurrentIndex(0)
  }, [markRead])

  // Touch/Swipe Handling mit Echtzeit-Animation
  const minSwipeDistance = 50

  const onTouchStart = useCallback((e) => {
    if (isAnimating) return
    touchStartX.current = e.targetTouches[0].clientX
    setIsSwiping(true)
  }, [isAnimating])

  const onTouchMove = useCallback((e) => {
    if (touchStartX.current === null) return
    const delta = e.targetTouches[0].clientX - touchStartX.current
    if (Math.abs(delta) > window.innerWidth * 0.12) {
      updateSwipeX(delta)
    }
  }, [])

  const onTouchEnd = useCallback(() => {
    if (touchStartX.current === null) return
    setIsSwiping(false)
    const delta = swipeXRef.current
    touchStartX.current = null

    if (delta < -minSwipeDistance && currentIndex < articles.length - 1) {
      animateAway('left', () => {
        markRead()
        if (!hideReadArticles) {
          setCurrentIndex(prev => prev + 1)
        }
      })
    } else if (delta > minSwipeDistance && currentIndex > 0) {
      animateAway('right', () => {
        markRead()
        setCurrentIndex(prev => prev - 1)
      })
    } else {
      updateSwipeX(0) // Snap back zur Mitte
    }
  }, [currentIndex, articles.length, animateAway, markRead, hideReadArticles])

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
  }, [handleNext, handlePrevious, toggleSave])

  const deleteCurrentArticle = () => {
    const updatedArticles = articles.filter((_, idx) => idx !== currentIndex)
    onArticlesUpdate(updatedArticles)
    if (currentIndex >= updatedArticles.length && currentIndex > 0) {
      setCurrentIndex(currentIndex - 1)
    }
  }

  // Entferne die ersten 2 Zeilen (Wiederholung des Titels)
  // Normalisiere \n zu <br> damit beide Formate funktionieren
  const cleanedContent = useMemo(() => {
    if (!currentArticle?.content) return ''
    const normalized = currentArticle.content.replace(/\n/g, '<br>')
    const parts = normalized.split('<br>')
    return parts.slice(2).join('<br>').replace(/^(<br>\s*)+/, '')
  }, [currentArticle])

  // Doppeltap/Doppelklick: zwischen Original und Zusammenfassung umschalten
  const handleCardClick = useCallback(() => {
    const now = Date.now()
    if (now - lastTapRef.current < 300 && currentArticle?.summary) {
      setShowSummary(prev => !prev)
    }
    lastTapRef.current = now
  }, [currentArticle])

  const displayContent = showSummary && currentArticle?.summary
    ? currentArticle.summary.replace(/\n/g, '<br>')
    : cleanedContent

  const isSaved = currentArticle && savedArticles.includes(currentArticle.id || currentArticle.url)

  const cardStyle = entranceDir ? {} : {
    transform: `translateX(${swipeX}px)`,
    transition: isSwiping ? 'none' : 'transform 0.25s ease, opacity 0.25s ease',
    opacity: Math.max(0, 1 - Math.abs(swipeX) / (window.innerWidth * 0.6)),
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
      {ttsError && (
        <div className="tts-error-banner">{ttsError}</div>
      )}
      <div className="article-card-wrapper">
        <div
          ref={cardRef}
          className={`article-card${entranceDir ? ` enter-from-${entranceDir}` : ''}`}
          style={cardStyle}
          onTouchStart={onTouchStart}
          onTouchMove={onTouchMove}
          onTouchEnd={onTouchEnd}
          onClick={handleCardClick}
        >
          <div className="article-info">
            <span className="article-category">{currentArticle.category}</span>
            <span className="article-date">
              {new Date(currentArticle.date).toLocaleDateString('de-CH')}
            </span>
            <span className="article-count">{currentIndex + 1}/{articles.length}</span>
            <a href={currentArticle.url} target="_blank" rel="noopener noreferrer" className="article-link">
              ↗
            </a>
            {showSummary && currentArticle?.summary && (
              <span className="summary-indicator">🤖 AI</span>
            )}
            <button
              className={`audio-btn ${isPlaying ? 'playing' : ''}`}
              onClick={(e) => { e.stopPropagation(); toggleAudio() }}
              title={isPlaying ? 'Vorlesen stoppen' : 'Artikel vorlesen'}
            >
              {isPlaying ? '⏸' : '▶'}
            </button>
            <button className={`save-btn ${isSaved ? 'saved' : ''}`} onClick={toggleSave}>
              {isSaved ? '★' : '☆'}
            </button>
          </div>

          <h2 className="article-title">{currentArticle.title}</h2>

          <div
            className="article-content"
            style={{ fontSize: FONT_SIZES[fontSizeLevel] }}
            dangerouslySetInnerHTML={{ __html: displayContent }}
          />
        </div>
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
