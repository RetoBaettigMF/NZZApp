import { useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import './UserMenu.css'

function UserMenu({ onShowAdmin }) {
  const { user, logout, changePassword } = useAuth()
  const [showChangePassword, setShowChangePassword] = useState(false)
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(false)

  const handleChangePassword = async (e) => {
    e.preventDefault()
    setError(null)
    setSuccess(false)

    const result = await changePassword(oldPassword, newPassword)

    if (result.success) {
      setSuccess(true)
      setOldPassword('')
      setNewPassword('')
      setTimeout(() => {
        setShowChangePassword(false)
        setSuccess(false)
      }, 2000)
    } else {
      setError(result.error)
    }
  }

  return (
    <div className="user-menu">
      <div className="user-info-menu">
        <div className="user-email">{user.email}</div>
        {user.is_admin && <span className="admin-badge">Admin</span>}
      </div>

      <div className="menu-divider"></div>

      {user.is_admin && (
        <>
          <button className="menu-item" onClick={onShowAdmin}>
            👥 User-Verwaltung
          </button>
          <div className="menu-divider"></div>
        </>
      )}

      <button
        className="menu-item"
        onClick={() => setShowChangePassword(!showChangePassword)}
      >
        🔑 Passwort ändern
      </button>

      {showChangePassword && (
        <form onSubmit={handleChangePassword} className="change-password-form">
          {error && <div className="form-error">{error}</div>}
          {success && <div className="form-success">Passwort geändert!</div>}

          <input
            type="password"
            placeholder="Altes Passwort"
            value={oldPassword}
            onChange={(e) => setOldPassword(e.target.value)}
            required
          />
          <input
            type="password"
            placeholder="Neues Passwort (min. 6 Zeichen)"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            minLength={6}
          />
          <button type="submit" className="btn-change-password">
            Ändern
          </button>
        </form>
      )}

      <div className="menu-divider"></div>

      <button className="menu-item logout" onClick={logout}>
        🚪 Abmelden
      </button>
    </div>
  )
}

export default UserMenu
