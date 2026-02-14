import './CategorySelector.css'

function CategorySelector({ categories, currentCategory, onCategoryChange, articleCount }) {
  const categoryLabels = {
    'all': 'Alle',
    'sport': '🏃 Sport',
    'wirtschaft': '💼 Wirtschaft',
    'wissenschaft': '🔬 Wissenschaft',
    'lokal': '📍 Lokal',
    'welt': '🌍 Welt',
    'allgemein': '📰 Allgemein'
  }

  return (
    <div className="category-selector">
      <div className="category-tabs">
        <button
          className={`category-tab ${currentCategory === 'all' ? 'active' : ''}`}
          onClick={() => onCategoryChange('all')}
        >
          {categoryLabels['all']}
        </button>
        {categories.map(cat => (
          <button
            key={cat}
            className={`category-tab ${currentCategory === cat ? 'active' : ''}`}
            onClick={() => onCategoryChange(cat)}
          >
            {categoryLabels[cat] || cat}
          </button>
        ))}
      </div>
      <span className="article-count">
        {articleCount} Artikel
      </span>
    </div>
  )
}

export default CategorySelector
