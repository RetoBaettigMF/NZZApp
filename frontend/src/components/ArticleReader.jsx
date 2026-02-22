import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import './ArticleReader.css'

const FONT_SIZES = ['0.85rem', '1rem', '1.2rem', '1.5rem']

function ArticleReader({ articles, onArticleRead, hideReadArticles, fontSizeLevel = 1, savedArticles, onSaveToggle }) {
  const [currentIndex, setCurrentIndex] = useState(0)
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
  const isPlayingRef = useRef(false)
  const currentIndexRef = useRef(0)
  const handleNextRef = useRef(null)
  const articlesLengthRef = useRef(0)

  const currentArticle = articles[currentIndex]
  currentIndexRef.current = currentIndex
  articlesLengthRef.current = articles.length

  const getArticleText = (article) => {
    const body = (article.rawContent || '')
      .replace(/^#{1,6}\s+/gm, '')
      .replace(/\*\*(.+?)\*\*/g, '$1')
      .replace(/\*(.+?)\*/g, '$1')
      .replace(/\[(.+?)\]\(.+?\)/g, '$1')
      .replace(/^[-*]\s+/gm, '')
      .replace(/\n{3,}/g, '\n\n')
      .trim()
    return `${article.title}. ${body}`
  }

  const stopReading = useCallback(() => {
    window.speechSynthesis?.cancel()
    autoPlayRef.current = false
    setIsPlaying(false)
    isPlayingRef.current = false
  }, [])

  const splitText = (text, maxLen = 3000) => {
    if (text.length <= maxLen) return [text]
    const chunks = []
    let remaining = text
    while (remaining.length > maxLen) {
      let cutAt = remaining.lastIndexOf('. ', maxLen)
      if (cutAt < maxLen * 0.5) cutAt = remaining.lastIndexOf(' ', maxLen)
      if (cutAt < 0) cutAt = maxLen
      else cutAt += 1
      chunks.push(remaining.slice(0, cutAt).trim())
      remaining = remaining.slice(cutAt).trim()
    }
    if (remaining) chunks.push(remaining)
    return chunks
  }

  const startReading = useCallback((article) => {
    if (!window.speechSynthesis) {
      setTtsError('Vorlesen wird auf diesem Browser nicht unterstützt.')
      setTimeout(() => setTtsError(null), 5000)
      return
    }
    const synth = window.speechSynthesis
    const text = getArticleText(article)
    const chunks = splitText(text)

    const voices = synth.getVoices()
    const voice = voices.find(v => v.lang === 'de-CH')
      || voices.find(v => v.lang === 'de-DE')
      || voices.find(v => v.lang.startsWith('de'))

    const speakChunk = (index) => {
      if (index >= chunks.length) {
        if (currentIndexRef.current < articlesLengthRef.current - 1) {
          autoPlayRef.current = true
          handleNextRef.current?.()
        } else {
          setIsPlaying(false)
          isPlayingRef.current = false
        }
        return
      }
      const utterance = new SpeechSynthesisUtterance(chunks[index])
      if (voice) {
        utterance.voice = voice
        utterance.lang = voice.lang
      }
      utterance.rate = 1.0
      utterance.onend = () => speakChunk(index + 1)
      utterance.onerror = (e) => {
        // interrupted = synth.cancel() wurde aufgerufen (z.B. Stop-Button) → kein Fehler zeigen
        if (e.error === 'interrupted' || e.error === 'canceled') return
        setIsPlaying(false)
        isPlayingRef.current = false
        setTtsError(`Fehler: ${e.error || 'unbekannt'}`)
        setTimeout(() => setTtsError(null), 5000)
      }
      utteranceRef.current = utterance
      synth.speak(utterance)
    }

    setIsPlaying(true)
    isPlayingRef.current = true
    setTtsError(null)

    // cancel() + sofortiges speak() verursacht synthesis-failed auf Android.
    // 50ms Delay reicht und liegt noch im User-Gesture-Aktivierungsfenster.
    synth.cancel()
    setTimeout(() => {
      try {
        speakChunk(0)
      } catch (e) {
        setTtsError(`Fehler beim Starten: ${e.message}`)
        setTimeout(() => setTtsError(null), 5000)
        setIsPlaying(false)
        isPlayingRef.current = false
      }
    }, 50)
  }, [])

  const toggleAudio = useCallback(() => {
    if (isPlayingRef.current) {
      stopReading()
    } else {
      startReading(currentArticle)
    }
  }, [currentArticle, startReading, stopReading])

  // Scroll to top on article change, stop audio wenn kein Autoplay ausstehend
  useEffect(() => {
    window.scrollTo(0, 0)
    document.documentElement.scrollTop = 0
    if (cardRef.current) cardRef.current.scrollTop = 0
    setTimeout(() => {
      window.scrollTo(0, 0)
      document.documentElement.scrollTop = 0
    }, 10)
    if (!autoPlayRef.current) {
      window.speechSynthesis?.cancel()
      setIsPlaying(false)
      isPlayingRef.current = false
    }
  }, [currentIndex])

  // Auto-play nach Navigation
  useEffect(() => {
    if (autoPlayRef.current && currentArticle) {
      autoPlayRef.current = false
      const timer = setTimeout(() => startReading(currentArticle), 300)
      return () => clearTimeout(timer)
    }
  }, [currentArticle, startReading])

  // Passe currentIndex an wenn er ungültig wird (z.B. wenn Artikel ausgeblendet werden)
  useEffect(() => {
    if (currentIndex >= articles.length && articles.length > 0) {
      setCurrentIndex(articles.length - 1)
    }
  }, [articles.length, currentIndex])

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
      const articleIsSaved = savedArticles.includes(articles[currentIndex]?.id || articles[currentIndex]?.url)
      animateAway('left', () => {
        markRead()
        if (!hideReadArticles || articleIsSaved) {
          setCurrentIndex(prev => prev + 1)
        }
      })
    } else {
      alert('Du bist bereits beim ältesten Artikel')
    }
  }, [currentIndex, articles, isAnimating, animateAway, markRead, hideReadArticles, savedArticles])

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
    onSaveToggle(currentArticle.id || currentArticle.url)
  }, [currentArticle, onSaveToggle])

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
      const articleIsSaved = savedArticles.includes(articles[currentIndex]?.id || articles[currentIndex]?.url)
      animateAway('left', () => {
        markRead()
        if (!hideReadArticles || articleIsSaved) {
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
  }, [currentIndex, articles, animateAway, markRead, hideReadArticles, savedArticles])

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
      {ttsError && <div className="tts-error-banner">{ttsError}</div>}
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
