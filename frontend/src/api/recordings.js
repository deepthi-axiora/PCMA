import { apiFetch } from './client.js'

export async function createRecording(data) {
  return apiFetch('/v1/recordings', {
    method: 'POST',
    body: JSON.stringify({
      audio_source: data.audioSource || 'microphone',
      source_available: data.sourceAvailable ?? true,
      microphone_permission_granted: data.microphonePermissionGranted ?? true,
      consent_acknowledged: data.consentAcknowledged ?? true,
    }),
  })
}

export async function getRecordings() {
  return apiFetch('/v1/recordings')
}

export async function getRecordingDetail(recordingId) {
  return apiFetch(`/v1/recordings/${recordingId}`)
}

export async function pauseRecording(recordingId) {
  return apiFetch(`/v1/recordings/${recordingId}/pause`, {
    method: 'POST',
  })
}

export async function resumeRecording(recordingId) {
  return apiFetch(`/v1/recordings/${recordingId}/resume`, {
    method: 'POST',
  })
}

export async function stopRecording(recordingId) {
  return apiFetch(`/v1/recordings/${recordingId}/stop`, {
    method: 'POST',
  })
}

export async function setAudioSource(recordingId, audioSource, sourceAvailable = true) {
  return apiFetch(`/v1/recordings/${recordingId}/audio-source`, {
    method: 'PATCH',
    body: JSON.stringify({
      audio_source: audioSource,
      source_available: sourceAvailable,
    }),
  })
}

export async function uploadRecordingAudio(recordingId, audioBlob, durationMs = null) {
  const formData = new FormData()
  const file = new File([audioBlob], `recording_${recordingId}.wav`, {
    type: audioBlob.type || 'audio/wav',
  })
  formData.append('audio', file)

  let endpoint = `/v1/recordings/${recordingId}/audio`
  if (durationMs !== null && durationMs !== undefined) {
    endpoint += `?duration_ms=${Math.round(durationMs)}`
  }

  return apiFetch(endpoint, {
    method: 'POST',
    body: formData,
  })
}

export async function getRecordingAudio(recordingId) {
  return apiFetch(`/v1/recordings/${recordingId}/audio`)
}
