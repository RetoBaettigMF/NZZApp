import { useState } from 'react'
import './DateNavigator.css'

function DateNavigator({ availableDates, availableServerDates, currentDate, onDateChange }) {
  // Verwende Server-Daten wenn verfügbar, sonst lokale Daten
  const allDates = availableServerDates.length > 0 ? availableServerDates : availableDates

  const currentIndex = allDates.indexOf(currentDate)
  // Da allDates nach neuesten Datum zuerst sortiert ist:
  // - Vorheriger Tag (älter) = Index erhöhen
  // - Nächster Tag (neuer) = Index verringern
  const hasPrevious = currentIndex < allDates.length - 1
  const hasNext = currentIndex > 0

  const handlePrevious = () => {
    // Vorheriger Tag = älteres Datum = höherer Index
    if (hasPrevious) {
      onDateChange(allDates[currentIndex + 1])
    }
  }

  const handleNext = () => {
    // Nächster Tag = neueres Datum = niedrigerer Index
    if (hasNext) {
      onDateChange(allDates[currentIndex - 1])
    }
  }

  const formatDate = (dateString) => {
    const date = new Date(dateString)
    return date.toLocaleDateString('de-CH', {
      weekday: 'short',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    })
  }

  if (allDates.length === 0) return null

  return (
    <div className="date-navigator">
      <button
        className="date-nav-btn"
        onClick={handlePrevious}
        disabled={!hasPrevious}
      >
        ← Vorheriger Tag
      </button>

      <span className="date-display">
        {formatDate(currentDate)}
      </span>

      <button
        className="date-nav-btn"
        onClick={handleNext}
        disabled={!hasNext}
      >
        Nächster Tag →
      </button>
    </div>
  )
}

export default DateNavigator
