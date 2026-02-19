import { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import './AdminPanel.css'

function AdminPanel({ onClose }) {
  const { token } = useAuth()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showAddUser, setShowAddUser] = useState(false)
  const [showResetPassword, setShowResetPassword] = useState(null)

  // Neue User-Daten
  const [newEmail, setNewEmail] = useState('')
  const [newPassword, setNewPassword] = useState('')

  // Reset Password
  const [resetPassword, setResetPassword] = useState('')

  useEffect(() => {
    loadUsers()
  }, [])

  const loadUsers = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/users', {
        headers: { 'Authorization': `Bearer ${token}` }
      })

      if (!response.ok) throw new Error('Fehler beim Laden der User')

      const data = await response.json()
      setUsers(data.users)
      setLoading(false)
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  const handleAddUser = async (e) => {
    e.preventDefault()
    setError(null)

    try {
      const response = await fetch('http://localhost:8000/api/users', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ email: newEmail, password: newPassword })
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error)
      }

      setNewEmail('')
      setNewPassword('')
      setShowAddUser(false)
      loadUsers()
    } catch (err) {
      setError(err.message)
    }
  }

  const handleDeleteUser = async (userId) => {
    if (!confirm('User wirklich löschen?')) return

    try {
      const response = await fetch(`http://localhost:8000/api/users/${userId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error)
      }

      loadUsers()
    } catch (err) {
      setError(err.message)
    }
  }

  const handleResetPassword = async (userId) => {
    if (!resetPassword) return

    try {
      const response = await fetch(`http://localhost:8000/api/users/${userId}/reset-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ new_password: resetPassword })
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error)
      }

      setResetPassword('')
      setShowResetPassword(null)
      alert('Passwort zurückgesetzt')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="admin-panel-overlay" onClick={onClose}>
      <div className="admin-panel" onClick={(e) => e.stopPropagation()}>
        <div className="admin-panel-header">
          <h2>👥 User-Verwaltung</h2>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        {error && (
          <div className="admin-error">
            {error}
          </div>
        )}

        <div className="admin-panel-content">
          {loading ? (
            <div className="admin-loading">Lade User...</div>
          ) : (
            <>
              <div className="admin-actions">
                <button
                  className="add-user-btn"
                  onClick={() => setShowAddUser(!showAddUser)}
                >
                  ➕ Neuer User
                </button>
              </div>

              {showAddUser && (
                <form onSubmit={handleAddUser} className="add-user-form">
                  <h3>Neuer User</h3>
                  <input
                    type="email"
                    placeholder="Email"
                    value={newEmail}
                    onChange={(e) => setNewEmail(e.target.value)}
                    required
                  />
                  <input
                    type="password"
                    placeholder="Passwort (min. 6 Zeichen)"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                    minLength={6}
                  />
                  <div className="form-buttons">
                    <button type="submit" className="btn-primary">Erstellen</button>
                    <button type="button" className="btn-secondary" onClick={() => setShowAddUser(false)}>
                      Abbrechen
                    </button>
                  </div>
                </form>
              )}

              <div className="users-list">
                {users.map(user => (
                  <div key={user.id} className="user-item">
                    <div className="user-info">
                      <div className="user-email">
                        {user.email}
                        {user.is_admin && <span className="admin-badge">Admin</span>}
                      </div>
                      <div className="user-meta">
                        Erstellt: {new Date(user.created_at).toLocaleDateString('de-CH')}
                      </div>
                    </div>

                    <div className="user-actions">
                      <button
                        className="btn-reset"
                        onClick={() => setShowResetPassword(showResetPassword === user.id ? null : user.id)}
                      >
                        🔑 Passwort
                      </button>
                      {!user.is_admin && (
                        <button
                          className="btn-delete"
                          onClick={() => handleDeleteUser(user.id)}
                        >
                          🗑
                        </button>
                      )}
                    </div>

                    {showResetPassword === user.id && (
                      <div className="reset-password-form">
                        <input
                          type="password"
                          placeholder="Neues Passwort"
                          value={resetPassword}
                          onChange={(e) => setResetPassword(e.target.value)}
                          minLength={6}
                        />
                        <button
                          onClick={() => handleResetPassword(user.id)}
                          className="btn-primary"
                        >
                          Zurücksetzen
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default AdminPanel
