import { useState, useEffect } from 'react'
import JSZip from 'jszip'
import './ZipLoader.css'

const API_BASE = '/api'

function ZipLoader({ onArticlesLoaded, onLoading, onError }) {
  const [lastUpdate, setLastUpdate] = useState(() => {
    return localStorage.getItem('nzz_last_update') || null
  })

  // Automatisch beim Start laden
  useEffect(() => {
    loadLatestArticles()
  }, [])

  const loadLatestArticles = async () => {
    onLoading(true)
    onError(null)

    try {
      // Prüfe ob lokal bereits Artikel vorhanden
      const localArticles = localStorage.getItem('nzz_articles')
      if (localArticles) {
        const parsed = JSON.parse(localArticles)
        if (parsed.length > 0) {
          onArticlesLoaded(parsed)
        }
      }

      // Lade neuestes Archiv vom Server
      const response = await fetch(`${API_BASE}/latest`)
      if (!response.ok) {
        throw new Error('Keine Archive gefunden')
      }

      const data = await response.json()
      
      // Prüfe ob neuer als lokale Daten
      if (lastUpdate === data.date && localArticles) {
        onLoading(false)
        return // Daten sind aktuell
      }

      // Lade ZIP
      const zipResponse = await fetch(data.download_url)
      if (!zipResponse.ok) {
        throw new Error('ZIP konnte nicht geladen werden')
      }

      const zipBlob = await zipResponse.blob()
      const zip = await JSZip.loadAsync(zipBlob)

      // Extrahiere Markdown-Dateien
      const articles = []
      const promises = []

      zip.forEach((relativePath, zipEntry) => {
        if (relativePath.endsWith('.md') && !relativePath.includes('manifest')) {
          promises.push(
            zipEntry.async('text').then(content => {
              const article = parseMarkdown(content, relativePath)
              if (article) articles.push(article)
            })
          )
        }
      })

      await Promise.all(promises)

      // Sortiere nach Datum (neueste zuerst)
      articles.sort((a, b) => new Date(b.date) - new Date(a.date))

      onArticlesLoaded(articles)
      localStorage.setItem('nzz_last_update', data.date)
      setLastUpdate(data.date)

    } catch (err) {
      console.error('Fehler beim Laden:', err)
      onError('Konnte keine neuen Artikel laden. Offline-Modus aktiv.')
    } finally {
      onLoading(false)
    }
  }

  const parseMarkdown = (content, path) => {
    try {
      // Extrahiere Metadaten aus dem Markdown
      const lines = content.split('\n')
      let title = ''
      let date = ''
      let category = 'allgemein'
      let url = ''
      let bodyStart = 0

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i]

        if (line.startsWith('# ') && !title) {
          title = line.substring(2).trim()
        } else if (line.includes('Datum:')) {
          // Extrahiere Datum (mit oder ohne Bold-Markdown)
          const datumMatch = line.match(/\*?\*?Datum:\*?\*?\s*(.+)/)
          if (datumMatch) {
            date = datumMatch[1].trim()
          }
        } else if (line.includes('Kategorie:')) {
          // Extrahiere Kategorie (mit oder ohne Bold-Markdown)
          const katMatch = line.match(/\*?\*?Kategorie:\*?\*?\s*(.+)/)
          if (katMatch) {
            category = katMatch[1].trim()
          }
        } else if (line.includes('Original auf NZZ.ch öffnen') || line.includes('URL:')) {
          // Extrahiere URL aus Markdown-Link: [Text](URL)
          const urlMatch = line.match(/\[.*?\]\((https?:\/\/[^\)]+)\)/)
          if (urlMatch) {
            url = urlMatch[1].trim()
          } else if (line.includes('URL:')) {
            url = line.split('URL:')[1].trim()
          }
        } else if (line.startsWith('---')) {
          bodyStart = i + 1
          break
        }
      }

      // Body extrahieren und ersten Titel entfernen
      let bodyLines = lines.slice(bodyStart)

      // Entferne ersten Markdown-Titel (# Titel) falls vorhanden
      // Backend sendet immer "# Titel" als erste Zeile nach dem Separator
      if (bodyLines.length > 0 && bodyLines[0].trim().startsWith('# ')) {
        bodyLines.shift() // Entferne erste Zeile
      }

      // Entferne leere Zeilen am Anfang
      while (bodyLines.length > 0 && bodyLines[0].trim() === '') {
        bodyLines.shift()
      }

      const body = bodyLines.join('\n')

      // Konvertiere Markdown zu HTML (einfache Version)
      const htmlContent = body
        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/^\* (.*$)/gim, '<li>$1</li>')
        .replace(/^\- (.*$)/gim, '<li>$1</li>')
        .replace(/\*\*(.*)\*\*/gim, '<strong>$1</strong>')
        .replace(/\*(.*)\*/gim, '<em>$1</em>')
        .replace(/\[([^\]]+)\]\(([^)]+)\)/gim, '<a href="$2" target="_blank">$1</a>')
        .replace(/\n/gim, '<br>')

      // Generiere ID aus URL oder Pfad
      const id = url || path.replace(/[^a-zA-Z0-9]/g, '_')

      return {
        id,
        title: title || 'Unbekannter Titel',
        date: date || new Date().toISOString(),
        category: category.toLowerCase(),
        url: url || '',
        content: htmlContent,
        rawContent: body
      }

    } catch (e) {
      console.error('Fehler beim Parsen:', e)
      return null
    }
  }

  return (
    <div className="zip-loader">
      <button 
        className="load-btn"
        onClick={loadLatestArticles}
        title="Neueste Artikel laden"
      >
        🔄 Aktualisieren
      </button>
      {lastUpdate && (
        <span className="last-update">
          Stand: {new Date(lastUpdate).toLocaleDateString('de-CH')}
        </span>
      )}
    </div>
  )
}

export default ZipLoader
