import './HelpModal.css'

const HELP_SECTIONS = [
  {
    title: 'Navigieren',
    items: [
      { key: 'Swipe links / rechts', desc: 'Nächster / vorheriger Artikel' },
      { key: '← →  Pfeiltasten', desc: 'Nächster / vorheriger Artikel' },
      { key: 'Leertaste', desc: 'Nächster Artikel' },
      { key: '« »  im Header', desc: 'Tag wechseln' },
      { key: 'Neuester Artikel', desc: 'Direkt zum aktuellsten Artikel springen' },
    ],
  },
  {
    title: 'Artikel',
    items: [
      { key: 'Doppeltippen', desc: 'Zwischen Original und AI-Zusammenfassung wechseln' },
      { key: '★  oder Taste *', desc: 'Artikel markieren / Markierung aufheben' },
      { key: 'Löschen', desc: 'Artikel entfernen (nur wenn nicht markiert)' },
    ],
  },
  {
    title: 'Einstellungen',
    items: [
      { key: 'Schriftgrösse', desc: '4 Stufen im Menu wählbar, wird gespeichert' },
      { key: 'Gelesene ausblenden', desc: 'Bereits gelesene Artikel verbergen' },
      { key: '↻  im Header', desc: 'Neueste Artikel vom Server laden' },
    ],
  },
]

function HelpModal({ onClose }) {
  return (
    <div className="help-overlay" onClick={onClose}>
      <div className="help-modal" onClick={(e) => e.stopPropagation()}>
        <div className="help-header">
          <h2>Bedienungsanleitung</h2>
          <button className="help-close" onClick={onClose}>✕</button>
        </div>
        <div className="help-content">
          {HELP_SECTIONS.map((section) => (
            <div key={section.title} className="help-section">
              <h3>{section.title}</h3>
              <dl>
                {section.items.map((item) => (
                  <div key={item.key} className="help-row">
                    <dt>{item.key}</dt>
                    <dd>{item.desc}</dd>
                  </div>
                ))}
              </dl>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default HelpModal
