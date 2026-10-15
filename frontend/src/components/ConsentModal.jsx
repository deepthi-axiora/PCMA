import { useState } from 'react'
import { Shield, AlertTriangle, CheckCircle, XCircle } from 'lucide-react'
import { updateProfile } from '../api/profile'
import { useAuth } from '../context/AuthContext'

const JURISDICTIONS = [
  { id: 'US-CA', name: 'California, USA (All-Party Consent)', notice: 'California Penal Code § 632 requires all parties to consent to confidential conversation recording.' },
  { id: 'US-NY', name: 'New York, USA (One-Party Consent)', notice: 'New York law requires at least one party to consent to conversation recording.' },
  { id: 'EU-GDPR', name: 'European Union (GDPR Compliant)', notice: 'GDPR Article 6 requires explicit informed consent for audio processing and identity profiling.' },
  { id: 'UK', name: 'United Kingdom (DPA / UK-GDPR)', notice: 'UK Data Protection Act requires unambiguous notification and purpose specification before recording.' },
  { id: 'IN', name: 'India (DPDP Act 2023)', notice: 'Digital Personal Data Protection Act requires explicit notice for audio data processing.' },
  { id: 'GENERIC-ALL', name: 'All-Party Consent (Default Global)', notice: 'All participants must be informed and acknowledge consent before recording starts.' },
]

export function ConsentModal({ isOpen, onClose, onConsentConfirmed }) {
  const { profile, refreshProfile } = useAuth()
  const [selectedJurisdiction, setSelectedJurisdiction] = useState(profile?.jurisdiction || 'US-CA')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState(null)

  if (!isOpen) return null

  const currentNotice = JURISDICTIONS.find((j) => j.id === selectedJurisdiction)?.notice

  const handleConfirm = async () => {
    setIsSubmitting(true)
    setError(null)
    try {
      await updateProfile({ jurisdiction: selectedJurisdiction })
      await refreshProfile()
      onConsentConfirmed({
        jurisdiction: selectedJurisdiction,
        consent_acknowledged: true,
      })
      onClose()
    } catch (err) {
      console.error('Consent save failed:', err)
      setError(err.message || 'Failed to save consent settings')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDecline = () => {
    setError('Recording is disabled when consent is declined.')
    onConsentConfirmed({
      jurisdiction: selectedJurisdiction,
      consent_acknowledged: false,
    })
  }

  return (
    <div className="modal-overlay">
      <div className="modal-content consent-modal">
        <div className="modal-header">
          <Shield className="modal-header-icon" />
          <h2>Jurisdiction & Consent Setup</h2>
        </div>

        <div className="modal-body">
          <p className="consent-intro">
            PCMA requires explicit compliance setup based on your legal jurisdiction before enabling audio recording.
          </p>

          <div className="form-group">
            <label htmlFor="jurisdiction-select">Select Legal Jurisdiction:</label>
            <select
              id="jurisdiction-select"
              value={selectedJurisdiction}
              onChange={(e) => setSelectedJurisdiction(e.target.value)}
              className="select-input"
            >
              {JURISDICTIONS.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.name}
                </option>
              ))}
            </select>
          </div>

          <div className="disclosure-box">
            <AlertTriangle className="disclosure-icon" />
            <div className="disclosure-text">
              <strong>Statutory Requirement:</strong>
              <p>{currentNotice}</p>
            </div>
          </div>

          <div className="legal-disclaimer">
            <em>
              Disclaimer: PCMA provides compliance workflows but does not provide formal legal advice. Verify local conversation privacy laws.
            </em>
          </div>

          {error && <div className="error-banner">{error}</div>}
        </div>

        <div className="modal-footer">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleDecline}
            disabled={isSubmitting}
          >
            <XCircle className="btn-icon" /> Decline
          </button>

          <button
            type="button"
            className="btn btn-primary"
            onClick={handleConfirm}
            disabled={isSubmitting}
          >
            <CheckCircle className="btn-icon" /> Acknowledge & Continue
          </button>
        </div>
      </div>
    </div>
  )
}
