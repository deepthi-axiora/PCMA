import { apiFetch } from './client.js'

export async function getCommitments() {
  return apiFetch('/v1/commitments')
}

export async function updateCommitmentStatus(commitmentId, status) {
  return apiFetch(`/v1/commitments/${commitmentId}`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  })
}

export async function getReminders() {
  return apiFetch('/v1/reminders')
}

export async function createReminder(data) {
  return apiFetch('/v1/reminders', {
    method: 'POST',
    body: JSON.stringify({
      title: data.title,
      remind_at: data.remind_at,
      timezone: data.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
      priority: data.priority || 'normal',
      commitment_id: data.commitment_id || null,
      action_item_id: data.action_item_id || null,
      deadline_id: data.deadline_id || null,
    }),
  })
}

export async function updateReminderStatus(reminderId, status) {
  return apiFetch(`/v1/reminders/${reminderId}`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  })
}

export async function deleteReminder(reminderId) {
  return apiFetch(`/v1/reminders/${reminderId}`, {
    method: 'DELETE',
  })
}
