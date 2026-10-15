import { useState, useRef, useEffect, useCallback } from 'react'
import { Mic, Pause, Play, Square, Bluetooth, Radio, AlertCircle, RefreshCw, Volume2 } from 'lucide-react'
import {
  createRecording,
  pauseRecording,
  resumeRecording,
  stopRecording,
  uploadRecordingAudio,
  setAudioSource,
} from '../api/recordings'
import { getTranscriptionStatus, retryTranscription } from '../api/transcriptions'
import { processExtraction } from '../api/conversations'

export function RecordingControls({ onRecordingFinished, onSelectConsent }) {
  const [recordingState, setRecordingState] = useState('idle') // idle, preparing, recording, paused, uploading, processing, ready, failed
  const [activeRecording, setActiveRecording] = useState(null)
  const [audioSource, setAudioSourceState] = useState('microphone')
  const [duration, setDuration] = useState(0)
  const [errorMessage, setErrorMessage] = useState(null)
  const [transcriptionJob, setTranscriptionJob] = useState(null)

  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])
  const timerRef = useRef(null)
  const canvasRef = useRef(null)
  const audioContextRef = useRef(null)
  const analyserRef = useRef(null)
  const animFrameRef = useRef(null)

  // Clean up timer and audio context on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
      if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
        audioContextRef.current.close().catch(() => {})
      }
    }
  }, [])

  // Audio visualization canvas renderer
  const drawWaveform = useCallback(() => {
    if (!analyserRef.current || !canvasRef.current) return

    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    const bufferLength = analyserRef.current.frequencyBinCount
    const dataArray = new Uint8Array(bufferLength)

    const render = () => {
      if (!analyserRef.current) return
      analyserRef.current.getByteFrequencyData(dataArray)

      ctx.clearRect(0, 0, canvas.width, canvas.height)
      const barWidth = (canvas.width / bufferLength) * 2.5
      let x = 0

      for (let i = 0; i < bufferLength; i++) {
        const barHeight = (dataArray[i] / 255) * canvas.height
        const gradient = ctx.createLinearGradient(0, canvas.height, 0, 0)
        gradient.addColorStop(0, '#6366f1')
        gradient.addColorStop(1, '#a855f7')

        ctx.fillStyle = gradient
        ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight)
        x += barWidth + 2
      }

      animFrameRef.current = requestAnimationFrame(render)
    }

    render()
  }, [])

  const startNativeRecording = async () => {
    setErrorMessage(null)
    setRecordingState('preparing')

    try {
      // 1. Request Browser Mic Permissions
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })

      // 2. Start Backend Recording Session
      const recordingData = await createRecording({
        audioSource,
        sourceAvailable: true,
        microphonePermissionGranted: true,
        consentAcknowledged: true,
      })

      setActiveRecording(recordingData)

      // 3. Initialize Audio Visualization
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)()
      const source = audioCtx.createMediaStreamSource(stream)
      const analyser = audioCtx.createAnalyser()
      analyser.fftSize = 64
      source.connect(analyser)

      audioContextRef.current = audioCtx
      analyserRef.current = analyser

      // 4. Initialize MediaRecorder
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      mediaRecorderRef.current = mediaRecorder
      audioChunksRef.current = []

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data)
        }
      }

      mediaRecorder.start(500)
      setRecordingState('recording')
      setDuration(0)

      // Start duration timer
      timerRef.current = setInterval(() => {
        setDuration((prev) => prev + 1)
      }, 1000)

      // Start visualizer
      drawWaveform()
    } catch (err) {
      console.error('Recording initialization failed:', err)
      setRecordingState('failed')

      if (err.code === 'consent_required' || err.status === 400 || err.status === 403) {
        setErrorMessage('Jurisdiction consent is required before recording.')
        if (onSelectConsent) onSelectConsent()
      } else {
        setErrorMessage(err.message || 'Microphone access denied or audio recording failed.')
      }
    }
  }

  const handlePause = async () => {
    if (!activeRecording) return
    try {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.pause()
      }
      if (timerRef.current) clearInterval(timerRef.current)
      await pauseRecording(activeRecording.id)
      setRecordingState('paused')
    } catch (err) {
      console.error('Pause failed:', err)
      setErrorMessage(err.message || 'Failed to pause recording')
    }
  }

  const handleResume = async () => {
    if (!activeRecording) return
    try {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'paused') {
        mediaRecorderRef.current.resume()
      }
      timerRef.current = setInterval(() => {
        setDuration((prev) => prev + 1)
      }, 1000)
      await resumeRecording(activeRecording.id)
      setRecordingState('recording')
      drawWaveform()
    } catch (err) {
      console.error('Resume failed:', err)
      setErrorMessage(err.message || 'Failed to resume recording')
    }
  }

  const pollTranscription = useCallback(async (recordingId) => {
    setRecordingState('processing')
    let attempts = 0
    const maxAttempts = 30

    const interval = setInterval(async () => {
      attempts += 1
      try {
        const job = await getTranscriptionStatus(recordingId)
        setTranscriptionJob(job)

        if (job.status === 'completed') {
          clearInterval(interval)
          setRecordingState('ready')
          // Auto-trigger extraction process
          try {
            await processExtraction(recordingId)
          } catch (extErr) {
            console.warn('Auto extraction trigger note:', extErr)
          }
          if (onRecordingFinished) onRecordingFinished(recordingId)
        } else if (job.status === 'failed') {
          clearInterval(interval)
          setRecordingState('failed')
          setErrorMessage(job.last_error_message || 'Transcription processing failed')
        }
      } catch (err) {
        console.warn('Transcription polling note:', err)
      }

      if (attempts >= maxAttempts) {
        clearInterval(interval)
        setRecordingState('failed')
        setErrorMessage('Transcription timed out. You can retry transcription manually.')
      }
    }, 2000)
  }, [onRecordingFinished])

  const handleStop = async () => {
    if (!activeRecording) return
    setRecordingState('uploading')

    if (timerRef.current) clearInterval(timerRef.current)
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)

    const mediaRecorder = mediaRecorderRef.current

    return new Promise((resolve) => {
      if (!mediaRecorder) {
        resolve()
        return
      }

      mediaRecorder.onstop = async () => {
        try {
          // Stop mic stream tracks
          mediaRecorder.stream.getTracks().forEach((track) => track.stop())

          // Package recorded audio blob
          const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
          const durationMs = duration * 1000

          // Upload audio to backend
          await uploadRecordingAudio(activeRecording.id, audioBlob, durationMs)

          // Finalize recording in backend
          await stopRecording(activeRecording.id)

          // Poll processing status
          await pollTranscription(activeRecording.id)
        } catch (err) {
          console.error('Upload/Stop error:', err)
          setRecordingState('failed')
          setErrorMessage(err.message || 'Failed to upload audio or stop recording')
        } finally {
          resolve()
        }
      }

      mediaRecorder.stop()
    })
  }

  const handleSourceChange = async (source) => {
    setAudioSourceState(source)
    if (activeRecording && (recordingState === 'recording' || recordingState === 'paused')) {
      try {
        await setAudioSource(activeRecording.id, source, true)
      } catch (err) {
        console.warn('Audio source change note:', err)
      }
    }
  }

  const handleRetryTranscription = async () => {
    if (!activeRecording) return
    setRecordingState('processing')
    setErrorMessage(null)
    try {
      await retryTranscription(activeRecording.id)
      await pollTranscription(activeRecording.id)
    } catch (err) {
      setRecordingState('failed')
      setErrorMessage(err.message || 'Retry failed')
    }
  }

  const formatTime = (secs) => {
    const mins = Math.floor(secs / 60)
    const remaining = secs % 60
    return `${mins.toString().padStart(2, '0')}:${remaining.toString().padStart(2, '0')}`
  }

  return (
    <div className="recording-controls-card">
      <div className="controls-header">
        <div className="state-badge-container">
          <span className={`state-badge state-${recordingState}`}>
            {recordingState.toUpperCase()}
          </span>
        </div>

        {/* Audio Source Selector */}
        <div className="source-selector">
          <button
            className={`source-btn ${audioSource === 'microphone' ? 'active' : ''}`}
            onClick={() => handleSourceChange('microphone')}
            disabled={recordingState === 'recording' || recordingState === 'paused'}
            title="Internal Microphone"
          >
            <Mic className="source-icon" /> Mic
          </button>
          <button
            className={`source-btn ${audioSource === 'bluetooth' ? 'active' : ''}`}
            onClick={() => handleSourceChange('bluetooth')}
            disabled={recordingState === 'recording' || recordingState === 'paused'}
            title="Bluetooth Headset / Audio Source"
          >
            <Bluetooth className="source-icon" /> BT
          </button>
          <button
            className={`source-btn ${audioSource === 'system' ? 'active' : ''}`}
            onClick={() => handleSourceChange('system')}
            disabled={recordingState === 'recording' || recordingState === 'paused'}
            title="System Audio"
          >
            <Radio className="source-icon" /> System
          </button>
        </div>
      </div>

      {/* Timer & Waveform */}
      <div className="recording-display">
        <div className="timer-display">{formatTime(duration)}</div>
        <canvas ref={canvasRef} className="waveform-canvas" width={300} height={60} />
      </div>

      {/* Controls Actions */}
      <div className="controls-actions">
        {recordingState === 'idle' && (
          <button className="btn btn-record" onClick={startNativeRecording}>
            <Mic className="btn-icon" /> Start Recording
          </button>
        )}

        {recordingState === 'recording' && (
          <>
            <button className="btn btn-pause" onClick={handlePause}>
              <Pause className="btn-icon" /> Pause
            </button>
            <button className="btn btn-stop" onClick={handleStop}>
              <Square className="btn-icon" /> Stop & Process
            </button>
          </>
        )}

        {recordingState === 'paused' && (
          <>
            <button className="btn btn-resume" onClick={handleResume}>
              <Play className="btn-icon" /> Resume
            </button>
            <button className="btn btn-stop" onClick={handleStop}>
              <Square className="btn-icon" /> Stop & Process
            </button>
          </>
        )}

        {recordingState === 'processing' && (
          <div className="processing-status-indicator">
            <RefreshCw className="spin status-icon" />
            <span>Transcribing & Analyzing Audio...</span>
          </div>
        )}

        {recordingState === 'ready' && (
          <div className="success-status-indicator">
            <Volume2 className="status-icon" />
            <span>Transcript & Insights Ready!</span>
            <button className="btn btn-secondary btn-sm" onClick={() => setRecordingState('idle')}>
              Record Another
            </button>
          </div>
        )}

        {recordingState === 'failed' && (
          <div className="failed-actions">
            {activeRecording && (
              <button className="btn btn-secondary" onClick={handleRetryTranscription}>
                <RefreshCw className="btn-icon" /> Retry Transcription
              </button>
            )}
            <button className="btn btn-primary" onClick={() => setRecordingState('idle')}>
              New Recording
            </button>
          </div>
        )}
      </div>

      {errorMessage && (
        <div className="error-banner">
          <AlertCircle className="error-icon" />
          <span>{errorMessage}</span>
        </div>
      )}
    </div>
  )
}
