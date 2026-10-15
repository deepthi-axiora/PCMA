import { apiFetch } from './client.js'

export async function getTranscriptionStatus(recordingId) {
  return apiFetch(`/v1/recordings/${recordingId}/transcription-status`)
}

export async function getTranscript(recordingId) {
  return apiFetch(`/v1/recordings/${recordingId}/transcript`)
}

export async function retryTranscription(recordingId) {
  return apiFetch(`/v1/recordings/${recordingId}/transcription/retry`, {
    method: 'POST',
  })
}

export async function getDiarizationStatus(recordingId) {
  return apiFetch(`/v1/recordings/${recordingId}/diarization-status`)
}

export async function relabelSpeaker(recordingId, speakerId, data) {
  return apiFetch(`/v1/recordings/${recordingId}/speakers/${speakerId}`, {
    method: 'PATCH',
    body: JSON.stringify({
      label: data.label !== undefined ? data.label : null,
      person_id: data.person_id !== undefined ? data.person_id : null,
    }),
  })
}
