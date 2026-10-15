import { useState, useEffect, useRef } from 'react'
import { Play, Pause, Volume2, AlertCircle } from 'lucide-react'
import { getRecordingAudio } from '../api/recordings'

export function AudioPlayer({ recordingId }) {
  const [audioUrl, setAudioUrl] = useState(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const audioRef = useRef(null)

  useEffect(() => {
    let objectUrl = null
    const loadAudio = async () => {
      setLoading(true)
      setError(null)
      try {
        const blob = await getRecordingAudio(recordingId)
        if (blob instanceof Blob) {
          objectUrl = URL.createObjectURL(blob)
          setAudioUrl(objectUrl)
        } else {
          setError('Invalid audio format received from server')
        }
      } catch (err) {
        console.error('Audio load failed:', err)
        setError(err.message || 'Encrypted audio unavailable')
      } finally {
        setLoading(false)
      }
    }

    if (recordingId) {
      loadAudio()
    }

    return () => {
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl)
      }
    }
  }, [recordingId])

  const togglePlay = () => {
    if (!audioRef.current) return
    if (isPlaying) {
      audioRef.current.pause()
      setIsPlaying(false)
    } else {
      audioRef.current.play()
      setIsPlaying(true)
    }
  }

  if (loading) {
    return <div className="audio-player-loading">Loading encrypted audio...</div>
  }

  if (error) {
    return (
      <div className="audio-player-error">
        <AlertCircle className="player-error-icon" />
        <span>{error}</span>
      </div>
    )
  }

  return (
    <div className="audio-player-card">
      <button className="play-toggle-btn" onClick={togglePlay}>
        {isPlaying ? <Pause className="btn-icon" /> : <Play className="btn-icon" />}
      </button>

      <div className="player-info">
        <Volume2 className="volume-icon" />
        <span className="player-title">Audio Recording #{recordingId}</span>
      </div>

      <audio
        ref={audioRef}
        src={audioUrl}
        onEnded={() => setIsPlaying(false)}
        controls
        className="native-audio-element"
      />
    </div>
  )
}
