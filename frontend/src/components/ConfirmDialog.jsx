import { AlertTriangle } from 'lucide-react'

export function ConfirmDialog({ isOpen, title, message, confirmLabel = 'Confirm', isDanger = false, onConfirm, onCancel, isLoading }) {
  if (!isOpen) return null

  return (
    <div className="modal-overlay">
      <div className="modal-content confirm-modal">
        <div className={`modal-header ${isDanger ? 'header-danger' : ''}`}>
          <AlertTriangle className="modal-header-icon" />
          <h3>{title}</h3>
        </div>

        <div className="modal-body">
          <p className="confirm-message">{message}</p>
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onCancel} disabled={isLoading}>
            Cancel
          </button>
          <button
            className={`btn ${isDanger ? 'btn-danger' : 'btn-primary'}`}
            onClick={onConfirm}
            disabled={isLoading}
          >
            {isLoading ? 'Processing...' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
