import { useState } from 'react'
import './DateNavigator.css'

function DateNavigator({ availableDates, currentDate, onDateChange }) {
  const currentIndex = availableDates.indexOf(currentDate)
  const hasPrevious = currentIndex > 0
  const hasNext = currentIndex < availableDates.length - 1

  const handlePrevious = () => {
    if (hasPrevious) {
      onDateChange(availableDates[currentIndex - 1])
    }
  }

  const handleNext = () => {
    if (hasNext) {
      onDateChange(availableDates[currentIndex + 1])
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

  if (availableDates.length === 0) return null

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
